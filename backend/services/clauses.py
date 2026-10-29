"""
Regulation clauses behind a finding, and a draft explanation of it (build spec 1.2, principles 4 and 5).

Retrieval is plain Python: the clauses a rule names (rule_codes) come first, then BM25 keyword search
over the library with the rule's title and description and the finding's title as the query. Groq has
no embeddings, and the library is small, so keyword search is enough and gives the same answer twice.

The explanation is a draft for the reviewer, never a conclusion, and is not stored as a finding. Groq
writes at most three sentences from the finding, its evidence, the rule and the retrieved clauses only.
The draft is used only if every number in it appears in that material, it cites only retrieved clauses
and it uses none of the words a finding must not use. Otherwise, or with no Groq key, a template
built from the same record is returned instead.
"""
import logging
import math
import re
from collections import Counter
from typing import Optional

from core.db import db
from services import llm

logger = logging.getLogger("proofpath.clauses")

MAX_CLAUSES = 3
MAX_CHARS = 700

STOP = set("""a an and are as at be been being by can for from has have if in into is it its may must no not
of on or shall such that the their then there these this those to was were where which while who will with
within without any each one more other own same than when""".split())

# What a finding must never say (CLAUDE.md, words): it says what differs and where, never what it implies
FORBIDDEN = re.compile(r"\b(fraud\w*|forg(?:ed|ery|eries)|fake\w*|counterfeit\w*|fabricat\w*|illegal\w*|unlawful\w*|"
                       r"guilt\w*|cheat\w*|deceiv\w*|deception|approv\w*|reject\w*|ineligib\w*|disqualif\w*|"
                       r"penal\w*|blacklist\w*|misconduct|breach\w*|violat\w*|contraven\w*|non-?complian\w*|infring\w*)\b", re.I)

SCHEMA = {
    "type": "object",
    "required": ["text", "clause_refs"],
    "properties": {"text": {"type": "string"}, "clause_refs": {"type": "array"}},
}


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", (text or "").lower())
    return [w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in words if w not in STOP]


def _bm25(query: list[str], docs: list[list[str]], k1: float = 1.4, b: float = 0.75) -> list[float]:
    if not docs:
        return []
    n = len(docs)
    avg = sum(len(d) for d in docs) / n or 1
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for t in set(query):
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    return scores


def load() -> Optional[list[dict]]:
    """Every clause, or None when the library is not there yet (migration 0009 not applied)."""
    try:
        return db.table("regulation_clauses").select("*").order("clause_ref").execute().data or []
    except Exception as e:
        logger.warning(f"Regulation clauses unavailable: {e}")
        return None


def retrieve(finding: dict, rule: Optional[dict], library: list[dict], k: int = MAX_CLAUSES) -> list[dict]:
    """Up to k clauses: those the rule names, then the best keyword matches scoring at least half the best."""
    code = finding.get("rule_code")
    named = [c for c in library if code and code in (c.get("rule_codes") or [])]
    rest = [c for c in library if c not in named]
    query = _tokens(" ".join(filter(None, [(rule or {}).get("title"), (rule or {}).get("description"),
                                           finding.get("title"), (finding.get("finding_type") or "").replace("_", " ")])))
    scores = _bm25(query, [_tokens(f"{c['heading']} {c['heading']} {c['body']}") for c in rest])
    top = max(scores, default=0)
    found = sorted(((s, c) for s, c in zip(scores, rest) if s > 0 and s >= top / 2), key=lambda p: -p[0])
    out = [{**c, "matched_by": "rule"} for c in named]
    out += [{**c, "matched_by": "search"} for _, c in found]
    return out[:k]


def _numbers(text: str) -> set[str]:
    return {n.lstrip("0") or "0" for n in re.findall(r"\d+", text or "")}


def _material(finding: dict, rule: Optional[dict], clauses: list[dict]) -> str:
    """Everything the draft may draw on, as one text."""
    parts = [finding.get("title"), finding.get("detail"), finding.get("rule_code"), str(finding.get("rule_version") or "")]
    for e in finding.get("evidence") or []:
        parts += [e.get("label"), e.get("shown_value"), str(e.get("page_number") or ""),
                  ((e.get("document") or {}).get("original_name"))]
    if rule:
        parts += [rule.get("title"), rule.get("description"), str(rule.get("params") or "")]
    for c in clauses:
        parts += [c["clause_ref"], c["heading"], c["body"]]
    return "\n".join(p for p in parts if p)


def _plain(text) -> Optional[str]:
    """Model text with typographic hyphens and spaces made plain, so clause references read as stored."""
    if not isinstance(text, str):
        return None
    return re.sub(r"[ \u00a0\u202f]+", " ", re.sub(r"[\u2010\u2011\u2012]", "-", text)).strip()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def grounded(text: str, refs: list, material: str, allowed_refs: set[str]) -> bool:
    """The checks a model's draft must pass before a reviewer sees it."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CHARS or len(_sentences(text)) > 3:
        return False
    if FORBIDDEN.search(text):
        return False
    if not _numbers(text) <= _numbers(material):
        return False
    return isinstance(refs, list) and all(isinstance(r, str) and r in allowed_refs for r in refs)


def template(finding: dict, rule: Optional[dict], clauses: list[dict]) -> dict:
    """The explanation without the model: the finding's own words and the first sentence of its clause."""
    first = (finding.get("detail") or finding.get("title") or "").strip()
    if first and not first.endswith((".", "!", "?")):
        first += "."
    name = f"Rule {finding.get('rule_code')}" + (f", {rule['title'].rstrip('.')}," if rule and rule.get("title") else "")
    if clauses:
        c = clauses[0]
        second = f"{name} rests on clause {c['clause_ref']} ({c['heading']}), which says: {_sentences(c['body'])[0]}"
        refs = [c["clause_ref"]]
    else:
        second = f"{name} has no clause in the library yet."
        refs = []
    return {"text": f"{first} {second}".strip(), "clause_refs": refs, "by": "rules"}


def explain(finding: dict, rule: Optional[dict], clauses: list[dict]) -> dict:
    """{"text", "clause_refs", "by"}, where by is "llm" for a draft that passed every check, else "rules"."""
    material = _material(finding, rule, clauses)
    allowed = {c["clause_ref"] for c in clauses}
    if clauses and llm.llm_enabled():
        try:
            result = llm._complete(
                "You help a scrutiny reviewer understand one finding on an application. In two or three plain sentences, "
                "say what was found and which clause the rule rests on. Use only the material given: never add facts, "
                "numbers, dates or names that are not in it. Say what differs and where; never say what it implies about "
                "the institution, and never suggest a decision on the application. Do not say the finding breaches or violates "
                "the clause; say what the clause asks and what was found. List the clause references you used.",
                material[:8000], schema=SCHEMA, max_tokens=500, temperature=0,
            )
        except Exception:
            logger.exception("Explanation draft failed")
            result = None
        text = _plain(result.get("text")) if isinstance(result, dict) else None
        if text and grounded(text, result.get("clause_refs"), material, allowed):
            return {"text": text, "clause_refs": result["clause_refs"], "by": "llm"}
    return template(finding, rule, clauses)


def public(clause: dict) -> dict:
    return {k: clause.get(k) for k in ("id", "clause_ref", "source", "heading", "body", "rule_codes", "is_illustrative",
                                       "matched_by", "created_at")}
