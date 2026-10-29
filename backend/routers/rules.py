"""Rules: versions, the lifecycle with four-eyes approval, impact preview and drafting from text (build spec 9 and 11)."""
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db, parallel
from core.ratelimit import rate_limit
from core.security import AuthenticatedUser, require_role
from services import audit, rules as service

router = APIRouter(prefix="/rules", tags=["Rules"])

ADMIN = ["rule_admin"]


class RuleChanges(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    params: Optional[dict[str, Any]] = None
    severity: Optional[str] = None
    effective_from: Optional[date] = None
    source_reference: Optional[str] = Field(None, max_length=300)
    clause: Optional[str] = Field(None, max_length=4000)


class NewVersion(RuleChanges):
    from_rule_id: str
    reason: str = Field(..., min_length=3, max_length=1000)


class Reason(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class Activate(Reason):
    effective_from: Optional[date] = None


class DraftFromText(BaseModel):
    text: str = Field(..., min_length=20, max_length=6000)
    source_reference: str = Field(..., min_length=3, max_length=300)


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except service.RuleError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)


def _with_names(rows: list[dict]) -> list[dict]:
    ids = list({r[k] for r in rows for k in ("created_by", "approved_by") if r.get(k)})
    names = {m["user_id"]: m["full_name"] for m in (db.table("members").select("user_id,full_name").in_("user_id", ids)
                                                    .execute().data or [])} if ids else {}
    return [{**r, "created_by_name": names.get(r.get("created_by")), "approved_by_name": names.get(r.get("approved_by")),
             "check": service.check_id(r["rule_code"]), "finding_types": sorted(service.finding_types(r["rule_code"]))} for r in rows]


def _record(user: AuthenticatedUser, event: str, rule: dict, **detail) -> None:
    audit.record(user, event, "rule", rule["id"], None,
                 {"rule_code": rule["rule_code"], "version": rule["version"], "status": rule["status"], **detail})


@router.get("")
def list_rules(user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rows = db.table("rules").select("*").order("rule_code").order("version", desc=True).execute().data or []
    return _with_names(rows)


@router.get("/schema")
def rule_schema(user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """What each check type's params may hold, for the editor."""
    return {"params": service.PARAMS, "severities": list(service.SEVERITIES)}


@router.get("/{rule_id}")
def get_rule(rule_id: str, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.get, rule_id)
    versions, events = parallel(
        lambda: service.versions_of(rule["rule_code"]),
        lambda: db.table("audit_events").select("id,event_type,actor_role,actor_id,detail,created_at").eq("entity_type", "rule")
                  .eq("entity_id", rule_id).order("id", desc=True).execute().data or [],
    )
    names = {m["user_id"]: m["full_name"] for m in db.fetch_all("members", role="rule_admin")}
    return {"rule": _with_names([rule])[0], "versions": _with_names(versions),
            "history": [{**e, "actor_name": names.get(e.get("actor_id"))} for e in events],
            "params_schema": service.PARAMS.get(rule["check_type"], {})}


@router.post("", status_code=201)
def create_version(body: NewVersion, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """A draft as the next version of an existing rule. New rule codes are not created here: each code
    switches on a check that exists in code (CLAUDE.md, Part 2)."""
    base = _call(service.get, body.from_rule_id)
    rule = _call(service.new_version, base, body.model_dump(exclude={"from_rule_id", "reason"}, exclude_none=True), user.id)
    _record(user, "rule_drafted", rule, from_version=base["version"], params=rule.get("params"), reason=body.reason.strip())
    return _with_names([rule])[0]


@router.put("/{rule_id}")
def edit_rule(rule_id: str, body: RuleChanges, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.get, rule_id)
    before = {k: rule.get(k) for k in service.EDITABLE}
    updated = _call(service.edit, rule, body.model_dump(exclude_none=True), user.id)
    changed = {k: {"from": before[k], "to": updated.get(k)} for k in service.EDITABLE if before[k] != updated.get(k)}
    if changed:
        _record(user, "rule_edited", updated, changes=changed)
    return _with_names([updated])[0]


@router.post("/{rule_id}/submit")
def submit_rule(rule_id: str, body: Reason, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.submit, _call(service.get, rule_id), user.id)
    _record(user, "rule_submitted", rule, reason=body.reason.strip())
    others = [m["user_id"] for m in db.fetch_all("members", role="rule_admin") if m["user_id"] != user.id]
    if others:
        db.table("notifications").insert([{"user_id": u, "kind": "rule_submitted", "ref_type": "rule", "ref_id": rule["id"],
                                          "message": f"{rule['rule_code']} version {rule['version']} is waiting for your approval"}
                                         for u in others]).execute()
    return _with_names([rule])[0]


@router.post("/{rule_id}/approve")
def approve_rule(rule_id: str, body: Reason, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.approve, _call(service.get, rule_id), user.id)
    _record(user, "rule_approved", rule, reason=body.reason.strip())
    if rule.get("created_by"):
        db.insert("notifications", {"user_id": rule["created_by"], "kind": "rule_approved", "ref_type": "rule", "ref_id": rule["id"],
                                    "message": f"{rule['rule_code']} version {rule['version']} was approved and can be activated"})
    return _with_names([rule])[0]


@router.post("/{rule_id}/return")
def return_rule(rule_id: str, body: Reason, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.send_back, _call(service.get, rule_id), user.id)
    _record(user, "rule_returned", rule, reason=body.reason.strip())
    if rule.get("created_by"):
        db.insert("notifications", {"user_id": rule["created_by"], "kind": "rule_returned", "ref_type": "rule", "ref_id": rule["id"],
                                    "message": f"{rule['rule_code']} version {rule['version']} was returned to you: {body.reason.strip()}"})
    return _with_names([rule])[0]


@router.post("/{rule_id}/activate")
def activate_rule(rule_id: str, body: Activate, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule, ended = _call(service.activate, _call(service.get, rule_id), body.effective_from)
    _record(user, "rule_activated", rule, effective_from=rule["effective_from"], reason=body.reason.strip(),
            previous=[{"version": e["version"], "effective_to": e["effective_to"], "status": e["status"]} for e in ended])
    return _with_names([rule])[0]


@router.post("/{rule_id}/retire")
def retire_rule(rule_id: str, body: Reason, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    rule = _call(service.retire, _call(service.get, rule_id))
    _record(user, "rule_retired", rule, effective_to=rule["effective_to"], reason=body.reason.strip())
    return _with_names([rule])[0]


@router.get("/{rule_id}/impact", dependencies=[Depends(rate_limit("10/minute", "impact"))])
def rule_impact(rule_id: str, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    return _call(service.impact, _call(service.get, rule_id))


@router.post("/draft-from-text", status_code=201, dependencies=[Depends(rate_limit("10/minute", "draft"))])
def draft_from_text(body: DraftFromText, user: AuthenticatedUser = Depends(require_role(ADMIN))):
    """Read a pasted clause into a draft version of the rule whose check applies it. The draft cites the
    clause, is saved as a draft only, and is never active until a second administrator approves it."""
    active = service.active_rules(service.as_of_date())
    by_type = {r["check_type"]: r for r in active.values()}
    draft, how = service.draft_from_text(body.text, by_type)
    if not draft:
        raise HTTPException(status_code=422, detail="No threshold this engine can apply was found in the text. "
                                                    "It reads minimum areas, area tolerances, photo ages, name similarity and similar values")
    base = by_type[draft["check_type"]]
    changes = {"params": {**(base.get("params") or {}), **draft["params"]}, "clause": draft["clause"],
               "source_reference": body.source_reference.strip()}
    if how == "llm":
        changes.update({"title": draft.get("title") or base.get("title"), "description": draft.get("description") or base.get("description")})
    rule = _call(service.new_version, base, changes, user.id)
    _record(user, "rule_drafted_from_text", rule, from_version=base["version"], drafted_by=how, params=rule.get("params"),
            clause=draft["clause"], source_reference=body.source_reference.strip())
    return {"rule": _with_names([rule])[0], "drafted_by": how,
            "note": "Drafted from the pasted text. Check every value against the clause before submitting it for approval."}
