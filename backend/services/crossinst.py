"""
The Cross-Institution Engine (build spec section 8): checks C7 to C9, run as part of a full validation.

Only applications of *other* institutions are compared, and only ones that have been submitted (a draft
is not yet a claim). Results are for reviewers only: an institution never sees a cross-institution
finding, and evidence cannot be requested on one, since that would tell it about another
institution's records.

  C7 REUSED_IDENTIFIER  the same certificate, NOC, registration or survey number in another application
  C8 GHOST_FACULTY      the same faculty member (same masked ID, or a similar name with the same
                        qualification) listed by another institution over an overlapping period
  C9 PHOTO_REUSE        an infrastructure photo within max_hamming bits of another institution's photo

Findings say what matches and where, and that it is a candidate for review, never what it implies.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from rapidfuzz import fuzz

from core.db import db, parallel
from services import normalise
from services.extraction import hamming

# (document type, field) -> the kind of identifier it holds. A kind is compared across institutions.
IDENTIFIER_KINDS = {
    ("approval_certificate", "certificate_no"): "certificate_no",
    ("fire_noc", "noc_no"): "fire_noc_no",
    ("application_form", "declared_fire_noc_no"): "fire_noc_no",
    ("land_document", "registration_no"): "registration_no",
    ("land_document", "survey_no"): "survey_no",
    ("application_form", "survey_no"): "survey_no",
}
KIND_LABEL = {
    "certificate_no": "Approval certificate number",
    "fire_noc_no": "Fire NOC number",
    "registration_no": "Land registration number",
    "survey_no": "Land survey number",
}
CROSS_DOC_TYPES = {"faculty_list", "infrastructure_photo"} | {t for t, _ in IDENTIFIER_KINDS}
PHOTO_LABEL = {"lab": "lab", "classroom": "classroom", "library": "library", "other": "other"}


@dataclass
class CrossData:
    """What other institutions' submitted applications claim, joined to their documents and applications."""
    applications: dict[str, dict] = field(default_factory=dict)        # id -> application (with institution)
    documents: dict[str, dict] = field(default_factory=dict)           # id -> current, file-checked document
    faculty: list[dict] = field(default_factory=list)
    photos: list[dict] = field(default_factory=list)                   # media_assets rows with a phash
    identifiers: list[dict] = field(default_factory=list)              # extracted_fields rows of IDENTIFIER_KINDS

    def application_of(self, document_id: str) -> dict:
        return self.applications[self.documents[document_id]["application_id"]]


def load(application: dict) -> CrossData:
    """Five queries at once. At prototype scale every other claim is read and compared in Python; a large
    deployment would push the matching into SQL (see ASSUMPTIONS.md)."""
    names = sorted({f for _, f in IDENTIFIER_KINDS})
    apps, docs, faculty, media, fields, institutions = parallel(
        lambda: db.table("applications").select("id,code,institution_id,workflow_status")
                  .neq("institution_id", application["institution_id"]).neq("workflow_status", "draft").execute().data or [],
        lambda: db.table("documents").select("id,application_id,doc_type,original_name,version,status,mime")
                  .eq("status", "current").eq("integrity_status", "passed").in_("doc_type", sorted(CROSS_DOC_TYPES))
                  .execute().data or [],
        lambda: db.table("faculty").select("*").neq("institution_id", application["institution_id"]).execute().data or [],
        lambda: db.table("media_assets").select("document_id,category,phash").execute().data or [],
        lambda: db.table("extracted_fields").select("id,document_id,field_name,field_value,original_value,page_number,review_state")
                  .in_("field_name", names).execute().data or [],
        lambda: db.table("institutions").select("id,code,name").execute().data or [],
    )
    by_institution = {i["id"]: i for i in institutions}
    out = CrossData(applications={a["id"]: {**a, "institution": by_institution.get(a["institution_id"], {})} for a in apps})
    out.documents = {d["id"]: d for d in docs if d["application_id"] in out.applications}
    out.faculty = [f for f in faculty if f.get("document_id") in out.documents]
    out.photos = [m for m in media if m.get("phash") and m["document_id"] in out.documents
                  and out.documents[m["document_id"]]["doc_type"] == "infrastructure_photo"]
    out.identifiers = [f for f in fields if f["document_id"] in out.documents
                       and (out.documents[f["document_id"]]["doc_type"], f["field_name"]) in IDENTIFIER_KINDS]
    return out


def _evidence(document: dict, page: Optional[int], role: str, label: str, value: str) -> dict:
    return {"document_id": document["id"], "page_number": page, "role": role, "label": label, "shown_value": value}


