"""
Settings a rule administrator looks after (build spec 12, /admin/settings): the as-of date, priority
weights, checklists, document types, extraction templates and the signature trust store. The registry
adapter mode is in routers/verification.py.

These are configuration, not rules: they are not versioned, so every change is written to the audit
trail with what it was before, what it became and why (ASSUMPTIONS.md).
"""
import re
import datetime as dt
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.clock import as_of_date
from core.db import db, parallel
from core.security import AuthenticatedUser, require_role
from services import audit, forensics, registry_adapter
from services.priority import WEIGHT_LABEL

router = APIRouter(prefix="/admin/settings", tags=["Settings"])

READERS = ["rule_admin", "reviewer"]
ADMIN = ["rule_admin"]


def _changed(user: AuthenticatedUser, setting: str, before, after, reason: str) -> None:
    audit.record(user, "setting_changed", "setting", setting, None, {"from": before, "to": after, "reason": reason.strip()})


@router.get("")
def get_settings(user: AuthenticatedUser = Depends(require_role(READERS))):
    as_of_row, weights, categories, types, required, templates = parallel(
        lambda: db.fetch_one("settings", key="as_of"),
        lambda: db.fetch_all("priority_weights"),
        lambda: db.fetch_all("categories"),
        lambda: db.fetch_all("document_types"),
        lambda: db.fetch_all("required_documents"),
        lambda: db.table("extraction_templates").select("*").order("doc_type").order("field_name").execute().data or [],
    )
    value = (as_of_row or {}).get("value") or {}
    order = list(WEIGHT_LABEL)
    return {
        "as_of": {"mode": value.get("mode", "today"), "date": value.get("date"), "effective": as_of_date().isoformat()},
        "priority_weights": sorted([{**w, "label": WEIGHT_LABEL.get(w["key"], w["key"])} for w in weights],
                                   key=lambda w: order.index(w["key"]) if w["key"] in order else 99),
        "categories": categories, "document_types": types, "required_documents": required,
        "extraction_templates": templates,
        "trust_store": [{k: v for k, v in c.items() if k != "pem"} for c in forensics.trust_store()],
        "registry_mode": registry_adapter.mode(),
    }


class AsOf(BaseModel):
    mode: Literal["today", "fixed"]
    date: Optional[dt.date] = None
    reason: str = Field(..., min_length=3, max_length=500)


