"""
Regulation clauses: the library a rule administrator keeps, the clauses behind a finding, and a draft
explanation of a finding for the reviewer (services/clauses.py, ASSUMPTIONS A41).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.access import application_for
from core.db import db
from core.ratelimit import rate_limit
from core.security import AuthenticatedUser, require_role
from services import audit, casefile, clauses as clause_service

router = APIRouter(tags=["Clauses"])

READERS = ["reviewer", "rule_admin"]
ADMIN = ["rule_admin"]

NOT_READY = "The clause library is not set up yet (migration 0009)"


def _library() -> list[dict]:
    library = clause_service.load()
    if library is None:
        raise HTTPException(status_code=503, detail=NOT_READY)
    return library


def _finding_and_rule(user: AuthenticatedUser, finding_id: str) -> tuple[dict, Optional[dict]]:
    finding = db.fetch_one("findings", id=finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    application_for(user, finding["application_id"])
    finding = next(f for f in casefile.findings_for(finding["application_id"]) if f["id"] == finding_id)
    rule = None
    if finding.get("rule_code"):
        filters = {"rule_code": finding["rule_code"]}
        if finding.get("rule_version"):
            filters["version"] = finding["rule_version"]
        rule = db.fetch_one("rules", **filters)
    return finding, rule


def _rule_view(rule: Optional[dict]) -> Optional[dict]:
    if not rule:
        return None
    return {k: rule.get(k) for k in ("rule_code", "version", "title", "description", "source_reference", "clause", "note")}


@router.get("/findings/{finding_id}/clauses")
def finding_clauses(finding_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    finding, rule = _finding_and_rule(user, finding_id)
    found = clause_service.retrieve(finding, rule, _library())
    return {"rule": _rule_view(rule), "clauses": [clause_service.public(c) for c in found]}


@router.post("/findings/{finding_id}/explanation", dependencies=[Depends(rate_limit("20/minute", "explanation"))])
def finding_explanation(finding_id: str, user: AuthenticatedUser = Depends(require_role(READERS))):
    """A draft of two or three sentences for the reviewer. Not stored on the finding; the audit trail
    records that it was drafted, how, and from which clauses."""
    finding, rule = _finding_and_rule(user, finding_id)
    found = clause_service.retrieve(finding, rule, _library())
    draft = clause_service.explain(finding, rule, found)
    audit.record(user, "explanation_drafted", "finding", finding_id, finding["application_id"],
                 {"by": draft["by"], "clause_refs": draft["clause_refs"]})
    return {"rule": _rule_view(rule), "clauses": [clause_service.public(c) for c in found], "explanation": draft}


@router.get("/admin/clauses", tags=["Settings"])
def list_clauses(user: AuthenticatedUser = Depends(require_role(READERS))):
    return [clause_service.public(c) for c in _library()]


class NewClause(BaseModel):
    clause_ref: str = Field(..., min_length=2, max_length=40)
    source: str = Field(..., min_length=3, max_length=200)
    heading: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=20, max_length=4000)
    rule_codes: list[str] = Field(default_factory=list, max_length=20)
    is_illustrative: bool = True
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/admin/clauses", tags=["Settings"], status_code=201)
def add_clause(body: NewClause, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """Add a clause to the library. Clauses are kept, not edited; the audit trail records who added which."""
    library = _library()
    ref = body.clause_ref.strip()
    if any(c["clause_ref"].lower() == ref.lower() for c in library):
        raise HTTPException(status_code=409, detail=f"Clause {ref} is already in the library")
    known = {r["rule_code"] for r in db.table("rules").select("rule_code").execute().data or []}
    codes = sorted({c.strip().upper() for c in body.rule_codes if c.strip()})
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"No rule is called {', '.join(unknown)}")
    row = db.table("regulation_clauses").insert({
        "clause_ref": ref, "source": body.source.strip(), "heading": body.heading.strip(), "body": body.body.strip(),
        "rule_codes": codes, "is_illustrative": body.is_illustrative, "created_by": user.id,
    }).execute().data[0]
    audit.record(user, "clause_added", "regulation_clause", row["id"], None,
                 {"clause_ref": ref, "rule_codes": codes, "is_illustrative": body.is_illustrative, "reason": body.reason.strip()})
    return clause_service.public(row)
