"""Validation, statuses, priority, findings, reviewer actions, the Case File and the audit log (build spec 11)."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.access import EDITABLE_STATES, application_for
from core.db import db, parallel
from core.security import AuthenticatedUser, require_role
from core.clock import as_of_date
from core.ratelimit import rate_limit
from services import audit, casefile, preflight as preflight_service, priority as priority_service, reviews
from services.validation import run_validation

router = APIRouter(tags=["Findings"])

REVIEWER = ["reviewer"]
READERS = ["reviewer", "rule_admin"]

# What an institution may see of its own application's audit trail: its own steps and the requests
# made to it. Validation runs are left out, since their details name findings it does not see.
INSTITUTION_EVENTS = {"application_created", "application_seeded", "application_submitted", "document_upload_started",
                      "document_finalized", "document_processed", "document_processing_failed",
                      "finding_request_evidence", "evidence_request_fulfilled", "rooms_saved"}


class FindingAction(BaseModel):
    action: Literal["resolve", "dismiss", "request_evidence"]
    reason: str = Field(..., min_length=3, max_length=2000)
    due_date: Optional[date] = None


@router.post("/applications/{application_id}/validate")
def validate(application_id: str, user: AuthenticatedUser = Depends(require_role(REVIEWER))):
    application = application_for(user, application_id)
    if application["workflow_status"] == "draft":
        raise HTTPException(status_code=409, detail="The institution has not submitted this application yet")
    result = run_validation(application_id, "full", user)
    application, findings = parallel(lambda: db.fetch_one("applications", id=application_id),
                                     lambda: db.fetch_all("findings", application_id=application_id))
    statuses, priority = parallel(lambda: casefile.status_view(application, findings),
                                  lambda: casefile.priority_view(application, findings))
    return {**result, "statuses": statuses, "priority": priority}


@router.post("/applications/{application_id}/preflight", dependencies=[Depends(rate_limit("20/minute", "preflight"))])
def preflight(application_id: str, user: AuthenticatedUser = Depends(require_role(["institution"]))):
    """The institution's own check before submitting: within-application checks only, nothing stored."""
    application = application_for(user, application_id)
    if application["workflow_status"] not in EDITABLE_STATES:
        raise HTTPException(status_code=409, detail="Pre-flight is for an application you can still change")
    return preflight_service.run(application)


