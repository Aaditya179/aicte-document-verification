"""
Case files: one per application, holding its documents, every fact read from them, and the
verdict on each field (verified, conflict or unverified) with the reason.

An institution sees only its own cases. Verifiers, analysts and auditors see all of them.
The administrator manages accounts and has no route to case data.
"""
from collections import Counter
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.security import AuthenticatedUser, require_role

router = APIRouter(prefix="/cases", tags=["Cases"])

CASE_READERS = ["institution", "verifier", "analyst", "auditor"]
STATUSES = ("verified", "conflict", "unverified")


def _counts(case_ids: List[str]) -> Dict[str, Dict[str, int]]:
    if not case_ids:
        return {}
    rows = db.table("checks").select("case_id, status").in_("case_id", case_ids).execute().data or []
    tally = Counter((r["case_id"], r["status"]) for r in rows)
    return {cid: {s: tally[(cid, s)] for s in STATUSES} for cid in case_ids}


def _load_case(case_id: str, user: AuthenticatedUser) -> dict:
    res = db.table("cases").select("*, institutions(id, name, aicte_id, state, city)").eq("id", case_id).limit(1).execute()
    case = res.data[0] if res.data else None
    # A case outside the institution's own scope reads as missing, not forbidden
    if not case or (user.role == "institution" and case["institution_id"] != user.institution_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("")
async def list_cases(user: AuthenticatedUser = Depends(require_role(CASE_READERS))):
    query = db.table("cases").select("*, institutions(name, aicte_id)").order("created_at", desc=True)
    if user.role == "institution":
        query = query.eq("institution_id", user.institution_id)
    cases = query.execute().data or []
    counts = _counts([c["id"] for c in cases])
    return [{**c, "checks": counts.get(c["id"], dict.fromkeys(STATUSES, 0))} for c in cases]


@router.get("/{case_id}")
async def get_case(case_id: str, user: AuthenticatedUser = Depends(require_role(CASE_READERS))):
    case = _load_case(case_id, user)
    documents = db.table("documents").select("id, doc_type, title, sha256, mime_type, page_count, uploaded_at") \
        .eq("case_id", case_id).order("uploaded_at").execute().data or []
    facts = db.table("facts").select("*").eq("case_id", case_id).order("field").execute().data or []
    checks = db.table("checks").select("*").eq("case_id", case_id).order("field").execute().data or []

    by_id = {f["id"]: f for f in facts}
    for check in checks:
        check["facts"] = [by_id[i] for i in check.get("fact_ids") or [] if i in by_id]

    # Patterns across institutions show only to roles that may see other institutions
    patterns = []
    if user.role != "institution":
        patterns = db.table("patterns").select("*").contains("case_ids", [case_id]) \
            .order("detected_at", desc=True).execute().data or []

    return {
        "case": case,
        "documents": documents,
        "checks": checks,
        "summary": {s: sum(1 for c in checks if c["status"] == s) for s in STATUSES},
        "patterns": patterns,
    }


patterns_router = APIRouter(prefix="/patterns", tags=["Patterns"])


@patterns_router.get("")
async def list_patterns(status: str = "open",
                        user: AuthenticatedUser = Depends(require_role(["verifier", "analyst", "auditor"]))):
    query = db.table("patterns").select("*").order("detected_at", desc=True)
    if status != "all":
        query = query.eq("status", status)
    return query.execute().data or []
