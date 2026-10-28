"""
Authenticity checks on a document (build spec section 10, phase 4): the issuer registry (MOCK) and a
reviewer's manual confirmation with the issuer. Each method writes its own verification_checks row and
never changes another method's; the latest row per method is that method's state.
"""
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.access import document_for
from core.config import settings
from core.db import db
from core.security import AuthenticatedUser, require_role
from services import audit, forensics, registry_adapter
from services.extraction import sniff_mime
from services.validation import has_full_run, run_validation

router = APIRouter(tags=["Verification"])

READERS = ["reviewer", "rule_admin"]
ATTACHMENT_MAX_MB = 5
EXTENSION = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
MANUAL_STATUS = {"pending": "manual_pending", "confirmed": "manual_confirmed", "not_confirmed": "manual_not_confirmed"}
CHECK_FIELDS = ("id", "document_id", "method", "source", "status", "is_mock", "checked_by", "checked_at")


def _public(check: dict, names: dict[str, str]) -> dict:
    """A check as the browser sees it: the attachment's storage path stays on the server."""
    response = dict(check.get("response") or {})
    attachment = response.pop("attachment", None)
    if attachment:
        response["attachment"] = {k: attachment.get(k) for k in ("name", "mime", "size")}
    return {**{k: check.get(k) for k in CHECK_FIELDS}, "response": response,
            "checked_by_name": names.get(check.get("checked_by") or "", None)}


def _require_submitted(application: dict) -> None:
    if application["workflow_status"] == "draft":
        raise HTTPException(status_code=409, detail="The institution has not submitted this application yet")


def _revalidate(user: AuthenticatedUser, application: dict, trigger: str) -> Optional[dict]:
    """A registry answer can open or close check C15, so a validated application is validated again."""
    if not has_full_run(application["id"]):
        return None
    return run_validation(application["id"], "full", user, trigger=trigger)["summary"]


