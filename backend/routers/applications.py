"""Applications: create, list, open and submit (build spec section 11)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.access import application_for
from core.clock import as_of_date
from core.db import db
from core.security import AuthenticatedUser, require_role
from schemas import ApplicationCreate
from services import audit

router = APIRouter(prefix="/applications", tags=["Applications"])

ANY_ROLE = ["institution", "reviewer", "rule_admin"]
REVIEW_DAYS = 30

# Fields of a document that the browser sees; the storage path stays on the server
DOCUMENT_FIELDS = ("id", "application_id", "doc_type", "version", "supersedes_id", "status", "original_name", "mime",
                   "size_bytes", "page_count", "sha256", "integrity_status", "integrity_note", "processing_status",
                   "processing_note", "uploaded_at")


def public_document(document: dict, category: str | None = None) -> dict:
    out = {k: document.get(k) for k in DOCUMENT_FIELDS}
    out["photo_category"] = category
    return out


def _documents_of(application_ids: list[str]) -> list[dict]:
    if not application_ids:
        return []
    return (db.table("documents").select("*").in_("application_id", application_ids)
            .order("uploaded_at", desc=True).execute().data or [])


@router.get("")
async def list_applications(user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    query = db.table("applications").select("*").order("created_at", desc=True)
    if user.role == "institution":
        query = query.eq("institution_id", user.institution_id)
    applications = query.execute().data or []

    institutions = {i["id"]: i for i in db.fetch_all("institutions")}
    documents = _documents_of([a["id"] for a in applications])
    out = []
    for a in applications:
        current = [d for d in documents if d["application_id"] == a["id"] and d["status"] == "current"]
        out.append({
            **a,
            "institution": {k: institutions.get(a["institution_id"], {}).get(k) for k in ("code", "name", "city")},
            "documents": {
                "current": len(current),
                "failed_check": sum(d["integrity_status"] == "failed" for d in current),
                "being_read": sum(d["processing_status"] in ("pending", "processing") and d["integrity_status"] != "failed"
                                  for d in current),
            },
        })
    return out


@router.post("", status_code=201)
async def create_application(body: ApplicationCreate, user: AuthenticatedUser = Depends(require_role(["institution"]))):
    institution = db.fetch_one("institutions", id=user.institution_id)
    if not institution:
        raise HTTPException(status_code=409, detail="Your account is not linked to an institution")
    taken = {a["code"] for a in db.table("applications").select("code").eq("institution_id", institution["id"])
             .eq("academic_year", body.academic_year).execute().data or []}
    n = 1
    while f"{institution['code']}-{body.academic_year}-{n:02d}" in taken:
        n += 1
    application = db.insert("applications", {
        "code": f"{institution['code']}-{body.academic_year}-{n:02d}",
        "institution_id": institution["id"], "category": body.category, "academic_year": body.academic_year,
        "declared_total_area_sqm": body.declared_total_area_sqm, "created_by": user.id,
    })
    audit.record(user, "application_created", "application", application["id"], application["id"],
                 {"code": application["code"], "category": body.category, "academic_year": body.academic_year})
    return application


@router.get("/{application_id}")
async def get_application(application_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    application = application_for(user, application_id)
    institution = db.fetch_one("institutions", id=application["institution_id"]) or {}
    documents = _documents_of([application_id])
    media = {}
    if documents:
        media = {m["document_id"]: m for m in db.table("media_assets").select("document_id,category")
                 .in_("document_id", [d["id"] for d in documents]).execute().data or []}

    types = {t["code"]: t for t in db.fetch_all("document_types")}
    required = db.fetch_all("required_documents", category=application["category"])
    current_ok = [d for d in documents if d["status"] == "current" and d["integrity_status"] == "passed"]
    checklist = []
    for r in sorted(required, key=lambda r: list(types).index(r["doc_type"]) if r["doc_type"] in types else 99):
        present = [d for d in current_ok if d["doc_type"] == r["doc_type"]]
        checklist.append({
            "doc_type": r["doc_type"], "label": types.get(r["doc_type"], {}).get("label", r["doc_type"]),
            "mandatory": r["mandatory"], "present": bool(present),
        })

    return {
        "application": application,
        "institution": {k: institution.get(k) for k in ("id", "code", "name", "city", "is_fictional")},
        "documents": [public_document(d, media.get(d["id"], {}).get("category")) for d in documents],
        "checklist": checklist,
        "photo_categories": sorted({media[d["id"]]["category"] for d in current_ok if d["id"] in media and media[d["id"]]["category"]}),
    }


@router.post("/{application_id}/submit")
async def submit_application(application_id: str, user: AuthenticatedUser = Depends(require_role(["institution"]))):
    application = application_for(user, application_id)
    if application["workflow_status"] != "draft":
        raise HTTPException(status_code=409, detail="Only a draft application can be submitted")
    documents = [d for d in _documents_of([application_id]) if d["status"] == "current"]
    if not documents:
        raise HTTPException(status_code=409, detail="Upload at least one document before submitting")
    if any(d["processing_status"] in ("pending", "processing") and d["integrity_status"] != "failed" for d in documents):
        raise HTTPException(status_code=409, detail="Wait until every document has been read, then submit")

    deadline = as_of_date() + timedelta(days=REVIEW_DAYS)
    updated = db.update("applications", application_id, {
        "workflow_status": "submitted", "submitted_at": datetime.now(timezone.utc).isoformat(),
        "review_deadline": deadline.isoformat(),
    })
    reviewers = db.fetch_all("members", role="reviewer")
    if reviewers:
        db.table("notifications").insert([{
            "user_id": r["user_id"], "kind": "application_submitted", "ref_type": "application", "ref_id": application_id,
            "message": f"{application['code']} was submitted for review",
        } for r in reviewers]).execute()
    audit.record(user, "application_submitted", "application", application_id, application_id,
                 {"code": application["code"], "review_deadline": deadline.isoformat()})
    return updated
