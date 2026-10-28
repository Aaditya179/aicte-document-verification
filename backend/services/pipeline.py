"""
Upload pipeline (build spec section 6).

1. init: the API checks the name, type and size, creates the document row and returns a signed
   upload URL for {institution_id}/{application_id}/{document_id}-{safe_filename}.
2. The browser uploads the file straight to storage.
3. finalize: the API downloads the file, checks its first bytes against the claimed type, the size and
   the page limit, stores its SHA-256 and the file check result, and starts reading it in the background.
   A file that fails the check is kept for the record but never read or validated.
4. Reading (process_document): text, fields, faculty and photo data, then processing_status = done.

Versions: a document that passes the check replaces the current document of the same type (for photos,
the same type and evidence category). It becomes version + 1 and the old one is marked superseded.
"""
import hashlib
import logging
import re
import uuid
from typing import Optional

from core.config import settings
from core.db import db
from core.security import AuthenticatedUser
from services import audit, extraction, forensics

logger = logging.getLogger("proofpath.pipeline")

PHOTO_CATEGORIES = {"lab", "classroom", "library", "other"}


def safe_filename(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.") or "file"
    stem, dot, ext = base.rpartition(".")
    return (stem[:80] + dot + ext.lower()) if dot else base[:80]


def storage_path(application: dict, document_id: str, filename: str) -> str:
    return f"{application['institution_id']}/{application['id']}/{document_id}-{safe_filename(filename)}"


def check_upload_metadata(doc_type: dict, filename: str, mime: str, size: int, category: Optional[str]) -> Optional[str]:
    """Why this upload is refused before any bytes are sent, or None."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in extraction.EXTENSIONS:
        return "Upload a PDF, JPEG or PNG file"
    if mime not in extraction.ALLOWED_MIME or extraction.EXTENSIONS[ext] != mime:
        return f"The file type {mime or 'unknown'} does not match the file name {filename}"
    if size <= 0:
        return "The file is empty"
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        return f"The file is larger than {settings.MAX_UPLOAD_MB} MB"
    if doc_type["is_photo"]:
        if mime == extraction.MIME_PDF:
            return "Upload the photo as a JPEG or PNG image"
        if category not in PHOTO_CATEGORIES:
            return "Choose what the photo shows: lab, classroom, library or other"
    elif category:
        return "Only photos take an evidence category"
    return None


def init_upload(user: AuthenticatedUser, application: dict, doc_type: dict, filename: str, mime: str,
                size: int, category: Optional[str]) -> dict:
    document_id = str(uuid.uuid4())
    path = storage_path(application, document_id, filename)
    document = db.insert("documents", {
        "id": document_id, "application_id": application["id"], "doc_type": doc_type["code"],
        "storage_path": path, "original_name": filename[:200], "mime": mime, "size_bytes": size,
        "uploaded_by": user.id, "version": 1, "status": "current",
        "integrity_status": "pending", "processing_status": "pending",
    })
    if doc_type["is_photo"]:
        db.insert("media_assets", {"document_id": document_id, "category": category})
    signed = db.storage.create_signed_upload_url(path)
    audit.record(user, "document_upload_started", "document", document_id, application["id"],
                 {"doc_type": doc_type["code"], "file": filename, "size_bytes": size})
    return {"document": document, "upload": {"path": path, "token": signed["token"], "signed_url": signed["signed_url"]}}


def _integrity(document: dict, data: bytes) -> tuple[str, Optional[str], Optional[int]]:
    """(passed or failed, why it failed, page count)."""
    actual = extraction.sniff_mime(data)
    if actual is None:
        return "failed", "The file is not a PDF, JPEG or PNG, whatever its name says", None
    if actual != document["mime"]:
        return "failed", f"The file says it is {document['mime']} but its content is {actual}", None
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        return "failed", f"The file is larger than {settings.MAX_UPLOAD_MB} MB", None
    try:
        pages = extraction.page_count(data, actual)
    except extraction.UnreadableFile as exc:
        return "failed", str(exc), None
    if pages > settings.MAX_PAGES:
        return "failed", f"The file has {pages} pages; the limit is {settings.MAX_PAGES}", pages
    return "passed", None, pages


def _supersede(document: dict) -> dict:
    """Make this document the current version of its type (and photo category) in the application."""
    current = (db.table("documents").select("id,version").eq("application_id", document["application_id"])
               .eq("doc_type", document["doc_type"]).eq("status", "current").eq("integrity_status", "passed")
               .neq("id", document["id"]).execute().data or [])
    if not current:
        return {}
    media = db.fetch_one("media_assets", document_id=document["id"])
    if media:
        same_category = {m["document_id"] for m in db.table("media_assets").select("document_id,category")
                         .in_("document_id", [c["id"] for c in current]).execute().data or []
                         if m["category"] == media["category"]}
        current = [c for c in current if c["id"] in same_category]
        if not current:
            return {}
    previous = max(current, key=lambda c: c["version"])
    for c in current:
        db.update("documents", c["id"], {"status": "superseded"})
    return {"version": previous["version"] + 1, "supersedes_id": previous["id"]}


def finalize(user: Optional[AuthenticatedUser], document: dict) -> tuple[dict, bool]:
    """Run the file check. Returns the updated document and whether it should be read next.
    `user` is None for the seed script, which uploads as the system."""
    if document["integrity_status"] != "pending":
        return document, False
    try:
        data = db.storage.download(document["storage_path"])
    except Exception:
        raise FileNotFoundError("The file has not been uploaded yet")

    status, note, pages = _integrity(document, data)
    sha256 = hashlib.sha256(data).hexdigest()
    updates = {
        "sha256": sha256, "integrity_status": status, "integrity_note": note, "page_count": pages,
        "size_bytes": len(data),
        "processing_status": "processing" if status == "passed" else "error",
        "processing_note": None if status == "passed" else "Not read because the file check failed",
    }
    if status == "passed":
        updates.update(_supersede(document))
    updated = db.update("documents", document["id"], updates) or {**document, **updates}
    db.insert("verification_checks", {
        "document_id": document["id"], "method": "HASH", "source": "internal", "status": status,
        "response": {"sha256": sha256, "note": note}, "checked_by": user.id if user else None,
    })
    audit.record(user, "document_finalized", "document", document["id"], document["application_id"],
                 {"sha256": sha256, "integrity": status, "note": note, "pages": pages,
                  "version": updated.get("version"), "supersedes_id": updated.get("supersedes_id")})
    return updated, status == "passed"


def _min_confidence() -> float:
    rule = (db.table("rules").select("params").eq("rule_code", "R-OCR-01").eq("status", "active")
            .order("version", desc=True).limit(1).execute().data or [])
    try:
        return float(rule[0]["params"].get("min_confidence", extraction.DEFAULT_MIN_CONFIDENCE))
    except (IndexError, AttributeError, TypeError, ValueError):
        return extraction.DEFAULT_MIN_CONFIDENCE


def revalidate_after_replacement(application: dict) -> None:
    """A document read into an application that has been validated before (a replacement, usually for an
    evidence request) gets a fresh full run, so findings that no longer hold close automatically and any
    new one appears (build spec 7.1, step 3). The run is recorded as the system's, not a person's."""
    from services.validation import has_full_run, run_validation  # validation reads documents; avoid an import cycle
    if application["workflow_status"] == "draft" or not has_full_run(application["id"]):
        return
    try:
        run_validation(application["id"], "full", None, trigger="document_replaced")
    except Exception:
        logger.exception("Validation after a replacement failed for %s", application["id"])


def process_document(document_id: str) -> None:
    """Read the document. Runs in the background after finalize; never raises."""
    document = db.fetch_one("documents", id=document_id)
    if not document or document["integrity_status"] != "passed":
        return
    try:
        doc_type = db.fetch_one("document_types", code=document["doc_type"])
        application = db.fetch_one("applications", id=document["application_id"])
        data = db.storage.download(document["storage_path"])

        db.table("extracted_fields").delete().eq("document_id", document_id).execute()
        db.table("faculty").delete().eq("document_id", document_id).execute()
        counts = {"fields": 0, "needs_confirmation": 0, "faculty": 0}

        if doc_type["is_photo"]:
            db.table("media_assets").update(extraction.photo_metadata(data)).eq("document_id", document_id).execute()
        else:
            pages = extraction.read_pages(data, document["mime"])
            templates = db.fetch_all("extraction_templates", doc_type=document["doc_type"])
            fields = extraction.extract_fields(pages, templates, _min_confidence())
            if fields:
                db.table("extracted_fields").insert([{**f, "document_id": document_id} for f in fields]).execute()
            counts["fields"] = len(fields)
            counts["needs_confirmation"] = sum(f["review_state"] == "needs_confirmation" for f in fields)
            if document["doc_type"] == "faculty_list":
                faculty = extraction.parse_faculty(pages)
                if faculty:
                    db.table("faculty").insert([{**f, "document_id": document_id, "application_id": application["id"],
                                                 "institution_id": application["institution_id"]} for f in faculty]).execute()
                counts["faculty"] = len(faculty)

        try:
            signature, metadata = forensics.record(document, data, doc_type)
            counts.update({"signature": signature["status"], "metadata": metadata["status"]})
        except Exception:
            logger.exception("Signature and metadata checks failed for %s", document_id)

        db.update("documents", document_id, {"processing_status": "done", "processing_note": None})
        audit.record(None, "document_processed", "document", document_id, document["application_id"], counts)
        revalidate_after_replacement(application)
    except Exception as exc:
        logger.exception("Reading document %s failed", document_id)
        note = str(exc) if isinstance(exc, extraction.UnreadableFile) else "The document could not be read"
        db.update("documents", document_id, {"processing_status": "error", "processing_note": note})
        audit.record(None, "document_processing_failed", "document", document_id, document["application_id"], {"note": note})