def _other(app: dict) -> str:
    inst = app.get("institution") or {}
    return f"{inst.get('name') or 'another institution'} ({app['code']})"


# ------------------------------------------------------------------------------------------------
# C7 Reused identifiers
# ------------------------------------------------------------------------------------------------

def reused_identifiers(ctx, cross: CrossData, make) -> list:
    """One finding per kind of identifier and other application."""
    from services.validation import usable  # the same notion of a usable value as the other checks

    ours: dict[str, tuple[str, dict, dict]] = {}       # kind -> (key, field, document)
    for doc in ctx.passed:
        for f in ctx.fields.get(doc["id"], []):
            kind = IDENTIFIER_KINDS.get((doc["doc_type"], f["field_name"]))
            if kind and usable(f) and kind not in ours:
                ours[kind] = (normalise.identifier_key(f["field_value"]), f, doc)

    matched: dict[tuple[str, str], tuple[dict, dict]] = {}   # (kind, other application id) -> (their field, document)
    for f in cross.identifiers:
        if f.get("review_state") == "needs_confirmation" or not f.get("field_value"):
            continue
        doc = cross.documents[f["document_id"]]
        kind = IDENTIFIER_KINDS[(doc["doc_type"], f["field_name"])]
        if kind in ours and normalise.identifier_key(f["field_value"]) == ours[kind][0]:
            matched.setdefault((kind, doc["application_id"]), (f, doc))

    out = []
    for (kind, other_id), (theirs, their_doc) in sorted(matched.items(), key=lambda m: (m[0][0], cross.applications[m[0][1]]["code"])):
        other = cross.applications[other_id]
        _, mine, my_doc = ours[kind]
        label = KIND_LABEL[kind]
        mine_shown, theirs_shown = mine.get("original_value") or mine["field_value"], theirs.get("original_value") or theirs["field_value"]
        out.append(make(
            key=f"REUSED_IDENTIFIER|{ctx.application['code']}|{other['code']}|{kind}", finding_type="REUSED_IDENTIFIER",
            rule_code="R-ID-REUSE", severity="medium",
            title=f"{label} {mine_shown} also appears in {other['code']}",
            detail=f"The {ctx.label(my_doc['doc_type']).lower()} of this application gives {label.lower()} {mine_shown} "
                   f"(page {mine.get('page_number') or 'not known'}). The {ctx.label(their_doc['doc_type']).lower()} in the "
                   f"application of {_other(other)} gives {theirs_shown} (page {theirs.get('page_number') or 'not known'}). "
                   "Candidate for review.",
            evidence=[_evidence(my_doc, mine.get("page_number"), "A", f"This application, {ctx.label(my_doc['doc_type']).lower()}", mine_shown),
                      _evidence(their_doc, theirs.get("page_number"), "B", f"{other['code']}, {ctx.label(their_doc['doc_type']).lower()}", theirs_shown)],
            related_application_id=other_id,
        ))
    return out


# ------------------------------------------------------------------------------------------------
# C8 Ghost faculty
# ------------------------------------------------------------------------------------------------

def _qualification(value: Optional[str]) -> str:
    return "".join((value or "").lower().replace(".", " ").split())


def _period(row: dict) -> tuple[date, date]:
    start = date.fromisoformat(row["period_start"]) if row.get("period_start") else date.min
    end = date.fromisoformat(row["period_end"]) if row.get("period_end") else date.max   # empty end: still there
    return start, end


def overlaps(a: dict, b: dict) -> bool:
    (s1, e1), (s2, e2) = _period(a), _period(b)
    return s1 <= e2 and s2 <= e1


def faculty_match(a: dict, b: dict, similarity: float) -> Optional[str]:
    """Why two faculty rows may be one person, or None. Spec 8: same masked ID, or a similar name with an
    identical qualification; and in both cases overlapping periods."""
    if not overlaps(a, b):
        return None
    if a.get("masked_id") and a["masked_id"] == b.get("masked_id"):
        return f"the same ID {a['masked_id']}"
    score = fuzz.token_sort_ratio(a.get("name_norm") or "", b.get("name_norm") or "")
    if score >= similarity * 100 and _qualification(a.get("qualification")) and \
            _qualification(a.get("qualification")) == _qualification(b.get("qualification")):
        return f"a name {round(score)}% similar and the same qualification ({a.get('qualification')})"
    return None


def _when(row: dict) -> str:
    start = date.fromisoformat(row["period_start"]).strftime("%d/%m/%Y") if row.get("period_start") else "not given"
    end = date.fromisoformat(row["period_end"]).strftime("%d/%m/%Y") if row.get("period_end") else "now"
    return f"{start} to {end}"


