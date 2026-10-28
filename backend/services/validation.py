"""
The validation engine (build spec section 7). Deterministic Python only: no check uses an LLM.

run_validation(application_id, mode, actor):
  full       reviewer run: records a validation run, writes findings, auto-closes what no longer holds
  preflight  institution's own check: returns findings, writes nothing, never includes cross-institution types
  dry_run    rule impact preview: returns findings, writes nothing

Each check reads a snapshot of one application (Context) and returns Findings. A finding's key is
TYPE|application_code|discriminator, so a re-run finds the same finding again and reviewer actions on it
survive. Values that still need a person to confirm them are never compared; check C5 lists them instead.

Wording: a finding says what differs and where, never what it implies.
"""
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from core.clock import as_of_date
from core.db import db, parallel
from core.security import AuthenticatedUser
from services import audit, crossinst, normalise

logger = logging.getLogger("proofpath.validation")

UNRESOLVED = ("open", "evidence_requested")
CROSS_TYPES = {"REUSED_IDENTIFIER", "GHOST_FACULTY", "PHOTO_REUSE"}


@dataclass
class Finding:
    key: str
    finding_type: str
    rule_code: str
    rule_version: Optional[int]
    severity: str
    title: str
    detail: str
    evidence: list[dict] = field(default_factory=list)
    is_cross_institution: bool = False
    related_application_id: Optional[str] = None


@dataclass
class Context:
    application: dict
    as_of: date
    documents: list[dict]                       # current versions, whatever their file check
    fields: dict[str, list[dict]]               # document id -> extracted fields
    doc_types: dict[str, dict]
    required: list[dict]                        # required_documents rows for the category
    pairs: list[dict]
    rules: dict[str, dict]                      # rule code -> the active version on the as-of date
    category_label: str = ""
    media: dict[str, dict] = field(default_factory=dict)    # document id -> media_assets row (photos)
    faculty: list[dict] = field(default_factory=list)       # faculty rows of the current faculty list
    rooms: list[dict] = field(default_factory=list)         # the room table entered for the floor plan
    cross: Optional[crossinst.CrossData] = None             # other institutions' claims; None skips C7 to C9

    @property
    def passed(self) -> list[dict]:
        return [d for d in self.documents if d["integrity_status"] == "passed"]

    def label(self, doc_type: str) -> str:
        return self.doc_types.get(doc_type, {}).get("label", normalise.text(doc_type.replace("_", " ")))

    def field(self, document: dict, name: str) -> Optional[dict]:
        return next((f for f in self.fields.get(document["id"], []) if f["field_name"] == name), None)

    def version(self, rule_code: str) -> Optional[int]:
        return self.rules.get(rule_code, {}).get("version")

    def param(self, rule_code: str, name: str, default):
        return (self.rules.get(rule_code, {}).get("params") or {}).get(name, default)


# ------------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------------

def usable(f: Optional[dict]) -> bool:
    """A value the checks may compare: read, and not waiting for a person to confirm it."""
    return bool(f) and f.get("field_value") is not None and f.get("review_state") != "needs_confirmation"


