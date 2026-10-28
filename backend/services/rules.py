"""
The rules registry (build spec section 9): versions, the lifecycle with four-eyes approval, the impact
preview and drafting a rule from pasted text.

A rule is data executed by fixed code: each rule code switches on one check (validation.CHECKS), and a
new version changes its thresholds (params), wording or dates. Nothing is ever edited in place once it
has left draft: a change is a new version, so a validation run that recorded version 1 keeps meaning
version 1.

Lifecycle: draft (the author edits) -> pending_approval (the author submits) -> approved by a
different rule administrator -> active from its effective date (the previous version of the code ends
the day before) -> retired. A version can be returned from pending_approval to draft with a reason.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from core.clock import as_of_date
from core.db import db
from services import llm
from services.validation import CHECKS, CROSS_TYPES, active_rules, evaluate, load_context

logger = logging.getLogger("proofpath.rules")

# What each check type's params may hold: (kind, minimum, maximum, label) or (kind, choices, label)
PARAMS: dict[str, dict[str, dict]] = {
    "ghost_faculty": {"similarity": {"kind": "number", "min": 0.5, "max": 1.0, "label": "Name similarity (0.5 to 1)"}},
    "photo_reuse": {"max_hamming": {"kind": "int", "min": 0, "max": 32, "label": "Largest fingerprint distance counted as a copy (0 to 32)"}},
    "infra_evidence": {"required": {"kind": "choices", "choices": ["lab", "classroom", "library", "floor_plan"],
                                    "label": "Evidence required"}},
    "area_check": {"area_tolerance_pct": {"kind": "number", "min": 0, "max": 50, "label": "Tolerance, per cent of the declared area"},
                   "min_area_sqm": {"kind": "number", "min": 0, "max": 1_000_000, "label": "Minimum built-up area, sq m"}},
    "photo_metadata": {"max_photo_age_months": {"kind": "int", "min": 1, "max": 120, "label": "Oldest photo accepted, months"},
                       "require_exif": {"kind": "bool", "label": "A photo with no date in its EXIF data is a finding"}},
    "extraction": {"min_confidence": {"kind": "number", "min": 0, "max": 1, "label": "Lowest OCR confidence accepted without a person (0 to 1)"}},
}
SEVERITIES = ("low", "medium", "high")
# Rules whose effect is not a validation check, so their impact cannot be previewed by re-running checks
NO_PREVIEW = {"extraction": "This rule applies when a document is read, so a change takes effect on documents read from then on."}


class RuleError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def finding_types(rule_code: str) -> set[str]:
    return next((types for _, code, _, types in CHECKS if code == rule_code), set())


def check_id(rule_code: str) -> Optional[str]:
    return next((cid for cid, code, _, _ in CHECKS if code == rule_code), None)


def clean_params(check_type: str, params: dict) -> dict:
    """Keep only the params this check type reads, each within its range. Raises RuleError(422)."""
    schema = PARAMS.get(check_type, {})
    unknown = set(params) - set(schema)
    if unknown:
        raise RuleError(422, f"This check does not use {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    for name, spec in schema.items():
        if name not in params or params[name] is None:
            continue
        value = params[name]
        if spec["kind"] in ("number", "int"):
            try:
                value = int(value) if spec["kind"] == "int" else float(value)
            except (TypeError, ValueError):
                raise RuleError(422, f"{spec['label']} must be a number")
            if spec["kind"] == "int" and float(params[name]) != value:
                raise RuleError(422, f"{spec['label']} must be a whole number")
            if not spec["min"] <= value <= spec["max"]:
                raise RuleError(422, f"{spec['label']} must be between {spec['min']} and {spec['max']}")
        elif spec["kind"] == "bool":
            if not isinstance(value, bool):
                raise RuleError(422, f"{spec['label']} must be yes or no")
        elif spec["kind"] == "choices":
            if not isinstance(value, list) or not value or any(v not in spec["choices"] for v in value):
                raise RuleError(422, f"{spec['label']} must be some of {', '.join(spec['choices'])}")
            value = [c for c in spec["choices"] if c in value]
        out[name] = value
    return out


# ------------------------------------------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def versions_of(rule_code: str) -> list[dict]:
    return db.table("rules").select("*").eq("rule_code", rule_code).order("version", desc=True).execute().data or []


def get(rule_id: str) -> dict:
    rule = db.fetch_one("rules", id=rule_id)
    if not rule:
        raise RuleError(404, "Rule not found")
    return rule


EDITABLE = ("title", "description", "params", "severity", "effective_from", "source_reference", "clause")


def _validated(base: dict, changes: dict) -> dict:
    out = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
    if "params" in out:
        # A change names only the params it sets; the others keep the version's values
        out["params"] = clean_params(base["check_type"], {**(base.get("params") or {}), **out["params"]})
    if "severity" in out and out["severity"] not in SEVERITIES:
        raise RuleError(422, "Severity must be low, medium or high")
    if "effective_from" in out and isinstance(out["effective_from"], date):
        out["effective_from"] = out["effective_from"].isoformat()
    for k in ("title", "description", "source_reference", "clause"):
        if k in out:
            out[k] = str(out[k]).strip() or None
    return out


def new_version(from_rule: dict, changes: dict, author_id: str) -> dict:
    """A draft as the next version of the rule's code, starting from `from_rule`."""
    versions = versions_of(from_rule["rule_code"])
    open_ = [v for v in versions if v["status"] in ("draft", "pending_approval")]
    if open_:
        raise RuleError(409, f"Version {open_[0]['version']} of {from_rule['rule_code']} is already being worked on. "
                             "Finish or return it first")
    row = {k: from_rule.get(k) for k in ("rule_code", "title", "description", "check_type", "params", "categories",
                                         "source_reference", "clause", "severity", "requires_human_review", "note")}
    row.update(_validated(from_rule, changes))
    row.update({"version": max(v["version"] for v in versions) + 1, "status": "draft", "created_by": author_id,
                "approved_by": None, "approved_at": None, "effective_to": None})
    if not changes.get("effective_from"):
        row["effective_from"] = None                  # set at activation unless the author chooses a date
    return db.insert("rules", row)


