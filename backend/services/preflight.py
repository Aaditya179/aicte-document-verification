"""
Pre-flight (build spec 7 and 12): the institution runs the within-application checks on its own
application before submitting, and sees what to fix and where. Nothing is stored: no validation run,
no finding, no audit event. Cross-institution checks and the reviewer's registry comparison are never
included.

Each item carries a `fix`: the wizard step that fixes it and, where there is one, the document type or
photo category to upload again.
"""
from dataclasses import asdict
from typing import Optional

from services.validation import Context, Finding, evaluate, load_context

STEPS = ("details", "documents", "evidence", "preflight", "submit")

PHOTO_TYPE = "infrastructure_photo"


def _named(label: str) -> str:
    """A label inside a sentence: "affidavit", but "Fire NOC" keeps its capitals."""
    return label if any(c.isupper() for c in label[1:]) else label.lower()


def _doc_type_of(f: Finding, ctx: Context) -> Optional[str]:
    by_id = {d["id"]: d for d in ctx.documents}
    for e in f.evidence:
        doc = by_id.get(e.get("document_id"))
        if doc:
            return doc["doc_type"]
    return None


def fix_for(f: Finding, ctx: Context) -> dict:
    discriminator = f.key.split("|", 2)[2] if f.key.count("|") >= 2 else ""
    t = f.finding_type
    if t == "MISSING_DOCUMENT":
        step = "evidence" if discriminator in ("floor_plan", PHOTO_TYPE) else "documents"
        return {"step": step, "doc_type": discriminator, "hint": f"Upload the {_named(ctx.label(discriminator))}."}
    if t == "EXPIRED_DOCUMENT":
        return {"step": "documents", "doc_type": discriminator, "hint": "Upload the current, in-date version."}
    if t == "DATE_ORDER_INVALID":
        return {"step": "documents", "doc_type": discriminator, "hint": "Check the dates printed on it, and upload a corrected copy if one is wrong."}
    if t in ("DATE_CONFLICT", "ID_MISMATCH", "COUNT_CONFLICT"):
        return {"step": "documents", "doc_type": _doc_type_of(f, ctx),
                "hint": "The two documents give different values. Upload a corrected copy of whichever is wrong."}
    if t == "FIELD_NEEDS_CONFIRMATION":
        doc_type = discriminator.split(".")[0] or None
        return {"step": "documents", "doc_type": doc_type,
                "hint": "This value could not be read clearly. Upload a clearer copy; a date reads best with the month in words."}
    if t == "DUPLICATE_FILE":
        return {"step": "documents", "doc_type": _doc_type_of(f, ctx),
                "hint": "The same file is uploaded as two documents. Upload the right file for one of them."}
    if t == "INFRA_EVIDENCE_MISSING":
        if discriminator == "floor_plan":
            return {"step": "evidence", "doc_type": "floor_plan", "hint": "Upload the floor plan."}
        return {"step": "evidence", "doc_type": PHOTO_TYPE, "category": discriminator, "hint": "Upload a photo of it."}
    if t in ("AREA_MISMATCH", "AREA_BELOW_MINIMUM"):
        return {"step": "evidence", "anchor": "rooms",
                "hint": "Check the room table against the floor plan, and the declared built-up area."}
    if t == "PHOTO_METADATA":
        category = next((m.get("category") for e in f.evidence for m in [ctx.media.get(e.get("document_id") or "", {})] if m), None)
        return {"step": "evidence", "doc_type": PHOTO_TYPE, "category": category, "hint": "Upload a recent photo."}
    return {"step": "documents", "hint": "Check the document named above."}


def run(application: dict) -> dict:
    ctx = load_context(application, include_cross=False)
    findings, _ = evaluate(ctx, include_cross=False)
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order.get(f.severity, 9), STEPS.index(fix_for(f, ctx)["step"]), f.key))
    items = []
    for f in findings:
        item = asdict(f)
        for k in ("is_cross_institution", "related_application_id"):
            item.pop(k)
        item["fix"] = fix_for(f, ctx)
        items.append(item)
    return {"as_of_date": ctx.as_of.isoformat(), "rule_versions": {c: r["version"] for c, r in sorted(ctx.rules.items())},
            "items": items, "stored": False}
