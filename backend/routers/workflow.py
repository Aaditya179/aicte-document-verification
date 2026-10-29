"""
The review workflow around findings (build spec 11): the room table, confirming or correcting a value a
reviewer was asked about, evidence requests and their fulfilment, and in-app notifications.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from core.access import EDITABLE_STATES, application_for, document_for
from core.db import db, parallel
from core.security import AuthenticatedUser, require_role
from schemas import FieldConfirm, FieldCorrect, Fulfil, RoomTable
from services import audit, normalise
from services.validation import has_full_run, run_validation

router = APIRouter(tags=["Workflow"])

ANY_ROLE = ["institution", "reviewer", "rule_admin"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notify(user_ids: list[str], kind: str, application: dict, message: str) -> None:
    rows = [{"user_id": u, "kind": kind, "ref_type": "application", "ref_id": application["id"], "message": message}
            for u in dict.fromkeys(user_ids) if u]
    if rows:
        db.table("notifications").insert(rows).execute()


# ------------------------------------------------------------------------------------------------
# Room table (check C11)
# ------------------------------------------------------------------------------------------------

def _room_view(application: dict) -> dict:
    rooms = db.table("rooms").select("*").eq("application_id", application["id"]).order("room_label").execute().data or []
    total = sum((Decimal(str(r["area_sqm"])) for r in rooms if r.get("area_sqm") is not None), Decimal(0))
    return {"rooms": rooms, "total_sqm": float(total), "declared_total_area_sqm": application.get("declared_total_area_sqm")}


@router.get("/applications/{application_id}/rooms")
def get_rooms(application_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    return _room_view(application_for(user, application_id))


@router.post("/applications/{application_id}/rooms")
def save_rooms(application_id: str, body: RoomTable,
               user: AuthenticatedUser = Depends(require_role(["institution", "reviewer"]))):
    """Replace the room table. An institution may change it while it can change documents; a reviewer
    may enter it from the floor plan at any time."""
    application = application_for(user, application_id)
    if user.role == "institution" and application["workflow_status"] not in EDITABLE_STATES:
        raise HTTPException(status_code=409, detail="This application has been submitted; the room table can no longer be changed")
    if body.floor_plan_document_id:
        plan, plan_app = document_for(user, body.floor_plan_document_id)
        if plan_app["id"] != application_id or plan["doc_type"] != "floor_plan":
            raise HTTPException(status_code=422, detail="Choose a floor plan of this application")
    db.table("rooms").delete().eq("application_id", application_id).execute()
    if body.rooms:
        db.table("rooms").insert([{**r.model_dump(), "application_id": application_id,
                                   "floor_plan_document_id": body.floor_plan_document_id} for r in body.rooms]).execute()
    view = _room_view(application)
    audit.record(user, "rooms_saved", "application", application_id, application_id,
                 {"rooms": len(body.rooms), "total_sqm": view["total_sqm"]})
    return view


# ------------------------------------------------------------------------------------------------
# Confirming or correcting a value (check C5)
# ------------------------------------------------------------------------------------------------

def _field_for(user: AuthenticatedUser, field_id: str) -> tuple[dict, dict, dict]:
    field = db.fetch_one("extracted_fields", id=field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Value not found")
    document, application = document_for(user, field["document_id"])
    return field, document, application


def _after_review(user: AuthenticatedUser, application: dict) -> dict | None:
    """A confirmed or corrected value can close a finding or open a new conflict, so the application is
    validated again straight away if it has been validated before."""
    if application["workflow_status"] == "draft" or not has_full_run(application["id"]):
        return None
    return run_validation(application["id"], "full", user, trigger="value_confirmed")["summary"]


@router.post("/fields/{field_id}/confirm")
def confirm_field(field_id: str, body: FieldConfirm, user: AuthenticatedUser = Depends(require_role(["reviewer"]))):
    """The value as read is right. For an ambiguous date, the day-first reading shown is the one confirmed."""
    field, document, application = _field_for(user, field_id)
    if field.get("field_value") is None:
        raise HTTPException(status_code=409, detail="No value was read, so there is nothing to confirm. Correct it instead")
    updated = db.update("extracted_fields", field_id, {"review_state": "confirmed", "reviewed_by": user.id, "reviewed_at": _now()})
    db.insert("review_actions", {"field_id": field_id, "actor_id": user.id, "actor_role": user.role,
                                 "action": "confirm_field", "reason": body.reason.strip()})
    audit.record(user, "field_confirmed", "extracted_field", field_id, application["id"],
                 {"document_id": document["id"], "field": field["field_name"], "value": field["field_value"],
                  "reason": body.reason.strip()})
    return {"field": updated, "validation": _after_review(user, application)}


@router.post("/fields/{field_id}/correct")
def correct_field(field_id: str, body: FieldCorrect, user: AuthenticatedUser = Depends(require_role(["reviewer"]))):
    """Replace the value the checks compare. The value as printed in the document (original_value) is kept."""
    field, document, application = _field_for(user, field_id)
    parsed = normalise.normalise(field.get("value_type") or "text", body.value)
    if parsed.value is None:
        raise HTTPException(status_code=422, detail=parsed.note or "The value could not be read")
    if parsed.ambiguous:
        raise HTTPException(status_code=422, detail=f"{parsed.note}. Give the month in words, for example 3 August 2025")
    updated = db.update("extracted_fields", field_id, {
        "field_value": parsed.value, "review_state": "corrected", "review_reason": None,
        "reviewed_by": user.id, "reviewed_at": _now(),
    })
    db.insert("review_actions", {"field_id": field_id, "actor_id": user.id, "actor_role": user.role,
                                 "action": "correct_field", "reason": body.reason.strip()})
    audit.record(user, "field_corrected", "extracted_field", field_id, application["id"],
                 {"document_id": document["id"], "field": field["field_name"], "original_value": field.get("original_value"),
                  "from": field.get("field_value"), "to": parsed.value, "reason": body.reason.strip()})
    return {"field": updated, "validation": _after_review(user, application)}


# ------------------------------------------------------------------------------------------------
# Evidence requests
# ------------------------------------------------------------------------------------------------

@router.get("/evidence-requests")
def list_evidence_requests(application_id: str | None = None,
                           user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    """An institution sees the requests made to it; reviewers and rule admins see all of them. Open
    requests first, then the most recent."""
    query = db.table("evidence_requests").select("*")
    if application_id:
        application_for(user, application_id)
        query = query.eq("application_id", application_id)
    elif user.role == "institution":
        own = [a["id"] for a in db.table("applications").select("id").eq("institution_id", user.institution_id).execute().data or []]
        if not own:
            return []
        query = query.in_("application_id", own)
    requests = query.execute().data or []
    if not requests:
        return []
    findings, apps = parallel(
        lambda: db.table("findings").select("id,title,finding_type,status,is_cross_institution")
                  .in_("id", list({r["finding_id"] for r in requests if r.get("finding_id")})).execute().data or [],
        lambda: db.table("applications").select("id,code,workflow_status")
                  .in_("id", list({r["application_id"] for r in requests})).execute().data or [],
    )
    findings, apps = {f["id"]: f for f in findings}, {a["id"]: a for a in apps}
    out = []
    for r in requests:
        f = findings.get(r.get("finding_id"), {})
        if user.role == "institution" and f.get("is_cross_institution"):
            continue                                  # never happens (refused at request time), kept as a guard
        out.append({**r, "finding": {k: f.get(k) for k in ("id", "title", "finding_type", "status")},
                    "application": apps.get(r["application_id"], {})})
    out.sort(key=lambda r: (r["status"] != "open", r.get("due_date") or "", r["created_at"]))
    return out


@router.post("/evidence-requests/{request_id}/fulfil")
def fulfil_evidence_request(request_id: str, body: Fulfil, user: AuthenticatedUser = Depends(require_role(["institution"]))):
    """The institution answers a request, with a note and, usually, the replacement document it uploaded.
    The finding goes back to the reviewer (open), and when no request is left open the application
    returns to review."""
    request = db.fetch_one("evidence_requests", id=request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    application = application_for(user, request["application_id"])
    if request["status"] != "open":
        raise HTTPException(status_code=409, detail="This request has already been answered")
    document = None
    if body.document_id:
        document, doc_app = document_for(user, body.document_id)
        if doc_app["id"] != application["id"] or document["status"] != "current" or document["integrity_status"] != "passed":
            raise HTTPException(status_code=422, detail="Choose a current document of this application that passed the file check")

    db.update("evidence_requests", request_id, {"status": "fulfilled", "fulfilled_by_document_id": body.document_id})
    finding = db.fetch_one("findings", id=request["finding_id"]) if request.get("finding_id") else None
    if finding and finding["status"] == "evidence_requested":
        db.update("findings", finding["id"], {"status": "open"})
    still_open = db.table("evidence_requests").select("id").eq("application_id", application["id"]).eq("status", "open").execute().data
    if not still_open and application["workflow_status"] == "awaiting_institution":
        db.update("applications", application["id"], {"workflow_status": "under_review"})

    title = finding["title"] if finding else "a finding"
    reviewers = [request.get("requested_by")] if request.get("requested_by") else [m["user_id"] for m in db.fetch_all("members", role="reviewer")]
    _notify(reviewers, "evidence_fulfilled", application,
            f"{application['code']} answered the request on {title}" + (f" with {document['original_name']}" if document else "") + ".")
    audit.record(user, "evidence_request_fulfilled", "evidence_request", request_id, application["id"], {
        "finding_id": request.get("finding_id"), "document_id": body.document_id, "note": body.note.strip(),
        "workflow_status": "under_review" if not still_open else application["workflow_status"],
    })
    return db.fetch_one("evidence_requests", id=request_id)


# ------------------------------------------------------------------------------------------------
# Notifications (polled; CLAUDE.md, assumption D4)
# ------------------------------------------------------------------------------------------------

@router.get("/notifications")
def list_notifications(user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    items, unread = parallel(
        lambda: db.table("notifications").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(30).execute().data or [],
        lambda: db.table("notifications").select("id").eq("user_id", user.id).is_("read_at", "null").execute().data or [],
    )
    return {"items": items, "unread": len(unread)}


@router.post("/notifications/read-all")
def read_all(user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    db.table("notifications").update({"read_at": _now()}).eq("user_id", user.id).is_("read_at", "null").execute()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
def read_one(notification_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    note = db.fetch_one("notifications", id=notification_id)
    if not note or note["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    return db.update("notifications", notification_id, {"read_at": _now()})