def edit(rule: dict, changes: dict, user_id: str) -> dict:
    if rule["status"] != "draft":
        raise RuleError(409, "Only a draft can be changed. Start a new version instead")
    if rule.get("created_by") and rule["created_by"] != user_id:
        raise RuleError(403, "Only the author of a draft can change it")
    updates = _validated(rule, changes)
    return db.update("rules", rule["id"], updates) if updates else rule


def submit(rule: dict, user_id: str) -> dict:
    if rule["status"] != "draft":
        raise RuleError(409, "Only a draft can be submitted for approval")
    if rule.get("created_by") and rule["created_by"] != user_id:
        raise RuleError(403, "Only the author of a draft can submit it")
    return db.update("rules", rule["id"], {"status": "pending_approval"})


def approve(rule: dict, user_id: str) -> dict:
    """Four eyes: the approver must not be the author."""
    if rule["status"] != "pending_approval":
        raise RuleError(409, "Only a version waiting for approval can be approved")
    if rule.get("approved_by"):
        raise RuleError(409, "This version is already approved")
    if rule.get("created_by") == user_id:
        raise RuleError(403, "You wrote this version, so another rule administrator must approve it")
    return db.update("rules", rule["id"], {"approved_by": user_id, "approved_at": _now()})


def send_back(rule: dict, user_id: str) -> dict:
    if rule["status"] != "pending_approval":
        raise RuleError(409, "Only a version waiting for approval can be returned to its author")
    if rule.get("created_by") == user_id:
        raise RuleError(403, "Another rule administrator returns a version; the author can ask for it back instead")
    return db.update("rules", rule["id"], {"status": "draft", "approved_by": None, "approved_at": None})


def activate(rule: dict, effective_from: Optional[date] = None) -> tuple[dict, list[dict]]:
    """Make an approved version active from its effective date (the as-of date if none is set or it is
    earlier). The previous active version of the code ends the day before; nothing else changes."""
    if rule["status"] != "pending_approval" or not rule.get("approved_by"):
        raise RuleError(409, "A version must be approved by a second rule administrator before it is activated")
    as_of = as_of_date()
    start = effective_from or (date.fromisoformat(rule["effective_from"]) if rule.get("effective_from") else as_of)
    start = max(start, as_of)
    ended = []
    for v in versions_of(rule["rule_code"]):
        if v["id"] != rule["id"] and v["status"] == "active" and not (v.get("effective_to") and v["effective_to"] < start.isoformat()):
            end = (start - timedelta(days=1)).isoformat()
            ended.append(db.update("rules", v["id"], {"effective_to": end, "status": "retired" if start <= as_of else "active"}))
    active = db.update("rules", rule["id"], {"status": "active", "effective_from": start.isoformat(), "effective_to": None})
    return active, ended


def retire(rule: dict) -> dict:
    if rule["status"] != "active":
        raise RuleError(409, "Only an active version can be retired")
    end = max(as_of_date() - timedelta(days=1), date.fromisoformat(rule["effective_from"]) if rule.get("effective_from") else date.min)
    return db.update("rules", rule["id"], {"status": "retired", "effective_to": end.isoformat()})


# ------------------------------------------------------------------------------------------------
# Impact preview (validation mode dry_run): nothing is written
# ------------------------------------------------------------------------------------------------

