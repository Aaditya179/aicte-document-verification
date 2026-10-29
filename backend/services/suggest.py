"""
AI suggestions for values the label patterns did not find (build spec 1.2, principles 4 and 6).

The extraction templates read a value only when its label is worded as expected. When a field is still
missing after them, the page text goes to Groq in one call per document, which names the line the value
is on. A suggestion is kept only if:

- the line it quotes is on the page it names, word for word (spacing and case aside),
- the value is inside that line and reads as its type (a real date, a number),
- no other field was suggested from the same line with the same value.

A kept suggestion is stored with source_method AI_SUGGESTED and review_state needs_confirmation, so no
check compares it until a reviewer confirms or corrects it, and the reason says which line it came from.
With no Groq key, or when Groq fails, the fields stay "not found" exactly as before.
"""
import logging
import re
from typing import Optional

from services import llm, normalise
from services.extraction import PageText

logger = logging.getLogger("proofpath.suggest")

SOURCE = "AI_SUGGESTED"
MAX_CHARS = 12000          # page text sent, so a long document stays within one call

SCHEMA = {
    "type": "object",
    "required": ["fields"],
    "properties": {"fields": {"type": "array"}},
}

KIND = {"date": "a date", "int": "a whole number", "number": "a number", "text": "a short text or identifier"}


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _missing(templates: list[dict], rows: list[dict]) -> list[dict]:
    # A label found with a value that did not parse is left alone: the reviewer sees what was printed
    read = {r["field_name"] for r in rows if r.get("field_value") is not None or r.get("original_value")}
    return [t for t in templates if t["field_name"] not in read]


def _document_text(pages: list[PageText]) -> str:
    parts, used = [], 0
    for p in pages:
        if p.unread_scan or not p.text.strip():
            continue
        chunk = f"[page {p.page}]\n{p.text.strip()}\n"
        parts.append(chunk[: MAX_CHARS - used])
        used += len(parts[-1])
        if used >= MAX_CHARS:
            break
    return "\n".join(parts)


def _ask(doc_label: str, targets: list[dict], text: str) -> Optional[list]:
    wanted = "\n".join(f"- {t['field_name']}: {t['field_name'].replace('_', ' ')}, {KIND.get(t['value_type'], 'a value')}"
                       for t in targets)
    result = llm._complete(
        "You locate values in the text of one document. For each field asked for, find the line of the text "
        "that states it. Copy that line exactly as it appears, copy the value exactly as it appears in that "
        "line, and give the page number from the [page N] marker above it. If the text does not state the "
        "field, give null for value, line and page. Never infer, calculate, reformat or guess a value. "
        'Answer as {"fields": [{"field_name": ..., "value": ..., "line": ..., "page": ...}]}.',
        f"Document type: {doc_label}\n\nFields:\n{wanted}\n\nText:\n{text}",
        schema=SCHEMA, max_tokens=1500, temperature=0,
    )
    return result.get("fields") if isinstance(result, dict) and isinstance(result.get("fields"), list) else None


def _grounded(item: dict, template: dict, pages: dict[int, PageText]) -> Optional[dict]:
    """The row for a suggestion that passes every check, or None."""
    value, line, page = item.get("value"), item.get("line"), item.get("page")
    if not isinstance(value, str) or not isinstance(line, str) or not value.strip() or not line.strip():
        return None
    try:
        page = int(page)
    except (TypeError, ValueError):
        return None
    source = pages.get(page)
    if not source or _flat(line) not in _flat(source.text) or _flat(value) not in _flat(line):
        return None
    parsed = normalise.normalise(template["value_type"], value)
    if parsed.value is None:
        return None
    reason = f'Suggested by AI from the line "{normalise.text(line)[:160]}" on page {page}; a person confirms it before it is compared'
    if parsed.ambiguous:
        reason += f"; {parsed.note}"
    return {
        "field_name": template["field_name"], "field_value": parsed.value, "original_value": normalise.text(value),
        "value_type": template["value_type"], "page_number": page, "source_method": SOURCE, "confidence": None,
        "review_state": "needs_confirmation", "review_reason": reason,
    }


def fill_missing(pages: list[PageText], templates: list[dict], rows: list[dict], doc_label: str) -> list[dict]:
    """`rows` with AI suggestions in place of fields the templates did not find. Never raises."""
    targets = _missing(templates, rows)
    text = _document_text(pages)
    if not targets or not text or not llm.llm_enabled():
        return rows
    try:
        answer = _ask(doc_label, targets, text)
    except Exception:
        logger.exception("AI suggestion failed")
        return rows
    if not answer:
        return rows

    by_name = {t["field_name"]: t for t in targets}
    by_page = {p.page: p for p in pages}
    found: dict[str, dict] = {}
    claims: dict[tuple, list[str]] = {}
    for item in answer:
        template = by_name.get(item.get("field_name")) if isinstance(item, dict) else None
        row = _grounded(item, template, by_page) if template else None
        if row:
            found[row["field_name"]] = row
            claims.setdefault((row["page_number"], _flat(item["line"]), _flat(item["value"])), []).append(row["field_name"])
    # Two fields from one line with one value: one of them is wrong, so neither is kept
    clash = {n for names in claims.values() if len(names) > 1 for n in names}
    found = {n: r for n, r in found.items() if n not in clash}
    if not found:
        return rows
    kept = [r for r in rows if r["field_name"] not in found]
    return kept + [found[t["field_name"]] for t in templates if t["field_name"] in found]
