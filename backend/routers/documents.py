"""Documents: signed upload, file check, status, viewing and the values read from them (build spec 6 and 11)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from core.access import application_for, document_for, require_editable
from core.config import settings
from core.db import db
from core.ratelimit import rate_limit
from core.security import AuthenticatedUser, require_role
from routers.applications import public_document
from schemas import UploadInit
from services import pipeline

router = APIRouter(tags=["Documents"])

ANY_ROLE = ["institution", "reviewer", "rule_admin"]
READ_ALL = ["reviewer", "rule_admin"]
UPLOAD_LIMIT = Depends(rate_limit("30/minute", "upload"))


@router.post("/applications/{application_id}/documents/init", status_code=201, dependencies=[UPLOAD_LIMIT])
def init_upload(application_id: str, body: UploadInit,
                      user: AuthenticatedUser = Depends(require_role(["institution"]))):
    application = application_for(user, application_id)
    require_editable(application)
    doc_type = db.fetch_one("document_types", code=body.doc_type)
    if not doc_type:
        raise HTTPException(status_code=422, detail=f"Unknown document type {body.doc_type}")
    problem = pipeline.check_upload_metadata(doc_type, body.filename, body.mime, body.size, body.category)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    result = pipeline.init_upload(user, application, doc_type, body.filename, body.mime, body.size, body.category)
    return {"document": public_document(result["document"], body.category), "upload": result["upload"]}


@router.post("/documents/{document_id}/finalize", dependencies=[UPLOAD_LIMIT])
def finalize_upload(document_id: str, background: BackgroundTasks,
                          user: AuthenticatedUser = Depends(require_role(["institution"]))):
    document, _ = document_for(user, document_id)
    try:
        updated, read_next = pipeline.finalize(user, document)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if read_next:
        background.add_task(pipeline.process_document, document_id)
    media = db.fetch_one("media_assets", document_id=document_id)
    return public_document(updated, media["category"] if media else None)


@router.get("/documents/{document_id}")
def get_document(document_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    document, application = document_for(user, document_id)
    media = db.fetch_one("media_assets", document_id=document_id)
    out = public_document(document, media["category"] if media else None)
    out["application_code"] = application["code"]
    if media and user.role in READ_ALL:
        out["photo"] = {k: media.get(k) for k in ("phash", "width", "height", "taken_at", "gps", "exif")}
    return out


@router.get("/documents/{document_id}/signed-url")
def document_link(document_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    """A short-lived link to view the file. The bucket is private; links expire after a few minutes."""
    document, _ = document_for(user, document_id)
    if document["integrity_status"] == "pending":
        raise HTTPException(status_code=409, detail="The file has not been checked yet")
    signed = db.storage.create_signed_url(document["storage_path"], settings.SIGNED_LINK_TTL_SECONDS)
    url = signed.get("signedURL") or signed.get("signedUrl")
    if not url:
        raise HTTPException(status_code=502, detail="Could not create a viewing link, try again")
    return {"url": url, "expires_in": settings.SIGNED_LINK_TTL_SECONDS, "mime": document["mime"]}


# What an institution sees of the values read from its own documents: the reading, not the review
INSTITUTION_FIELD_KEYS = ("id", "field_name", "original_value", "value_type", "page_number", "source_method",
                          "confidence", "review_state", "review_reason")


@router.get("/documents/{document_id}/fields")
def document_fields(document_id: str, user: AuthenticatedUser = Depends(require_role(ANY_ROLE))):
    """The values read from the document, each with its page, how it was read and whether it needs confirming.
    An institution sees this for its own documents, so it can tell at upload whether a file read well."""
    document, _ = document_for(user, document_id)
    fields = db.table("extracted_fields").select("*").eq("document_id", document_id).order("field_name").execute().data or []
    faculty = []
    if document["doc_type"] == "faculty_list":
        faculty = db.table("faculty").select("*").eq("document_id", document_id).order("faculty_code").execute().data or []
    if user.role == "institution":
        fields = [{k: f.get(k) for k in INSTITUTION_FIELD_KEYS} for f in fields]
        for f in fields:                              # a reviewer's confirmation or correction stays on their side
            if f["review_state"] in ("confirmed", "corrected"):
                f["review_state"] = "auto"
    return {"fields": fields, "faculty": faculty}