def ddmmyyyy(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(iso)


def field_label(name: str) -> str:
    return normalise.text(name.replace("_", " ")).capitalize()


def shown(f: dict) -> str:
    return f.get("original_value") or f.get("field_value") or "not found"


def evidence(document: Optional[dict], f: Optional[dict], role: str, label: str, value: Optional[str] = None) -> dict:
    return {
        "document_id": document["id"] if document else None,
        "page_number": f.get("page_number") if f else None,
        "role": role, "label": label,
        "shown_value": value if value is not None else (shown(f) if f else None),
    }


def page_text(f: dict) -> str:
    return f"page {f['page_number']}" if f.get("page_number") else "page not known"


def same_value(value_type: str, a: str, b: str) -> bool:
    if value_type in ("int", "number"):
        try:
            return Decimal(a) == Decimal(b)
        except InvalidOperation:
            return a == b
    if value_type == "date":
        return a == b
    return normalise.identifier_key(a) == normalise.identifier_key(b)


def first_of_type(ctx: Context, doc_type: str) -> Optional[dict]:
    """The current, file-checked document of a type (the newest if, oddly, there are several)."""
    docs = [d for d in ctx.passed if d["doc_type"] == doc_type]
    return max(docs, key=lambda d: d.get("version") or 1) if docs else None


# ------------------------------------------------------------------------------------------------
# Checks C1 to C6
# ------------------------------------------------------------------------------------------------

def check_missing_documents(ctx: Context) -> list[Finding]:
    """C1: required documents for the category minus current documents of that type that passed the file check."""
    out = []
    code = ctx.application["code"]
    for req in ctx.required:
        if not req.get("mandatory", True) or any(d["doc_type"] == req["doc_type"] for d in ctx.passed):
            continue
        label = ctx.label(req["doc_type"])
        detail = f"The checklist for {ctx.category_label.lower() or 'this category'} requires a {label.lower()}. " \
                 f"No current {label.lower()} has passed the file check."
        failed = [d for d in ctx.documents if d["doc_type"] == req["doc_type"] and d["integrity_status"] == "failed"]
        if failed:
            detail += f" A file uploaded as the {label.lower()} failed the file check: {failed[0].get('integrity_note') or 'see the document'}."
        out.append(Finding(
            key=f"MISSING_DOCUMENT|{code}|{req['doc_type']}", finding_type="MISSING_DOCUMENT",
            rule_code="R-DOC-REQ", rule_version=ctx.version("R-DOC-REQ"), severity="high",
            title=f"{label} not received", detail=detail,
            evidence=[evidence(failed[0] if failed else None, None, "SINGLE", f"Required {label.lower()}",
                               "failed the file check" if failed else "not received")],
        ))
    return out


def check_expired(ctx: Context) -> list[Finding]:
    """C2: an expiry date earlier than the as-of date, for document types that expire."""
    out = []
    for doc in ctx.passed:
        if not ctx.doc_types.get(doc["doc_type"], {}).get("has_expiry"):
            continue
        expiry = ctx.field(doc, "expiry_date")
        if not usable(expiry) or expiry["field_value"] >= ctx.as_of.isoformat():
            continue
        label = ctx.label(doc["doc_type"])
        out.append(Finding(
            key=f"EXPIRED_DOCUMENT|{ctx.application['code']}|{doc['doc_type']}", finding_type="EXPIRED_DOCUMENT",
            rule_code="R-EXP-01", rule_version=ctx.version("R-EXP-01"), severity="high",
            title=f"{label} expired on {ddmmyyyy(expiry['field_value'])}",
            detail=f"The {label.lower()} gives its validity as {shown(expiry)} ({page_text(expiry)}), "
                   f"before the as-of date {ctx.as_of:%d/%m/%Y}. Candidate for review.",
            evidence=[evidence(doc, expiry, "SINGLE", f"{label}, valid until")],
        ))
    return out


def check_date_order(ctx: Context) -> list[Finding]:
    """C3: an expiry date earlier than the issue date in the same document."""
    out = []
    for doc in ctx.passed:
        issue, expiry = ctx.field(doc, "issue_date"), ctx.field(doc, "expiry_date")
        if not (usable(issue) and usable(expiry)) or expiry["field_value"] >= issue["field_value"]:
            continue
        label = ctx.label(doc["doc_type"])
        out.append(Finding(
            key=f"DATE_ORDER_INVALID|{ctx.application['code']}|{doc['doc_type']}", finding_type="DATE_ORDER_INVALID",
            rule_code="R-DATE-01", rule_version=ctx.version("R-DATE-01"), severity="medium",
            title=f"{label}: valid-until date is before the date of issue",
            detail=f"The {label.lower()} was issued on {shown(issue)} ({page_text(issue)}) and is valid until "
                   f"{shown(expiry)} ({page_text(expiry)}), which is earlier. Candidate for review.",
            evidence=[evidence(doc, issue, "A", f"{label}, date of issue"),
                      evidence(doc, expiry, "B", f"{label}, valid until")],
        ))
    return out


def check_pairs(ctx: Context) -> list[Finding]:
    """C4: the same value stated in two documents of one application, different after normalisation."""
    out = []
    for pair in ctx.pairs:
        doc_a, doc_b = first_of_type(ctx, pair["doc_type_a"]), first_of_type(ctx, pair["doc_type_b"])
        if not doc_a or not doc_b:
            continue
        a, b = ctx.field(doc_a, pair["field_a"]), ctx.field(doc_b, pair["field_b"])
        if not (usable(a) and usable(b)) or same_value(a.get("value_type") or "text", a["field_value"], b["field_value"]):
            continue
        label_a, label_b = ctx.label(pair["doc_type_a"]), ctx.label(pair["doc_type_b"])
        out.append(Finding(
            key=f"{pair['finding_type']}|{ctx.application['code']}|{pair['pair_code']}", finding_type=pair["finding_type"],
            rule_code=pair.get("rule_code") or "R-PAIR-01", rule_version=ctx.version(pair.get("rule_code") or "R-PAIR-01"),
            severity="medium",
            title=f"{pair['label']} differs between the {label_a.lower()} and the {label_b.lower()}",
            detail=f"The {label_a.lower()} gives {shown(a)} ({page_text(a)}); the {label_b.lower()} gives "
                   f"{shown(b)} ({page_text(b)}). Candidate for review.",
            evidence=[evidence(doc_a, a, "A", f"{label_a}, {field_label(pair['field_a']).lower()}"),
                      evidence(doc_b, b, "B", f"{label_b}, {field_label(pair['field_b']).lower()}")],
        ))
    return out


def check_needs_confirmation(ctx: Context) -> list[Finding]:
    """C5: a value not found, read with low confidence, or ambiguous: a person confirms it."""
    out = []
    for doc in ctx.passed:
        for f in ctx.fields.get(doc["id"], []):
            if f.get("review_state") != "needs_confirmation":
                continue
            label = ctx.label(doc["doc_type"])
            out.append(Finding(
                key=f"FIELD_NEEDS_CONFIRMATION|{ctx.application['code']}|{doc['doc_type']}.{f['field_name']}",
                finding_type="FIELD_NEEDS_CONFIRMATION", rule_code="R-OCR-01", rule_version=ctx.version("R-OCR-01"),
                severity="low",
                title=f"{label}: {field_label(f['field_name']).lower()} needs confirmation",
                detail=f"{f.get('review_reason') or 'The value could not be read with confidence'}. "
                       "A reviewer confirms or corrects the value before it is compared.",
                evidence=[evidence(doc, f, "SINGLE", f"{label}, {field_label(f['field_name']).lower()}")],
            ))
    return out


def check_duplicates(ctx: Context) -> list[Finding]:
    """C6: two current documents of one application with the same SHA-256."""
    by_hash: dict[str, list[dict]] = {}
    for doc in ctx.passed:
        if doc.get("sha256"):
            by_hash.setdefault(doc["sha256"], []).append(doc)
    out = []
    for sha, docs in sorted(by_hash.items()):
        if len(docs) < 2:
            continue
        docs = sorted(docs, key=lambda d: (d["doc_type"], d.get("uploaded_at") or ""))
        names = [ctx.label(d["doc_type"]).lower() for d in docs]
        out.append(Finding(
            key=f"DUPLICATE_FILE|{ctx.application['code']}|{sha[:16]}", finding_type="DUPLICATE_FILE",
            rule_code="R-DUP-01", rule_version=ctx.version("R-DUP-01"), severity="low",
            title=f"The same file was uploaded as the {' and the '.join(names)}",
            detail=f"{len(docs)} documents share the SHA-256 fingerprint {sha[:16]}…: "
                   + "; ".join(f"{ctx.label(d['doc_type'])} ({d.get('original_name') or 'unnamed file'})" for d in docs)
                   + ". Candidate for review.",
            evidence=[evidence(d, None, "A" if i == 0 else "B", ctx.label(d["doc_type"]), d.get("original_name") or sha[:16])
                      for i, d in enumerate(docs)],
        ))
    return out


# ------------------------------------------------------------------------------------------------
# Checks C7 to C9 (services/crossinst.py) and C10 to C12
# ------------------------------------------------------------------------------------------------

def _cross_maker(ctx: Context):
    def make(*, rule_code: str, **kw) -> Finding:
        return Finding(rule_code=rule_code, rule_version=ctx.version(rule_code), is_cross_institution=True, **kw)
    return make


def check_reused_identifiers(ctx: Context) -> list[Finding]:
    """C7: the same certificate, NOC, registration or survey number in another institution's application."""
    return crossinst.reused_identifiers(ctx, ctx.cross, _cross_maker(ctx)) if ctx.cross else []


def check_ghost_faculty(ctx: Context) -> list[Finding]:
    """C8: a faculty member also listed by another institution over an overlapping period."""
    if not ctx.cross:
        return []
    return crossinst.ghost_faculty(ctx, ctx.cross, _cross_maker(ctx), float(ctx.param("R-GHOST-01", "similarity", 0.7)))


def check_photo_reuse(ctx: Context) -> list[Finding]:
    """C9: an infrastructure photo within max_hamming bits of another institution's photo."""
    if not ctx.cross:
        return []
    return crossinst.photo_reuse(ctx, ctx.cross, _cross_maker(ctx), int(ctx.param("R-PHOTO-01", "max_hamming", 8)))


PHOTO_CATEGORY_LABEL = {"lab": "Lab photo", "classroom": "Classroom photo", "library": "Library photo", "floor_plan": "Floor plan"}


def _photos(ctx: Context) -> list[tuple[dict, dict]]:
    return [(d, ctx.media.get(d["id"], {})) for d in ctx.passed if d["doc_type"] == "infrastructure_photo"]


def check_infra_evidence(ctx: Context) -> list[Finding]:
    """C10: the evidence categories the rule requires (lab, classroom, library, floor plan) are all present.
    A category already reported by C1 as a missing required document is not reported twice."""
    required = ctx.param("R-INFRA-01", "required", ["lab", "classroom", "library", "floor_plan"])
    required_types = {r["doc_type"] for r in ctx.required if r.get("mandatory", True)}
    photo_categories = {m.get("category") for _, m in _photos(ctx)}
    out = []
    for category in required:
        if category == "floor_plan":
            if any(d["doc_type"] == "floor_plan" for d in ctx.passed) or "floor_plan" in required_types:
                continue
        elif category in photo_categories or (not photo_categories and "infrastructure_photo" in required_types):
            continue
        label = PHOTO_CATEGORY_LABEL.get(category, category.replace("_", " ").capitalize())
        have = ", ".join(sorted(PHOTO_CATEGORY_LABEL.get(c, c).lower() for c in photo_categories if c)) or "none"
        out.append(Finding(
            key=f"INFRA_EVIDENCE_MISSING|{ctx.application['code']}|{category}", finding_type="INFRA_EVIDENCE_MISSING",
            rule_code="R-INFRA-01", rule_version=ctx.version("R-INFRA-01"), severity="high",
            title=f"{label} not received",
            detail=f"The infrastructure evidence rule asks for photos of a lab, a classroom and the library, and a floor "
                   f"plan. No {label.lower()} is among the current documents. Photos received: {have}.",
            evidence=[evidence(None, None, "SINGLE", f"Required {label.lower()}", "not received")],
        ))
    return out


def _decimal(value) -> Optional[Decimal]:
    try:
        return Decimal(str(value)) if value is not None else None
    except InvalidOperation:
        return None


def check_area(ctx: Context) -> list[Finding]:
    """C11: room areas add up to the declared total within the tolerance, and the declared total meets the
    minimum. The room table is entered from the floor plan; without one the sum is not checked."""
    code = ctx.application["code"]
    form = first_of_type(ctx, "application_form")
    declared_field = ctx.field(form, "declared_total_area_sqm") if form else None
    if usable(declared_field):
        declared, declared_ev = _decimal(declared_field["field_value"]), evidence(form, declared_field, "A", "Application form, total built-up area")
    else:
        declared = _decimal(ctx.application.get("declared_total_area_sqm"))
        declared_ev = evidence(None, None, "A", "Declared total built-up area", f"{declared} sq m" if declared is not None else None)
    if declared is None:
        return []
    out = []
    tolerance = _decimal(ctx.param("R-AREA-01", "area_tolerance_pct", 1)) or Decimal(1)
    minimum = _decimal(ctx.param("R-AREA-01", "min_area_sqm", 0)) or Decimal(0)
    plan = first_of_type(ctx, "floor_plan")
    if ctx.rooms:
        total = sum((_decimal(r.get("area_sqm")) or (_decimal(r.get("length_m")) or 0) * (_decimal(r.get("width_m")) or 0))
                    for r in ctx.rooms)
        total = Decimal(total).quantize(Decimal("0.01"))
        gap = abs(total - declared)
        if declared > 0 and gap * 100 / declared > tolerance:
            out.append(Finding(
                key=f"AREA_MISMATCH|{code}|total", finding_type="AREA_MISMATCH", rule_code="R-AREA-01",
                rule_version=ctx.version("R-AREA-01"), severity="medium",
                title=f"Room areas add up to {total:,.2f} sq m; the declared total is {declared:,.2f} sq m",
                detail=f"The {len(ctx.rooms)} rooms in the room table add up to {total:,.2f} sq m. The declared total "
                       f"built-up area is {declared:,.2f} sq m ({page_text(declared_field) if usable(declared_field) else 'application record'}), "
                       f"a difference of {gap:,.2f} sq m ({gap * 100 / declared:.1f}%), above the {tolerance}% tolerance. Candidate for review.",
                evidence=[declared_ev, evidence(plan, None, "B", f"Room table, {len(ctx.rooms)} rooms", f"{total:,.2f} sq m")],
            ))
    if minimum and declared < minimum:
        out.append(Finding(
            key=f"AREA_BELOW_MINIMUM|{code}|minimum", finding_type="AREA_BELOW_MINIMUM", rule_code="R-AREA-01",
            rule_version=ctx.version("R-AREA-01"), severity="high",
            title=f"Declared built-up area {declared:,.2f} sq m is below the {minimum:,.0f} sq m minimum",
            detail=f"The declared total built-up area is {declared:,.2f} sq m; the illustrative rule sets a minimum of "
                   f"{minimum:,.0f} sq m. Candidate for review.",
            evidence=[declared_ev],
        ))
    return out


def _months_before(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    m += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, 28)


def check_photo_metadata(ctx: Context) -> list[Finding]:
    """C12: a photo taken (EXIF date) more than max_photo_age_months before the as-of date. A photo with no
    EXIF date is a finding only when the rule sets require_exif."""
    months = int(ctx.param("R-PHOTOAGE-01", "max_photo_age_months", 12))
    require_exif = bool(ctx.param("R-PHOTOAGE-01", "require_exif", False))
    cutoff = _months_before(ctx.as_of, months)
    out = []
    for doc, media in _photos(ctx):
        category = media.get("category") or "other"
        label = PHOTO_CATEGORY_LABEL.get(category, "Infrastructure photo")
        taken = media.get("taken_at")
        if taken:
            taken_day = date.fromisoformat(str(taken)[:10])
            if taken_day >= cutoff:
                continue
            title = f"{label} taken on {taken_day:%d/%m/%Y}, more than {months} months before the as-of date"
            detail = (f"The photo's EXIF data gives the date it was taken as {taken_day:%d/%m/%Y}. The rule asks for photos "
                      f"taken after {cutoff:%d/%m/%Y} ({months} months before the as-of date {ctx.as_of:%d/%m/%Y}). Candidate for review.")
            shown_value = taken_day.strftime("%d/%m/%Y")
        elif require_exif:
            title, detail, shown_value = f"{label} has no date in its EXIF data", \
                "The rule asks for the date a photo was taken, and this file carries none. Candidate for review.", "no EXIF date"
        else:
            continue
        out.append(Finding(
            key=f"PHOTO_METADATA|{ctx.application['code']}|{category if category != 'other' else doc['id'][:8]}",
            finding_type="PHOTO_METADATA", rule_code="R-PHOTOAGE-01", rule_version=ctx.version("R-PHOTOAGE-01"),
            severity="low", title=title, detail=detail,
            evidence=[evidence(doc, None, "SINGLE", f"{label}, date taken", shown_value)],
        ))
    return out


# Check, the rule that switches it on, and the finding types it can produce
CHECKS: list[tuple[str, str, Callable[[Context], list[Finding]], set[str]]] = [
    ("C1", "R-DOC-REQ", check_missing_documents, {"MISSING_DOCUMENT"}),
    ("C2", "R-EXP-01", check_expired, {"EXPIRED_DOCUMENT"}),
    ("C3", "R-DATE-01", check_date_order, {"DATE_ORDER_INVALID"}),
    ("C4", "R-PAIR-01", check_pairs, {"DATE_CONFLICT", "ID_MISMATCH", "COUNT_CONFLICT"}),
    ("C5", "R-OCR-01", check_needs_confirmation, {"FIELD_NEEDS_CONFIRMATION"}),
    ("C6", "R-DUP-01", check_duplicates, {"DUPLICATE_FILE"}),
    ("C7", "R-ID-REUSE", check_reused_identifiers, {"REUSED_IDENTIFIER"}),
    ("C8", "R-GHOST-01", check_ghost_faculty, {"GHOST_FACULTY"}),
    ("C9", "R-PHOTO-01", check_photo_reuse, {"PHOTO_REUSE"}),
    ("C10", "R-INFRA-01", check_infra_evidence, {"INFRA_EVIDENCE_MISSING"}),
    ("C11", "R-AREA-01", check_area, {"AREA_MISMATCH", "AREA_BELOW_MINIMUM"}),
    ("C12", "R-PHOTOAGE-01", check_photo_metadata, {"PHOTO_METADATA"}),
]


def evaluate(ctx: Context, include_cross: bool = True) -> tuple[list[Finding], set[str]]:
    """Every finding the active rules produce, and the finding types whose checks ran."""
    findings, evaluated = [], set()
    for _, rule_code, check, types in CHECKS:
        if rule_code not in ctx.rules:
            continue                          # rule not active on the as-of date: the check does not run
        if types & CROSS_TYPES and (not include_cross or ctx.cross is None):
            continue                          # cross checks not run: their earlier findings are left alone
        evaluated |= types
        findings.extend(check(ctx))
    if not include_cross:
        findings = [f for f in findings if not f.is_cross_institution]
    return findings, evaluated


# ------------------------------------------------------------------------------------------------
# Loading and writing
# ------------------------------------------------------------------------------------------------

def active_rules(as_of: date, rows: Optional[list[dict]] = None) -> dict[str, dict]:
    """The active version of each rule on the as-of date (proofpath.rule_ver, done here in one query)."""
    if rows is None:
        rows = db.table("rules").select("*").eq("status", "active").execute().data or []
    out: dict[str, dict] = {}
    for r in rows:
        if r.get("effective_from") and r["effective_from"] > as_of.isoformat():
            continue
        if r.get("effective_to") and r["effective_to"] < as_of.isoformat():
            continue
        if r["rule_code"] not in out or r["version"] > out[r["rule_code"]]["version"]:
            out[r["rule_code"]] = r
    return out


def load_context(application: dict, include_cross: bool = True) -> Context:
    def documents():
        docs = (db.table("documents").select("*").eq("application_id", application["id"])
                .eq("status", "current").execute().data or [])
        ids = [d["id"] for d in docs]
        if not ids:
            return docs, [], [], []
        fields, media, faculty = parallel(
            lambda: db.table("extracted_fields").select("*").in_("document_id", ids).execute().data or [],
            lambda: db.table("media_assets").select("*").in_("document_id", ids).execute().data or [],
            lambda: db.table("faculty").select("*").in_("document_id", ids).execute().data or [],
        )
        return docs, fields, media, faculty

    as_of, (docs, field_rows, media, faculty), category, doc_types, required, pairs, rules, rooms, cross = parallel(
        as_of_date, documents,
        lambda: db.fetch_one("categories", code=application["category"]) or {},
        lambda: db.fetch_all("document_types"),
        lambda: db.fetch_all("required_documents", category=application["category"]),
        lambda: db.fetch_all("comparison_pairs"),
        lambda: db.table("rules").select("*").eq("status", "active").execute().data or [],
        lambda: db.fetch_all("rooms", application_id=application["id"]),
        lambda: crossinst.load(application) if include_cross else None,
    )
    fields: dict[str, list[dict]] = {}
    for f in field_rows:
        fields.setdefault(f["document_id"], []).append(f)
    return Context(
        application=application, as_of=as_of, documents=docs, fields=fields,
        doc_types={t["code"]: t for t in doc_types}, required=required, pairs=pairs,
        rules=active_rules(as_of, rules), category_label=category.get("label", ""),
        media={m["document_id"]: m for m in media}, faculty=faculty, rooms=rooms, cross=cross,
    )


def _write_evidence(by_finding: dict[str, list[dict]]) -> None:
    """Replace the evidence of these findings in two round trips."""
    if not by_finding:
        return
    db.table("finding_evidence").delete().in_("finding_id", list(by_finding)).execute()
    rows = [{**r, "finding_id": fid} for fid, ev in by_finding.items() for r in ev]
    if rows:
        db.table("finding_evidence").insert(rows).execute()


def has_full_run(application_id: str) -> bool:
    return bool(db.table("validation_runs").select("id").eq("application_id", application_id).eq("mode", "full")
                .limit(1).execute().data)


def run_validation(application_id: str, mode: str = "full", actor: Optional[AuthenticatedUser] = None,
                   trigger: str = "reviewer") -> dict:
    """trigger says what started a full run: "reviewer", "document_replaced" or "value_confirmed"."""
    application = db.fetch_one("applications", id=application_id)
    if not application:
        raise LookupError("Application not found")
    ctx = load_context(application, include_cross=(mode != "preflight"))
    findings, evaluated = evaluate(ctx, include_cross=(mode != "preflight"))
    rule_versions = {code: r["version"] for code, r in sorted(ctx.rules.items())}

    if mode != "full":
        return {"mode": mode, "as_of_date": ctx.as_of.isoformat(), "rule_versions": rule_versions,
                "findings": [asdict(f) for f in findings]}

    run = db.insert("validation_runs", {
        "application_id": application_id, "mode": "full", "as_of_date": ctx.as_of.isoformat(),
        "rule_versions": rule_versions, "started_by": actor.id if actor else None,
    })
    existing = {f["finding_key"]: f for f in db.fetch_all("findings", application_id=application_id)}
    produced = {f.key for f in findings}
    created, reopened, still_open = [], [], []
    evidence_to_write: dict[str, list[dict]] = {}

    for f in findings:
        row = {
            "finding_type": f.finding_type, "rule_code": f.rule_code, "rule_version": f.rule_version,
            "severity": f.severity, "title": f.title, "detail": f.detail,
            "is_cross_institution": f.is_cross_institution, "related_application_id": f.related_application_id,
            "last_run_id": run["id"],
        }
        old = existing.get(f.key)
        if not old:
            new = db.insert("findings", {**row, "finding_key": f.key, "application_id": application_id,
                                         "status": "open", "first_run_id": run["id"]})
            evidence_to_write[new["id"]] = f.evidence
            created.append(f.key)
            continue
        if old["status"] == "auto_closed":
            row["status"] = "open"
            reopened.append(f.key)
        elif old["status"] in UNRESOLVED:
            still_open.append(f.key)
        db.update("findings", old["id"], row)
        # A reviewer's resolved or dismissed finding keeps the evidence the reviewer acted on
        if old["status"] not in ("resolved", "dismissed"):
            evidence_to_write[old["id"]] = f.evidence
    _write_evidence(evidence_to_write)

    # Findings from earlier runs whose condition no longer holds (only for checks that ran this time)
    closed = []
    for key, old in existing.items():
        if key not in produced and old["status"] in UNRESOLVED and old["finding_type"] in evaluated:
            db.update("findings", old["id"], {"status": "auto_closed", "last_run_id": run["id"]})
            closed.append(key)

    summary = {"findings": len(findings), "created": len(created), "reopened": len(reopened),
               "still_open": len(still_open), "auto_closed": len(closed)}
    db.update("validation_runs", run["id"], {"finished_at": datetime.now(timezone.utc).isoformat(), "summary": summary})
    if application["workflow_status"] == "submitted":
        db.update("applications", application_id, {"workflow_status": "under_review"})
    audit.record(actor, "validation_run", "validation_run", run["id"], application_id, {
        **summary, "as_of_date": ctx.as_of.isoformat(), "rule_versions": rule_versions,
        "created_keys": created, "reopened_keys": reopened, "auto_closed_keys": closed, "trigger": trigger,
    })
    return {"mode": "full", "run_id": run["id"], "as_of_date": ctx.as_of.isoformat(),
            "rule_versions": rule_versions, "summary": summary}