def ghost_faculty(ctx, cross: CrossData, make, similarity: float) -> list:
    """One finding per faculty member of this application and other application."""
    out, seen = [], set()
    for mine in sorted(ctx.faculty, key=lambda r: r.get("faculty_code") or ""):
        for theirs in cross.faculty:
            other = cross.application_of(theirs["document_id"])
            key = f"GHOST_FACULTY|{ctx.application['code']}|{other['code']}|{mine.get('faculty_code')}"
            if key in seen:
                continue
            why = faculty_match(mine, theirs, similarity)
            if not why:
                continue
            seen.add(key)
            my_doc = next((d for d in ctx.passed if d["id"] == mine["document_id"]), None)
            their_doc = cross.documents[theirs["document_id"]]
            if not my_doc:
                continue
            out.append(make(
                key=key, finding_type="GHOST_FACULTY", rule_code="R-GHOST-01", severity="medium",
                # The title stays free of names: list views show masked IDs only (spec 8, privacy)
                title=f"Faculty member {mine.get('faculty_code')} ({mine.get('masked_id') or 'no ID'}) may also be listed by {other['code']}",
                detail=f"This faculty list names {mine['name_raw']}, {mine.get('qualification') or 'qualification not given'}, "
                       f"{_when(mine)} (page {mine.get('page_number') or 'not known'}). The faculty list of {_other(other)} "
                       f"names {theirs['name_raw']}, {theirs.get('qualification') or 'qualification not given'}, {_when(theirs)} "
                       f"(page {theirs.get('page_number') or 'not known'}): {why}, over overlapping periods. "
                       "Candidate for review, not proof that it is the same person.",
                evidence=[_evidence(my_doc, mine.get("page_number"), "A", "This application, faculty list",
                                    f"{mine['name_raw']}, {mine.get('qualification') or '—'}, {mine.get('masked_id') or 'no ID'}, {_when(mine)}"),
                          _evidence(their_doc, theirs.get("page_number"), "B", f"{other['code']}, faculty list",
                                    f"{theirs['name_raw']}, {theirs.get('qualification') or '—'}, {theirs.get('masked_id') or 'no ID'}, {_when(theirs)}")],
                related_application_id=other["id"],
            ))
    return out


# ------------------------------------------------------------------------------------------------
# C9 Photo reuse
# ------------------------------------------------------------------------------------------------

def photo_reuse(ctx, cross: CrossData, make, max_hamming: int) -> list:
    """One finding per other application, for the closest pair of photos within max_hamming bits."""
    ours = [(d, ctx.media[d["id"]]) for d in ctx.passed
            if d["doc_type"] == "infrastructure_photo" and ctx.media.get(d["id"], {}).get("phash")]
    best: dict[str, tuple[int, dict, dict, dict]] = {}       # other application id -> (distance, our doc, our media, their media)
    for doc, media in ours:
        for theirs in cross.photos:
            distance = hamming(media["phash"], theirs["phash"])
            if distance > max_hamming:
                continue
            other_id = cross.documents[theirs["document_id"]]["application_id"]
            if other_id not in best or distance < best[other_id][0]:
                best[other_id] = (distance, doc, media, theirs)

    out = []
    for other_id, (distance, doc, media, theirs) in sorted(best.items(), key=lambda b: cross.applications[b[0]]["code"]):
        other = cross.applications[other_id]
        their_doc = cross.documents[theirs["document_id"]]
        mine_label = PHOTO_LABEL.get(media.get("category") or "", "infrastructure")
        their_label = PHOTO_LABEL.get(theirs.get("category") or "", "infrastructure")
        out.append(make(
            key=f"PHOTO_REUSE|{ctx.application['code']}|{other['code']}", finding_type="PHOTO_REUSE",
            rule_code="R-PHOTO-01", severity="medium",
            title=f"The {mine_label} photo closely matches a photo in {other['code']}",
            detail=f"The {mine_label} photo of this application ({doc.get('original_name')}) and the {their_label} photo of "
                   f"{_other(other)} ({their_doc.get('original_name')}) have visual fingerprints {distance} of 64 bits apart "
                   f"(the rule flags {max_hamming} or fewer). A resized or re-saved copy of a photo stays this close. "
                   "Candidate for review.",
            evidence=[_evidence(doc, None, "A", f"This application, {mine_label} photo", f"fingerprint {media['phash']}"),
                      _evidence(their_doc, None, "B", f"{other['code']}, {their_label} photo", f"fingerprint {theirs['phash']}")],
            related_application_id=other_id,
        ))
    return out
