"""
Normalisation of values read from documents (build spec section 6), so two documents that state the
same thing in different ways compare equal, and anything uncertain is marked instead of guessed.

- Names: lowercase, titles removed (dr, prof, mr, ms, mrs), dots and commas removed, spaces collapsed.
- Dates: ISO YYYY-MM-DD. Textual months are unambiguous. A numeric date such as 03/08/2027, where both
  leading parts are 12 or less and differ, is ambiguous: the day-first reading (Indian usage) is kept
  as a suggestion and the value goes to a reviewer to confirm.
- Numbers: thousands separators, spaces and units removed.
- Identifiers: compared on a key that ignores case, spaces and the choice of separator.
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

TITLES = {"dr", "prof", "mr", "ms", "mrs"}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def name(value: str) -> str:
    tokens = re.sub(r"[.,]", " ", value.lower()).split()
    return " ".join(t for t in tokens if t not in TITLES)


def identifier_key(value: str) -> str:
    """'S. No. 112-3' style variations aside, '112/3', '112-3' and '112 / 3' share one key."""
    return re.sub(r"[\s/\-.\\_]+", "/", value.strip().upper()).strip("/")


def number(value: str) -> Optional[Decimal]:
    cleaned = re.sub(r"(?i)\s*(sq\.?\s*m(?:etres?|eters?)?|sqm|m2|m²)\.?\s*$", "", value.strip())
    cleaned = re.sub(r"[,\s]", "", cleaned)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def integer(value: str) -> Optional[int]:
    n = number(value)
    if n is None or n != n.to_integral_value():
        return None
    return int(n)


@dataclass
class ParsedDate:
    value: Optional[date]          # the reading used, or the suggested reading when ambiguous
    ambiguous: bool = False
    alternative: Optional[date] = None


def _year(y: str) -> int:
    n = int(y)
    return n + 2000 if len(y) == 2 else n


def _safe(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(value: str) -> ParsedDate:
    s = text(value).lower().replace(",", " ")
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return ParsedDate(_safe(int(m[1]), int(m[2]), int(m[3])))

    # 31 March 2028, 31-Mar-2028
    m = re.fullmatch(r"(\d{1,2})[\s\-]+([a-z]+)\.?[\s\-]+(\d{2,4})", s)
    if m and m[2] in MONTHS:
        return ParsedDate(_safe(_year(m[3]), MONTHS[m[2]], int(m[1])))

    # March 31 2028
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})\s+(\d{2,4})", s)
    if m and m[1] in MONTHS:
        return ParsedDate(_safe(_year(m[3]), MONTHS[m[1]], int(m[2])))

    # 31/03/2028, 31-03-2028, 31.03.2028
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), _year(m[3])
        if a > 12:
            return ParsedDate(_safe(y, b, a))
        if b > 12:
            return ParsedDate(_safe(y, a, b))
        if a == b:
            return ParsedDate(_safe(y, a, a))
        return ParsedDate(_safe(y, b, a), ambiguous=True, alternative=_safe(y, a, b))

    return ParsedDate(None)


def _spoken(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


@dataclass
class Normalised:
    value: Optional[str]           # what checks compare; None when the text could not be read as its type
    ambiguous: bool = False
    note: Optional[str] = None     # why a reviewer should confirm it


def normalise(value_type: str, raw: str) -> Normalised:
    if value_type == "date":
        parsed = parse_date(raw)
        if parsed.value is None:
            return Normalised(None, note=f'"{text(raw)}" could not be read as a date')
        if parsed.ambiguous:
            return Normalised(parsed.value.isoformat(), ambiguous=True,
                              note=f'"{text(raw)}" could be {_spoken(parsed.value)} or {_spoken(parsed.alternative)}')
        return Normalised(parsed.value.isoformat())
    if value_type == "int":
        n = integer(raw)
        return Normalised(str(n)) if n is not None else Normalised(None, note=f'"{text(raw)}" is not a whole number')
    if value_type == "number":
        n = number(raw)
        return Normalised(format(n.normalize(), "f")) if n is not None else Normalised(None, note=f'"{text(raw)}" is not a number')
    return Normalised(text(raw))
