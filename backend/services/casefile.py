"""
Everything a reviewer sees about one application: findings with their evidence and the actions taken on
them, the four statuses, the priority composition, and the Case File (build spec 7.3, 7.4, 12).
"""
from typing import Optional

from core.clock import as_of_date
from core.db import db, parallel
from services import priority, statuses

DISCLAIMERS = [
    "Decision support only. This report does not approve, reject or declare any institution at fault. "
    "The final decision rests with the competent authority.",
    "All data in this report is synthetic. Rules shown are illustrative, not official AICTE rules. "
    "The issuer-registry check is a MOCK.",
]
FINAL_DECISION = "Final decision: Pending (authorised AICTE official)"

ACTION_LABEL = {
    "resolve": "Resolved", "dismiss": "Dismissed", "request_evidence": "Asked the institution for evidence",
    "confirm_field": "Confirmed a value", "correct_field": "Corrected a value",
}


def _in(table: str, column: str, values: list, select: str = "*") -> list[dict]:
    if not values:
        return []
    return db.table(table).select(select).in_(column, values).execute().data or []


def findings_for(application_id: str, *, institution_view: bool = False) -> list[dict]:
    """Findings with evidence, reviewer actions and evidence requests. The institution sees only the
    findings a reviewer has asked it about, and never a cross-institution one."""
    rows = db.table("findings").select("*").eq("application_id", application_id).order("created_at").execute().data or []
    if institution_view:
        rows = [f for f in rows if f["status"] == "evidence_requested" and not f["is_cross_institution"]]
    ids = [f["id"] for f in rows]
    evidence, actions, requests = parallel(*(lambda t=t: _in(t, "finding_id", ids)
                                             for t in ("finding_evidence", "review_actions", "evidence_requests")))

    doc_ids = list({e["document_id"] for e in evidence if e.get("document_id")})
    actor_ids = list({a["actor_id"] for a in actions if a.get("actor_id")})
    doc_rows, member_rows = parallel(lambda: _in("documents", "id", doc_ids, "id,doc_type,original_name,version,status,mime"),
                                     lambda: _in("members", "user_id", actor_ids, "user_id,full_name,role"))
    docs = {d["id"]: d for d in doc_rows}
    members = {m["user_id"]: m for m in member_rows}

    out = []
    for f in rows:
        ev = sorted([e for e in evidence if e["finding_id"] == f["id"]], key=lambda e: e.get("role") or "")
        for e in ev:
            d = docs.get(e.get("document_id"))
            e["document"] = {k: d.get(k) for k in ("doc_type", "original_name", "version", "status", "mime")} if d else None
        acts = sorted([a for a in actions if a["finding_id"] == f["id"]], key=lambda a: a["created_at"])
        for a in acts:
            a["actor_name"] = members.get(a.get("actor_id"), {}).get("full_name")
            a["action_label"] = ACTION_LABEL.get(a["action"], a["action"])
        item = {**f, "evidence": ev, "actions": [] if institution_view else acts,
                "evidence_requests": sorted([r for r in requests if r["finding_id"] == f["id"]], key=lambda r: r["created_at"])}
        out.append(item)
    return out


def latest_run(application_id: str) -> Optional[dict]:
    runs = (db.table("validation_runs").select("*").eq("application_id", application_id).eq("mode", "full")
            .order("started_at", desc=True).limit(1).execute().data or [])
    return runs[0] if runs else None


def status_view(application: dict, findings: Optional[list[dict]] = None) -> dict:
    def documents_and_children():
        docs = (db.table("documents").select("*").eq("application_id", application["id"])
                .eq("status", "current").execute().data or [])
        ids = [d["id"] for d in docs]
        field_rows, checks = parallel(lambda: _in("extracted_fields", "document_id", ids),
                                      lambda: _in("verification_checks", "document_id", ids))
        return docs, field_rows, checks

    run, found, (documents, field_rows, checks), templates = parallel(
        lambda: latest_run(application["id"]),
        lambda: findings if findings is not None else db.fetch_all("findings", application_id=application["id"]),
        documents_and_children,
        lambda: db.table("extraction_templates").select("doc_type,field_name").eq("required", True).execute().data or [],
    )
    findings = found
    doc_type = {d["id"]: d["doc_type"] for d in documents}
    fields = [{**f, "doc_type": doc_type[f["document_id"]]} for f in field_rows]
    required = {(t["doc_type"], t["field_name"]) for t in templates}
    return {**statuses.compute(run is not None, findings, documents, fields, required, checks),
            "last_run": {k: run.get(k) for k in ("id", "started_at", "as_of_date", "rule_versions", "summary")} if run else None}


def priority_view(application: dict, findings: Optional[list[dict]] = None) -> dict:
    found, weights, as_of = parallel(
        lambda: findings if findings is not None else db.fetch_all("findings", application_id=application["id"]),
        lambda: {w["key"]: w["weight"] for w in db.fetch_all("priority_weights")},
        as_of_date,
    )
    return priority.compute(found, weights, application.get("review_deadline"), as_of)


def case_file(application: dict) -> dict:
    """The printable record of where a review stands (build spec section 12, Case File content)."""
    def documents_and_checks():
        docs = db.table("documents").select("*").eq("application_id", application["id"]).order("uploaded_at").execute().data or []
        return docs, _in("verification_checks", "document_id", [d["id"] for d in docs])

    institution, findings, (documents, checks), types, run = parallel(
        lambda: db.fetch_one("institutions", id=application["institution_id"]) or {},
        lambda: findings_for(application["id"]),
        documents_and_checks,
        lambda: {t["code"]: t["label"] for t in db.fetch_all("document_types")},
        lambda: latest_run(application["id"]),
    )
    rules = []
    if run and run.get("rule_versions"):
        all_rules = _in("rules", "rule_code", list(run["rule_versions"]), "rule_code,version,title,note")
        rules = [r for r in all_rules if run["rule_versions"].get(r["rule_code"]) == r["version"]]
        rules.sort(key=lambda r: r["rule_code"])

    status, prio = parallel(lambda: status_view(application, findings), lambda: priority_view(application, findings))
    actions = [{**a, "finding_title": f["title"], "finding_key": f["finding_key"]} for f in findings for a in f["actions"]]
    return {
        "application": {k: application.get(k) for k in ("id", "code", "category", "academic_year", "workflow_status",
                                                         "submitted_at", "review_deadline", "declared_total_area_sqm")},
        "institution": {k: institution.get(k) for k in ("code", "name", "city", "is_fictional")},
        "statuses": status,
        "priority": prio,
        "findings": findings,
        "documents": [{
            "id": d["id"], "doc_type": d["doc_type"], "label": types.get(d["doc_type"], d["doc_type"]),
            "original_name": d.get("original_name"), "version": d.get("version"), "status": d.get("status"),
            "sha256": d.get("sha256"), "integrity_status": d.get("integrity_status"), "integrity_note": d.get("integrity_note"),
            "uploaded_at": d.get("uploaded_at"),
            "verification": [{k: c.get(k) for k in ("method", "status", "source", "is_mock", "checked_at")}
                             for c in checks if c["document_id"] == d["id"]],
        } for d in documents],
        "reviewer_actions": sorted(actions, key=lambda a: a["created_at"]),
        "latest_run": {k: run.get(k) for k in ("id", "started_at", "as_of_date", "summary")} if run else None,
        "rule_versions": rules,
        "final_decision": FINAL_DECISION,
        "disclaimers": DISCLAIMERS,
    }