@router.put("/as-of")
def set_as_of(body: AsOf, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """The date that date checks compare against. A fixed date keeps demos and the evaluation repeatable."""
    if body.mode == "fixed" and not body.date:
        raise HTTPException(status_code=422, detail="Choose the fixed date")
    before = (db.fetch_one("settings", key="as_of") or {}).get("value")
    value = {"mode": "fixed", "date": body.date.isoformat()} if body.mode == "fixed" else {"mode": "today"}
    db.table("settings").upsert({"key": "as_of", "value": value}, on_conflict="key").execute()
    _changed(user, "as_of", before, value, body.reason)
    return {"mode": value["mode"], "date": value.get("date"), "effective": as_of_date().isoformat()}


class Weights(BaseModel):
    weights: dict[str, int]
    reason: str = Field(..., min_length=3, max_length=500)


@router.put("/priority-weights")
def set_weights(body: Weights, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """Weights only order the review queue; they never change a status or a finding."""
    current = {w["key"]: w["weight"] for w in db.fetch_all("priority_weights")}
    unknown = set(body.weights) - set(current)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown weight {', '.join(sorted(unknown))}")
    if any(not 0 <= v <= 100 for v in body.weights.values()):
        raise HTTPException(status_code=422, detail="Each weight is between 0 and 100")
    changed = {k: v for k, v in body.weights.items() if current[k] != v}
    for k, v in changed.items():
        db.table("priority_weights").update({"weight": v}).eq("key", k).execute()
    if changed:
        _changed(user, "priority_weights", {k: current[k] for k in changed}, changed, body.reason)
    return get_settings(user)["priority_weights"]


class ChecklistItem(BaseModel):
    category: str
    doc_type: str
    required: bool
    reason: str = Field(..., min_length=3, max_length=500)


@router.put("/checklist")
def set_checklist(body: ChecklistItem, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """Whether a category requires a document type (check C1). Takes effect on the next validation run."""
    if not db.fetch_one("categories", code=body.category) or not db.fetch_one("document_types", code=body.doc_type):
        raise HTTPException(status_code=422, detail="Unknown category or document type")
    existing = db.fetch_one("required_documents", category=body.category, doc_type=body.doc_type)
    if body.required and not existing:
        db.insert("required_documents", {"category": body.category, "doc_type": body.doc_type, "mandatory": True})
    elif not body.required and existing:
        db.table("required_documents").delete().eq("id", existing["id"]).execute()
    if bool(existing) != body.required:
        _changed(user, f"checklist:{body.category}:{body.doc_type}", bool(existing), body.required, body.reason)
    return db.fetch_all("required_documents")


class DocumentTypeFlags(BaseModel):
    has_expiry: Optional[bool] = None
    signature_required: Optional[bool] = None
    reason: str = Field(..., min_length=3, max_length=500)


@router.put("/document-types/{code}")
def set_document_type(code: str, body: DocumentTypeFlags, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """has_expiry switches check C2 on for the type; signature_required makes an unsigned copy a C13 finding."""
    current = db.fetch_one("document_types", code=code)
    if not current:
        raise HTTPException(status_code=404, detail="Document type not found")
    changes = {k: v for k, v in body.model_dump(exclude={"reason"}, exclude_none=True).items() if current.get(k) != v}
    if changes:
        db.table("document_types").update(changes).eq("code", code).execute()
        _changed(user, f"document_type:{code}", {k: current[k] for k in changes}, changes, body.reason)
    return db.fetch_one("document_types", code=code)


class Template(BaseModel):
    regex: Optional[str] = Field(None, min_length=3, max_length=500)
    required: Optional[bool] = None
    reason: str = Field(..., min_length=3, max_length=500)


@router.put("/templates/{template_id}")
def set_template(template_id: str, body: Template, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """The pattern a value is read with, and whether it is required. Applies to documents read from now on."""
    current = db.fetch_one("extraction_templates", id=template_id)
    if not current:
        raise HTTPException(status_code=404, detail="Template not found")
    if body.regex is not None:
        try:
            pattern = re.compile(body.regex, re.IGNORECASE | re.MULTILINE)
        except re.error as exc:
            raise HTTPException(status_code=422, detail=f"The pattern is not valid: {exc}")
        if pattern.groups < (current.get("group_index") or 1):
            raise HTTPException(status_code=422, detail=f"The pattern needs a group ({{...}}) number {current.get('group_index') or 1} around the value")
    changes = {k: v for k, v in body.model_dump(exclude={"reason"}, exclude_none=True).items() if current.get(k) != v}
    if changes:
        db.update("extraction_templates", template_id, changes)
        _changed(user, f"template:{current['doc_type']}.{current['field_name']}", {k: current[k] for k in changes}, changes, body.reason)
    return db.fetch_one("extraction_templates", id=template_id)


@router.post("/trust-store", status_code=201)
def add_certificate(
    certificate: UploadFile = File(...),
    name: str = Form(..., min_length=2, max_length=200),
    reason: str = Form(..., min_length=3, max_length=500),
    user: AuthenticatedUser = Depends(require_role(ADMIN)),
):
    """Trust a certificate (PEM or DER) for signature checks. Signatures checked earlier keep their result
    until a reviewer checks them again."""
    data = certificate.file.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise HTTPException(status_code=422, detail="A certificate file is under 256 KB")
    try:
        info = forensics.describe(forensics.load_certificate(data))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    store = forensics.trust_store()
    if any(c["fingerprint"] == info["fingerprint"] for c in store):
        raise HTTPException(status_code=409, detail="This certificate is already trusted")
    entry = {**info, "name": name.strip(), "source": "rule_admin", "added_by": user.id,
             "added_at": datetime.now(timezone.utc).isoformat()}
    db.table("settings").upsert({"key": "trust_store", "value": {"certificates": store + [entry]}}, on_conflict="key").execute()
    _changed(user, "trust_store", None, {"added": {k: entry[k] for k in ("name", "subject", "fingerprint")}}, reason)
    return {k: v for k, v in entry.items() if k != "pem"}


class Remove(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/trust-store/{fingerprint}/remove")
def remove_certificate(fingerprint: str, body: Remove, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    store = forensics.trust_store()
    gone = next((c for c in store if c["fingerprint"] == fingerprint), None)
    if not gone:
        raise HTTPException(status_code=404, detail="Certificate not found")
    db.table("settings").upsert({"key": "trust_store", "value": {"certificates": [c for c in store if c is not gone]}},
                                on_conflict="key").execute()
    _changed(user, "trust_store", {"removed": {k: gone.get(k) for k in ("name", "subject", "fingerprint")}}, None, body.reason)
    return [{k: v for k, v in c.items() if k != "pem"} for c in store if c is not gone]