def impact(rule: dict) -> dict:
    """The findings this version would create or close on every submitted application, compared with
    the version active on the as-of date, without writing anything."""
    if rule["status"] not in ("draft", "pending_approval"):
        raise RuleError(409, "Impact is previewed for a version that is not active yet")
    as_of = as_of_date()
    current = active_rules(as_of).get(rule["rule_code"])
    base = {"rule_code": rule["rule_code"], "version": rule["version"], "check": check_id(rule["rule_code"]),
            "compared_with": current["version"] if current else None, "as_of_date": as_of.isoformat()}
    if rule["check_type"] in NO_PREVIEW:
        return {**base, "available": False, "note": NO_PREVIEW[rule["check_type"]], "applications": [],
                "totals": {"applications_checked": 0, "affected": 0, "created": 0, "closed": 0}}
    types = finding_types(rule["rule_code"])
    cross = bool(types & CROSS_TYPES)
    candidate = {**rule, "status": "active"}
    applications = (db.table("applications").select("*").neq("workflow_status", "draft").order("code").execute().data or [])
    institutions = {i["id"]: i["name"] for i in db.table("institutions").select("id,name").execute().data or []}

    def one(application: dict) -> Optional[dict]:
        ctx = load_context(application, include_cross=cross, reviewer=True)
        ctx.rules = {rule["rule_code"]: current} if current else {}
        before = {f.key: f for f in evaluate(ctx)[0]}
        ctx.rules = {rule["rule_code"]: candidate}
        after = {f.key: f for f in evaluate(ctx)[0]}
        created = [after[k] for k in sorted(set(after) - set(before))]
        closed = [before[k] for k in sorted(set(before) - set(after))]
        if not created and not closed:
            return None
        brief = lambda f: {"key": f.key, "title": f.title, "severity": f.severity}  # noqa: E731
        return {"id": application["id"], "code": application["code"], "institution": institutions.get(application["institution_id"]),
                "created": [brief(f) for f in created], "closed": [brief(f) for f in closed], "unchanged": len(set(before) & set(after))}

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="impact") as pool:
        rows = [r for r in pool.map(one, applications) if r]
    return {**base, "available": True, "note": "Dry run: compared with the active version on the as-of date. Nothing was written.",
            "applications": rows,
            "totals": {"applications_checked": len(applications), "affected": len(rows),
                       "created": sum(len(r["created"]) for r in rows), "closed": sum(len(r["closed"]) for r in rows)}}


# ------------------------------------------------------------------------------------------------
# Drafting from pasted regulation text
# ------------------------------------------------------------------------------------------------

DRAFT_SCHEMA = {
    "type": "object",
    "required": ["check_type", "params", "title", "description", "clause"],
    "properties": {
        "check_type": {"type": "string"}, "params": {"type": "object"}, "title": {"type": "string"},
        "description": {"type": "string"}, "clause": {"type": "string"},
    },
}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n+", text) if s.strip()]


def _number(s: str) -> float:
    return float(s.replace(",", ""))


def draft_by_rules(text: str) -> Optional[dict]:
    """The rule-based reading: one threshold this engine can apply, taken from the sentence that states it."""
    for sentence in _sentences(text):
        low = sentence.lower()
        area = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:sq\.?\s*m|square\s+met(?:re|er)s?|m2|m²)", low)
        if area and re.search(r"minimum|at least|not less than|no less than", low):
            params = {"min_area_sqm": _number(area.group(1))}
            pct = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", low)
            if pct:
                params["area_tolerance_pct"] = _number(pct.group(1))
            return {"check_type": "area_check", "params": params, "clause": sentence}
        months = re.search(r"(\d+)\s*months?", low)
        if months and re.search(r"photo|photograph", low):
            return {"check_type": "photo_metadata", "params": {"max_photo_age_months": int(months.group(1))}, "clause": sentence}
        pct = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", low)
        if pct and re.search(r"area", low):
            return {"check_type": "area_check", "params": {"area_tolerance_pct": _number(pct.group(1))}, "clause": sentence}
    return None


def _grounded(text: str, draft: dict) -> bool:
    """An LLM draft is used only if its clause is quoted from the text and every number in its params
    appears in that clause."""
    flat = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    clause = flat(draft.get("clause") or "")
    if not clause or clause not in flat(text):
        return False
    numbers = {_number(n) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", clause)}
    for v in (draft.get("params") or {}).values():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) not in numbers and float(v) * 100 not in numbers:
            return False
    return True


def draft_from_text(text: str, rules_by_type: dict[str, dict]) -> tuple[Optional[dict], str]:
    """(draft, how) where how is "llm" or "rules". The draft names a check type this engine runs, params
    for it and the clause it came from. None when neither reading finds a threshold."""
    types = {t: list(PARAMS.get(t, {})) for t in rules_by_type if t in PARAMS}
    result = llm._complete(
        "You turn a regulation clause into a threshold for an existing deterministic check. Use only check types and "
        f"parameter names from this list: {types}. Quote the clause exactly as it appears in the text. Use only numbers "
        "that appear in that clause. Write a short plain-language title and a one-sentence description. Do not add facts.",
        text[:6000], schema=DRAFT_SCHEMA, max_tokens=800, temperature=0,
    )
    if isinstance(result, dict) and result.get("check_type") in types and isinstance(result.get("params"), dict) and _grounded(text, result):
        try:
            result["params"] = clean_params(result["check_type"], result["params"])
            if result["params"]:
                return result, "llm"
        except RuleError:
            pass
    fallback = draft_by_rules(text)
    if fallback and fallback["check_type"] in rules_by_type:
        try:
            fallback["params"] = clean_params(fallback["check_type"], fallback["params"])
            return fallback, "rules"
        except RuleError:
            return None, "rules"
    return None, "rules"