@router.get("/applications/{application_id}/statuses")
def get_statuses(application_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    return casefile.status_view(application_for(user, application_id))


@router.get("/applications/{application_id}/priority")
def get_priority(application_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    return casefile.priority_view(application_for(user, application_id))


@router.get("/applications/{application_id}/findings")
def list_findings(application_id: str,
                        user: AuthenticatedUser = Depends(require_role(["institution", "reviewer", "rule_admin"]))):
    # The access check and the findings at once; the findings are returned only if the check passes
    _, items = parallel(lambda: application_for(user, application_id),
                        lambda: casefile.findings_for(application_id, institution_view=user.role == "institution"))
    return items


def _finding_for(user: AuthenticatedUser, finding_id: str) -> tuple[dict, dict]:
    finding = db.fetch_one("findings", id=finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    application = application_for(user, finding["application_id"])
    if user.role == "institution" and (finding["status"] != "evidence_requested" or finding["is_cross_institution"]):
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding, application


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str,
                      user: AuthenticatedUser = Depends(require_role(["institution", "reviewer", "rule_admin"]))):
    finding, _ = _finding_for(user, finding_id)
    items = casefile.findings_for(finding["application_id"], institution_view=user.role == "institution")
    return next(f for f in items if f["id"] == finding_id)


@router.post("/findings/{finding_id}/actions")
def finding_action(finding_id: str, body: FindingAction, user: AuthenticatedUser = Depends(require_role(REVIEWER))):
    finding, application = _finding_for(user, finding_id)
    reviews.act(user, finding, application, body.action, body.reason, body.due_date)
    return next(f for f in casefile.findings_for(application["id"]) if f["id"] == finding_id)


@router.get("/applications/{application_id}/casefile")
def get_case_file(application_id: str, user: AuthenticatedUser = Depends(require_role(REVIEWER))):
    return casefile.case_file(application_for(user, application_id))


@router.post("/applications/{application_id}/casefile/snapshot", status_code=201)
def save_snapshot(application_id: str, user: AuthenticatedUser = Depends(require_role(REVIEWER))):
    application = application_for(user, application_id)
    payload = casefile.case_file(application)
    snapshot = db.insert("case_file_snapshots", {"application_id": application_id, "generated_by": user.id, "payload": payload})
    audit.record(user, "case_file_snapshot", "case_file_snapshot", snapshot["id"], application_id,
                 {"findings": len(payload["findings"]), "run_id": (payload["latest_run"] or {}).get("id")})
    return {"id": snapshot["id"], "created_at": snapshot.get("created_at")}


@router.get("/applications/{application_id}/casefile/snapshots")
def list_snapshots(application_id: str, user: AuthenticatedUser = Depends(require_role(REVIEWER))):
    application_for(user, application_id)
    return (db.table("case_file_snapshots").select("id,created_at,generated_by").eq("application_id", application_id)
            .order("created_at", desc=True).execute().data or [])


@router.get("/audit", tags=["Audit"])
def audit_log(application_id: Optional[str] = None, limit: int = Query(100, ge=1, le=500),
                    user: AuthenticatedUser = Depends(require_role(["institution", "reviewer", "rule_admin"]))):
    """The audit trail, newest first. An institution sees only the events of its own applications."""
    if user.role == "institution":
        if not application_id:
            raise HTTPException(status_code=422, detail="Choose one of your applications")
        application_for(user, application_id)
    query = db.table("audit_events").select("*").order("id", desc=True).limit(limit)
    if application_id:
        query = query.eq("application_id", application_id)
    events = query.execute().data or []
    if user.role == "institution":
        events = [e for e in events if e["event_type"] in INSTITUTION_EVENTS]
    names = {m["user_id"]: m["full_name"] for m in db.fetch_all("members")}
    for e in events:
        e["actor_name"] = names.get(e.get("actor_id")) or ("System" if not e.get("actor_id") else None)
    return events


@router.get("/queue", tags=["Queue"])
def review_queue(band: Optional[Literal["High", "Medium", "Low"]] = None, institution_id: Optional[str] = None,
                 finding_type: Optional[str] = None, workflow_status: Optional[str] = None,
                 user: AuthenticatedUser = Depends(require_role(READERS))):
    """Submitted applications ordered by review priority (build spec 7.4), highest first, then the
    earliest review deadline. Each row carries the score's composition."""
    apps, institutions, findings, weights, runs, as_of = parallel(
        lambda: db.table("applications").select("*").neq("workflow_status", "draft").execute().data or [],
        lambda: db.table("institutions").select("id,code,name,city").execute().data or [],
        lambda: db.table("findings").select("application_id,finding_type,status,is_cross_institution")
                  .in_("status", list(casefile.UNRESOLVED_STATUSES)).execute().data or [],
        lambda: {w["key"]: w["weight"] for w in db.fetch_all("priority_weights")},
        lambda: db.table("validation_runs").select("application_id,started_at").eq("mode", "full").execute().data or [],
        as_of_date,
    )
    institutions = {i["id"]: i for i in institutions}
    by_app: dict[str, list[dict]] = {}
    for f in findings:
        by_app.setdefault(f["application_id"], []).append(f)
    last_run: dict[str, str] = {}
    for r in runs:
        if (r.get("started_at") or "") >= last_run.get(r["application_id"], ""):
            last_run[r["application_id"]] = r.get("started_at") or ""

    rows = []
    for a in apps:
        open_ = by_app.get(a["id"], [])
        score = priority_service.compute(open_, weights, a.get("review_deadline"), as_of)
        types = sorted({f["finding_type"] for f in open_})
        row = {
            "application": {k: a.get(k) for k in ("id", "code", "category", "academic_year", "workflow_status",
                                                   "submitted_at", "review_deadline")},
            "institution": institutions.get(a["institution_id"], {}),
            "priority": score, "finding_types": types,
            "cross_flags": sum(1 for f in open_ if f["is_cross_institution"]),
            "last_run_at": last_run.get(a["id"]),
        }
        if band and score["band"] != band:
            continue
        if institution_id and a["institution_id"] != institution_id:
            continue
        if finding_type and finding_type not in types:
            continue
        if workflow_status and a["workflow_status"] != workflow_status:
            continue
        rows.append(row)
    rows.sort(key=lambda r: (-r["priority"]["score"], r["application"].get("review_deadline") or "9999", r["application"]["code"]))
    return rows


@router.get("/cross", tags=["Queue"])
def cross_flags(user: AuthenticatedUser = Depends(require_role(READERS))):
    """Every unresolved cross-institution flag with both applications. Titles carry masked IDs, not names
    (build spec 8, privacy); names are on the case page."""
    findings = (db.table("findings").select("id,finding_key,finding_type,title,status,application_id,related_application_id,created_at")
                .eq("is_cross_institution", True).in_("status", list(casefile.UNRESOLVED_STATUSES)).execute().data or [])
    if not findings:
        return []
    ids = list({f["application_id"] for f in findings} | {f["related_application_id"] for f in findings if f.get("related_application_id")})
    apps, institutions = parallel(
        lambda: db.table("applications").select("id,code,institution_id,workflow_status").in_("id", ids).execute().data or [],
        lambda: db.table("institutions").select("id,code,name,city").execute().data or [],
    )
    institutions = {i["id"]: i for i in institutions}
    apps = {a["id"]: {**a, "institution": institutions.get(a["institution_id"], {})} for a in apps}
    out = [{**f, "application": apps.get(f["application_id"]), "related_application": apps.get(f.get("related_application_id"))}
           for f in findings]
    out.sort(key=lambda f: (f["finding_type"], f["finding_key"]))
    return out