@router.get("/documents/{document_id}/verification")
def document_verification(document_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    """Every authenticity check on the document, newest first, and whether an issuer registry holds it."""
    document, _ = document_for(user, document_id)
    checks = (db.table("verification_checks").select("*").eq("document_id", document_id)
              .order("checked_at", desc=True).execute().data or [])
    actor_ids = list({c["checked_by"] for c in checks if c.get("checked_by")})
    names = {m["user_id"]: m["full_name"] for m in (db.table("members").select("user_id,full_name")
                                                    .in_("user_id", actor_ids).execute().data or [])} if actor_ids else {}
    config = registry_adapter.REGISTRY_DOCUMENTS.get(document["doc_type"])
    return {
        "registry": {"supported": bool(config), "issuer": config["issuer"] if config else None,
                     "key_field": config["key"] if config else None, "mode": registry_adapter.mode(), "is_mock": True},
        "checks": [_public(c, names) for c in checks],
    }


@router.post("/documents/{document_id}/verify/registry")
def verify_registry(document_id: str, user: AuthenticatedUser = Depends(require_role(["reviewer"]))):
    """Look the document up in the issuer registry (MOCK) and compare the record with the values read."""
    document, application = document_for(user, document_id)
    _require_submitted(application)
    config = registry_adapter.REGISTRY_DOCUMENTS.get(document["doc_type"])
    if not config:
        raise HTTPException(status_code=422, detail="No issuer registry holds this kind of document. Record a manual check instead")
    if document["status"] != "current" or document["integrity_status"] != "passed":
        raise HTTPException(status_code=409, detail="Only the current version of a document that passed the file check can be looked up")
    fields = {f["field_name"]: f for f in db.fetch_all("extracted_fields", document_id=document_id)}
    key = fields.get(config["key"])
    if not registry_adapter.usable(key):
        raise HTTPException(status_code=409, detail=f"The {config['key'].replace('_', ' ')} has not been read or still needs confirming. "
                                                     "Check the value first, then look it up")

    result = registry_adapter.lookup(document["doc_type"], fields)
    check = db.insert("verification_checks", {
        "document_id": document_id, "method": "REGISTRY", "source": f"{registry_adapter.SOURCE}: {result.issuer}",
        "status": result.status, "is_mock": True, "checked_by": user.id,
        "response": {"mode": registry_adapter.mode(), "issuer": result.issuer,
                     "key": {"field": config["key"], "value": key["field_value"]},
                     "record": result.record, "compared": result.compared, "note": result.note},
    })
    audit.record(user, "registry_checked", "document", document_id, application["id"], {
        "status": result.status, "is_mock": True, "issuer": result.issuer, "key": key["field_value"],
        "differs": [c["field"] for c in result.compared if c["same"] is False],
    })
    return {"check": _public(check, {}), "validation": _revalidate(user, application, "registry_checked")}


@router.post("/documents/{document_id}/verify/signature")
def verify_signature(document_id: str, user: AuthenticatedUser = Depends(require_role(["reviewer"]))):
    """Check the embedded signature and the file metadata again, for example after the trust store changed.
    Each run is a new row; earlier results are kept."""
    document, application = document_for(user, document_id)
    _require_submitted(application)
    if document["status"] != "current" or document["integrity_status"] != "passed":
        raise HTTPException(status_code=409, detail="Only the current version of a document that passed the file check can be checked")
    try:
        data = db.storage.download(document["storage_path"])
    except Exception:
        raise HTTPException(status_code=502, detail="The file could not be fetched from storage, try again")
    doc_type = db.fetch_one("document_types", code=document["doc_type"]) or {}
    signature, metadata = forensics.record(document, data, doc_type, user.id)
    audit.record(user, "signature_checked", "document", document_id, application["id"],
                 {"signature": signature["status"], "metadata": metadata["status"],
                  "indicators": [i["code"] for i in metadata.get("indicators", [])]})
    return {"signature": signature["status"], "metadata": metadata["status"],
            "validation": _revalidate(user, application, "signature_checked")}


@router.post("/documents/{document_id}/verify/manual")
def verify_manual(
    document_id: str,
    outcome: Literal["pending", "confirmed", "not_confirmed"] = Form(...),
    issuer: str = Form(..., min_length=2, max_length=200),
    contact: str = Form(..., min_length=2, max_length=300),
    note: str = Form(..., min_length=3, max_length=2000),
    attachment: Optional[UploadFile] = File(None),
    user: AuthenticatedUser = Depends(require_role(["reviewer"])),
):
    """Record a confirmation sought from the issuer by phone, letter or email: who was asked, how, and
    what they said, with an optional copy of their reply. Asked and waiting is manual_pending."""
    document, application = document_for(user, document_id)
    _require_submitted(application)

    stored = None
    if attachment is not None and attachment.filename:
        data = attachment.file.read(ATTACHMENT_MAX_MB * 1024 * 1024 + 1)
        mime = sniff_mime(data)
        if mime is None:
            raise HTTPException(status_code=422, detail="The attachment must be a PDF, JPEG or PNG")
        if len(data) > ATTACHMENT_MAX_MB * 1024 * 1024:
            raise HTTPException(status_code=422, detail=f"The attachment is larger than {ATTACHMENT_MAX_MB} MB")
        path = f"verification/{application['id']}/{document_id}/{uuid.uuid4()}.{EXTENSION[mime]}"
        db.storage.upload(path, data, {"content-type": mime, "upsert": "false"})
        stored = {"path": path, "name": attachment.filename[:200], "mime": mime, "size": len(data)}

    check = db.insert("verification_checks", {
        "document_id": document_id, "method": "MANUAL", "source": issuer.strip(), "status": MANUAL_STATUS[outcome],
        "is_mock": False, "checked_by": user.id,
        "response": {"issuer": issuer.strip(), "contact": contact.strip(), "note": note.strip(), "attachment": stored},
    })
    audit.record(user, "manual_check_recorded", "document", document_id, application["id"], {
        "status": MANUAL_STATUS[outcome], "issuer": issuer.strip(), "contact": contact.strip(), "note": note.strip(),
        "attachment": stored["name"] if stored else None,
    })
    return {"check": _public(check, {})}


@router.get("/verification-checks/{check_id}/attachment")
def check_attachment(check_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    check = db.fetch_one("verification_checks", id=check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    document_for(user, check["document_id"])
    attachment = (check.get("response") or {}).get("attachment")
    if not attachment:
        raise HTTPException(status_code=404, detail="This check has no attachment")
    signed = db.storage.create_signed_url(attachment["path"], settings.SIGNED_LINK_TTL_SECONDS)
    url = signed.get("signedURL") or signed.get("signedUrl")
    if not url:
        raise HTTPException(status_code=502, detail="Could not create a viewing link, try again")
    return {"url": url, "mime": attachment.get("mime"), "expires_in": settings.SIGNED_LINK_TTL_SECONDS}


# ------------------------------------------------------------------------------------------------
# The registry adapter setting (the full settings screen is phase 5)
# ------------------------------------------------------------------------------------------------

class RegistryMode(BaseModel):
    mode: Literal["unavailable", "match", "mismatch"]
    reason: str = Field(..., min_length=3, max_length=500)


@router.get("/admin/settings/registry")
def get_registry_mode(user: AuthenticatedUser = Depends(require_role(READERS))):
    labels = {t["code"]: t["label"] for t in db.fetch_all("document_types")}
    return {"mode": registry_adapter.mode(), "modes": list(registry_adapter.MODES), "is_mock": True,
            "documents": [{"doc_type": t, "label": labels.get(t, t), **c} for t, c in registry_adapter.REGISTRY_DOCUMENTS.items()]}


@router.put("/admin/settings/registry")
def set_registry_mode(body: RegistryMode, user: AuthenticatedUser = Depends(require_role(["rule_admin"]))):
    before = registry_adapter.mode()
    db.table("settings").upsert({"key": "registry_adapter_mode", "value": body.mode}, on_conflict="key").execute()
    audit.record(user, "setting_changed", "setting", "registry_adapter_mode", None,
                 {"from": before, "to": body.mode, "reason": body.reason.strip()})
    return get_registry_mode(user)
