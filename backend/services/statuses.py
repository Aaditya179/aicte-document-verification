"""
The four independent statuses of an application (build spec 7.3). They are never collapsed into one
score: a valid signature does not make an application compliant, consistent documents do not make
them genuine, and an unavailable source is not a failure.

Only findings that are open or waiting for evidence count. Before the first full validation run every
status reads "Not run yet". Within a status the worst state wins, in the order listed. Administrative
status is separate and always "Pending (authorised AICTE official)".
"""
from typing import Optional

CONFLICT_TYPES = {"DATE_CONFLICT", "ID_MISMATCH", "COUNT_CONFLICT", "DATE_ORDER_INVALID"}
CROSS_TYPES = {"REUSED_IDENTIFIER", "GHOST_FACULTY", "PHOTO_REUSE"}
COMPLIANCE_TYPES = {"MISSING_DOCUMENT", "EXPIRED_DOCUMENT", "AREA_MISMATCH", "AREA_BELOW_MINIMUM", "INFRA_EVIDENCE_MISSING"}
UNRESOLVED = ("open", "evidence_requested")

ADMINISTRATIVE = "Pending (authorised AICTE official)"


def _status(key: str, label: str, value: str, tone: str, reasons: Optional[list[str]] = None) -> dict:
    return {"key": key, "label": label, "value": value, "tone": tone, "reasons": reasons or []}


def compute(has_run: bool, findings: list[dict], documents: list[dict], fields: list[dict],
            required_templates: set[tuple[str, str]], checks: list[dict]) -> dict:
    """
    findings: every finding of the application; documents: current documents; fields: their extracted
    fields (with doc_type added); required_templates: (doc_type, field_name) marked required;
    checks: verification_checks rows of the current documents.
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

    # Authenticity: the latest check per document and method decides
    latest: dict[tuple, dict] = {}
    for c in sorted(checks, key=lambda c: c.get("checked_at") or ""):
        latest[(c["document_id"], c["method"])] = c
    auth = [c for (_, method), c in latest.items() if method in ("SIGNATURE", "REGISTRY", "MANUAL")]
    statuses = {(c["method"], c.get("status")) for c in auth}
    mock = any(c.get("is_mock") for c in auth)
    suffix = " (MOCK source)" if mock else ""
    if ("SIGNATURE", "invalid") in statuses or ("SIGNATURE", "untrusted_chain") in statuses or ("REGISTRY", "mismatch") in statuses:
        authenticity = _status("authenticity", "Authenticity", "Signature invalid or source mismatch", "conflict", of_type({"SIGNATURE_INVALID", "REGISTRY_MISMATCH"}))
    elif ("MANUAL", "manual_pending") in statuses:
        authenticity = _status("authenticity", "Authenticity", "Manual verification pending", "pending")
    elif ("REGISTRY", "unavailable") in statuses:
        authenticity = _status("authenticity", "Authenticity", "Pending (source unavailable)" + suffix, "pending")
    elif ("SIGNATURE", "valid") in statuses or ("REGISTRY", "match") in statuses or ("MANUAL", "manual_confirmed") in statuses:
        authenticity = _status("authenticity", "Authenticity", "Signature valid or source verified" + suffix, "ok")
    else:
        authenticity = _status("authenticity", "Authenticity", "Not yet verified", "neutral")

    # Compliance
    compliance_findings = of_type(COMPLIANCE_TYPES)
    present = {(f["doc_type"], f["field_name"]) for f in fields if f.get("field_value") is not None}
    uploaded_types = {d["doc_type"] for d in documents if d["integrity_status"] == "passed"}
    not_extracted = sorted(f"{t.replace('_', ' ')}: {n.replace('_', ' ')}" for t, n in required_templates
                           if t in uploaded_types and (t, n) not in present)
    if compliance_findings:
        compliance = _status("compliance", "Compliance", "Review required", "conflict", compliance_findings)
    elif not_extracted:
        compliance = _status("compliance", "Compliance", "Not assessable", "pending",
                             [f"Could not be read: {', '.join(not_extracted)}"])
    else:
        compliance = _status("compliance", "Compliance", "Meets configured checks", "ok")

    return {"statuses": [integrity, consistency, authenticity, compliance], "administrative": ADMINISTRATIVE}
