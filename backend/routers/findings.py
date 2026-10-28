"""Validation, statuses, priority, findings, reviewer actions, the Case File and the audit log (build spec 11)."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.access import application_for
from core.db import db, parallel
from core.security import AuthenticatedUser, require_role
from services import audit, casefile, reviews
from services.validation import run_validation

router = APIRouter(tags=["Findings"])

REVIEWER = ["reviewer"]
READERS = ["reviewer", "rule_admin"]

# What an institution may see of its own application's audit trail: its own steps and the requests
# made to it. Validation runs are left out, since their details name findings it does not see.
INSTITUTION_EVENTS = {"application_created", "application_seeded", "application_submitted", "document_upload_started",
                      "document_finalized", "document_processed", "document_processing_failed",
                      "finding_request_evidence"}


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


@router.get("/applications/{application_id}/statuses")
def get_statuses(application_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    return casefile.status_view(application_for(user, application_id))


@router.get("/applications/{application_id}/priority")
def get_priority(application_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    return casefile.priority_view(application_for(user, application_id))


@router.get("/applications/{application_id}/findings")
def list_findings(application_id: str,
                        user: AuthenticatedUser = Depends(require_role(["institution", "reviewer", "rule_admin"]))):
    application_for(user, application_id)
    return casefile.findings_for(application_id, institution_view=user.role == "institution")


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
