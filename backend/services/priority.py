"""
Review priority (build spec 7.4). It only orders the queue and never changes a status.

score = min(100, sum of the weights of unresolved findings
                 + 5 for each unresolved finding beyond the first
                 + 20 if the review deadline is within 7 days, or 10 if within 14 days)

Bands: High 60 and above, Medium 30 to 59, Low below 30. The composition (each term and what it adds)
is returned so the screen can show how the number was reached.
"""
from datetime import date
from typing import Optional

WEIGHT_KEY = {
    "MISSING_DOCUMENT": "missing_document",
    "EXPIRED_DOCUMENT": "expired_document",
    "INFRA_EVIDENCE_MISSING": "infra_evidence_missing",
    "REUSED_IDENTIFIER": "cross_institution",
    "GHOST_FACULTY": "cross_institution",
    "PHOTO_REUSE": "cross_institution",
    "DATE_CONFLICT": "conflict",
    "ID_MISMATCH": "conflict",
    "COUNT_CONFLICT": "conflict",
    "DATE_ORDER_INVALID": "conflict",
    "AREA_MISMATCH": "area",
    "AREA_BELOW_MINIMUM": "area",
    "SIGNATURE_INVALID": "signature_or_registry",
    "REGISTRY_MISMATCH": "signature_or_registry",
    "FIELD_NEEDS_CONFIRMATION": "needs_confirmation",
    "DUPLICATE_FILE": "duplicate",
    "PHOTO_METADATA": "metadata",
    "METADATA_ANOMALY": "metadata",
}

WEIGHT_LABEL = {
    "missing_document": "Missing document",
    "expired_document": "Expired document",
    "infra_evidence_missing": "Infrastructure evidence missing",
    "cross_institution": "Cross-institution flag",
    "conflict": "Conflict between documents",
    "area": "Area finding",
    "signature_or_registry": "Signature or registry problem",
    "needs_confirmation": "Value needs confirmation",
    "duplicate": "Duplicate file",
    "metadata": "File or photo metadata",
}

UNRESOLVED = ("open", "evidence_requested")


def band(score: int) -> str:
    return "High" if score >= 60 else "Medium" if score >= 30 else "Low"


def compute(findings: list[dict], weights: dict[str, int], review_deadline: Optional[str], as_of: date) -> dict:
    open_ = [f for f in findings if f["status"] in UNRESOLVED]
    terms: dict[str, dict] = {}
    for f in open_:
        key = WEIGHT_KEY.get(f["finding_type"])
        if not key:
            continue
        t = terms.setdefault(key, {"key": key, "label": WEIGHT_LABEL[key], "weight": weights.get(key, 0), "count": 0})
        t["count"] += 1
    composition = []
    for t in sorted(terms.values(), key=lambda t: -t["weight"] * t["count"]):
        composition.append({**t, "contribution": t["weight"] * t["count"]})

    extra = max(0, len(open_) - 1) * 5
    if extra:
        composition.append({"key": "additional", "label": "Each unresolved finding beyond the first", "weight": 5,
                            "count": len(open_) - 1, "contribution": extra})

    days_left = None
    if review_deadline:
        days_left = (date.fromisoformat(str(review_deadline)[:10]) - as_of).days
        bonus = 20 if days_left <= 7 else 10 if days_left <= 14 else 0
        if bonus:
            composition.append({"key": "deadline", "label": f"Review due in {days_left} day{'s' if abs(days_left) != 1 else ''}"
                                if days_left >= 0 else f"Review {-days_left} day{'s' if days_left != -1 else ''} overdue",
                                "weight": bonus, "count": 1, "contribution": bonus})

    raw = sum(t["contribution"] for t in composition)
    score = min(100, raw)
    return {"score": score, "band": band(score), "raw": raw, "capped": raw > 100,
            "unresolved": len(open_), "days_to_deadline": days_left, "composition": composition}
