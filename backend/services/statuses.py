"""
The four independent statuses of an application (build spec 7.3). They are never collapsed into one
score: a valid signature does not make an application compliant, consistent documents do not make
them genuine, and an unavailable source is not a failure.

Only findings that are open or waiting for evidence count. Before the first full validation run every
status reads "Not run yet". Within a status the worst state wins, in the order listed. Administrative
status is separate and always "Pending (authorised AICTE official)".
"""
from typing import Optional

from services.registry_adapter import REGISTRY_DOCUMENTS

CONFLICT_TYPES = {"DATE_CONFLICT", "ID_MISMATCH", "COUNT_CONFLICT", "DATE_ORDER_INVALID"}
CROSS_TYPES = {"REUSED_IDENTIFIER", "GHOST_FACULTY", "PHOTO_REUSE"}
COMPLIANCE_TYPES = {"MISSING_DOCUMENT", "EXPIRED_DOCUMENT", "AREA_MISMATCH", "AREA_BELOW_MINIMUM", "INFRA_EVIDENCE_MISSING"}
UNRESOLVED = ("open", "evidence_requested")

ADMINISTRATIVE = "Pending (authorised AICTE official)"


def _status(key: str, label: str, value: str, tone: str, reasons: Optional[list[str]] = None) -> dict:
    return {"key": key, "label": label, "value": value, "tone": tone, "reasons": reasons or []}


def _doc_label(d: dict) -> str:
    return d.get("label") or (d.get("doc_type") or "document").replace("_", " ").capitalize()


def _authenticity(documents: list[dict], checks: list[dict], problem_findings: list[str]) -> dict:
    """The latest check per document and method decides that method's state; methods never override
    each other, and the worst state over all documents wins. An unavailable source is Pending, never
    a failure. Every reason names the document and the method, and a MOCK source says so."""
    labels = {d["id"]: _doc_label(d) for d in documents}
    latest: dict[tuple, dict] = {}
    for c in sorted(checks, key=lambda c: c.get("checked_at") or ""):
        if c["method"] in ("SIGNATURE", "REGISTRY", "MANUAL"):
            latest[(c["document_id"], c["method"])] = c

    def line(c: dict, what: str) -> str:
        source = {"SIGNATURE": "signature", "REGISTRY": "issuer registry" + (" (MOCK)" if c.get("is_mock") else ""),
                  "MANUAL": f"manual check with {c.get('source') or 'the issuer'}"}[c["method"]]
        return f"{labels.get(c['document_id'], 'A document')}, {source}: {what}"

    bad_signature = [c for c in latest.values() if c["method"] == "SIGNATURE" and c.get("status") in ("invalid", "untrusted_chain")]
    bad_source = [c for c in latest.values() if (c["method"], c.get("status")) in (("REGISTRY", "mismatch"), ("MANUAL", "manual_not_confirmed"))]
    waiting = [c for c in latest.values() if (c["method"], c.get("status")) == ("MANUAL", "manual_pending")]
    unavailable = [c for c in latest.values() if (c["method"], c.get("status")) == ("REGISTRY", "unavailable")]
    good = [c for c in latest.values() if (c["method"], c.get("status")) in
            (("SIGNATURE", "valid"), ("REGISTRY", "match"), ("MANUAL", "manual_confirmed"))]

    if bad_signature or bad_source:
        value = ("Signature invalid or source mismatch" if bad_signature and bad_source
                 else "Signature invalid" if bad_signature else "Source mismatch")
        reasons = [line(c, "signature " + c["status"].replace("_", " ")) for c in bad_signature]
        reasons += [line(c, "values differ" if c["method"] == "REGISTRY" else "the issuer did not confirm it") for c in bad_source]
        return _status("authenticity", "Authenticity", value, "conflict", reasons + problem_findings)
    if waiting:
        return _status("authenticity", "Authenticity", "Manual verification pending", "pending",
                       [line(c, "asked, waiting for an answer") for c in waiting])
    if unavailable:
        mock = " (MOCK source)" if all(c.get("is_mock") for c in unavailable) else ""
        return _status("authenticity", "Authenticity", "Pending (source unavailable)" + mock, "pending",
                       [line(c, "source unavailable, not a failure") for c in unavailable])
    if good:
        kinds = {c["method"] == "SIGNATURE" for c in good}
        value = "Signature valid or source verified" if len(kinds) == 2 else "Signature valid" if True in kinds else "Source verified"
        if all(c.get("is_mock") for c in good):
            value += " (MOCK source)"
        checked = {c["document_id"] for c in good}
        reasons = [line(c, "matches" if c["method"] == "REGISTRY" else "valid" if c["method"] == "SIGNATURE" else "confirmed") for c in good]
        # Documents an issuer registry holds that no method has checked yet
        unchecked = sorted(_doc_label(d) for d in documents if d["doc_type"] in REGISTRY_DOCUMENTS
                           and d["id"] not in checked and d["id"] not in {k[0] for k in latest})
        if unchecked:
            reasons.append(f"Not checked yet: {', '.join(unchecked)}")
        return _status("authenticity", "Authenticity", value, "ok", reasons)
    return _status("authenticity", "Authenticity", "Not yet verified", "neutral")


