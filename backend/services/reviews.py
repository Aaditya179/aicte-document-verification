"""
A reviewer's action on a finding: resolve, dismiss, or ask the institution for evidence. Every action
needs a reason, is stored in review_actions and is written to the audit trail. None of them touches the
administrative decision, which stays with the authorised AICTE official.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException

from core.clock import as_of_date
from core.db import db
from core.security import AuthenticatedUser
from services import audit

NEW_STATUS = {"resolve": "resolved", "dismiss": "dismissed", "request_evidence": "evidence_requested"}
ACTIONABLE = ("open", "evidence_requested")
EVIDENCE_DAYS = 7


def act(user: AuthenticatedUser, finding: dict, application: dict, action: str, reason: str,
        due_date: Optional[date] = None) -> dict:
    reason = reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Give a reason for this action")
    if finding["status"] not in ACTIONABLE:
        raise HTTPException(status_code=409, detail=f"This finding is already {finding['status'].replace('_', ' ')}")
    if action == "request_evidence" and finding["status"] == "evidence_requested":
        raise HTTPException(status_code=409, detail="Evidence has already been requested for this finding")
    if action == "request_evidence" and finding["is_cross_institution"]:
        # The institution must never learn about another institution's records
        raise HTTPException(status_code=409, detail="Evidence cannot be requested for a cross-institution flag")

    before = finding["status"]
    updated = db.update("findings", finding["id"], {"status": NEW_STATUS[action]})
    db.insert("review_actions", {"finding_id": finding["id"], "actor_id": user.id, "actor_role": user.role,
                                 "action": action, "reason": reason})
    detail = {"finding_key": finding["finding_key"], "from": before, "to": NEW_STATUS[action], "reason": reason}

    if action == "request_evidence":
        due = due_date or (as_of_date() + timedelta(days=EVIDENCE_DAYS))
        request = db.insert("evidence_requests", {
            "finding_id": finding["id"], "application_id": application["id"], "requested_by": user.id,
            "message": reason, "due_date": due.isoformat(), "status": "open",
        })
        db.update("applications", application["id"], {"workflow_status": "awaiting_institution"})
        people = db.fetch_all("members", institution_id=application["institution_id"])
        if people:
            db.table("notifications").insert([{
                "user_id": p["user_id"], "kind": "evidence_requested", "ref_type": "application", "ref_id": application["id"],
                "message": f"A reviewer asked for evidence on {application['code']}: {finding['title']}. Due {due:%d/%m/%Y}.",
            } for p in people]).execute()
        detail.update({"evidence_request_id": request["id"], "due_date": due.isoformat()})

    audit.record(user, f"finding_{action}", "finding", finding["id"], application["id"], detail)
    return updated