def compute(has_run: bool, findings: list[dict], documents: list[dict], fields: list[dict],
            required_templates: set[tuple[str, str]], checks: list[dict], rooms_entered: bool = True) -> dict:
    """
    findings: every finding of the application; documents: current documents; fields: their extracted
    fields (with doc_type added); required_templates: (doc_type, field_name) marked required;
    checks: verification_checks rows of the current documents; rooms_entered: whether the room table
    for the floor-plan arithmetic (C11) has been entered.
    """
    if not has_run:
        names = (("integrity", "Integrity"), ("consistency", "Consistency"), ("authenticity", "Authenticity"), ("compliance", "Compliance"))
        return {"statuses": [_status(k, l, "Not run yet", "neutral") for k, l in names], "administrative": ADMINISTRATIVE}

    open_ = [f for f in findings if f["status"] in UNRESOLVED]
    of_type = lambda types: [f["title"] for f in open_ if f["finding_type"] in types]  # noqa: E731

    # Integrity
    failed = [d for d in documents if d["integrity_status"] == "failed"]
    duplicates = of_type({"DUPLICATE_FILE"})
    if failed:
        integrity = _status("integrity", "Integrity", "File check failed", "conflict",
                            [f"{d.get('original_name') or 'A file'}: {d.get('integrity_note') or 'failed the file check'}" for d in failed])
    elif duplicates:
        integrity = _status("integrity", "Integrity", "Duplicate file detected", "pending", duplicates)
    else:
        integrity = _status("integrity", "Integrity", "Passed", "ok")

    # Consistency
    conflicts, cross = of_type(CONFLICT_TYPES), of_type(CROSS_TYPES)
    unconfirmed = [f for f in fields if f.get("review_state") == "needs_confirmation"]
    if conflicts:
        consistency = _status("consistency", "Consistency", "Conflict detected", "conflict", conflicts)
    elif cross:
        consistency = _status("consistency", "Consistency", "Cross-application flag", "conflict", cross)
    elif unconfirmed:
        consistency = _status("consistency", "Consistency", "Inconclusive", "pending",
                              [f"{len(unconfirmed)} value{'s' if len(unconfirmed) != 1 else ''} waiting for confirmation"])
    else:
        consistency = _status("consistency", "Consistency", "Consistent", "ok")

    authenticity = _authenticity(documents, checks, of_type({"SIGNATURE_INVALID", "REGISTRY_MISMATCH"}))

    # Compliance
    compliance_findings = of_type(COMPLIANCE_TYPES)
    present = {(f["doc_type"], f["field_name"]) for f in fields if f.get("field_value") is not None}
    uploaded_types = {d["doc_type"] for d in documents if d["integrity_status"] == "passed"}
    not_extracted = sorted(f"{t.replace('_', ' ')}: {n.replace('_', ' ')}" for t, n in required_templates
                           if t in uploaded_types and (t, n) not in present)
    if compliance_findings:
        compliance = _status("compliance", "Compliance", "Review required", "conflict", compliance_findings)
    elif not_extracted or not rooms_entered:
        reasons = [f"Could not be read: {', '.join(not_extracted)}"] if not_extracted else []
        if not rooms_entered:
            reasons.append("Room table not entered, so room areas cannot be added up")
        compliance = _status("compliance", "Compliance", "Not assessable", "pending", reasons)
    else:
        compliance = _status("compliance", "Compliance", "Meets configured checks", "ok")

    return {"statuses": [integrity, consistency, authenticity, compliance], "administrative": ADMINISTRATIVE}
