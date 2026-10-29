"""
Issuer registry lookups (build spec section 10, method REGISTRY).

Only a MOCK adapter exists. A real one (for example DigiLocker or API Setu) needs authorisation and is
future work. The MOCK answers by the `registry_adapter_mode` setting:

  unavailable  the default: the registry cannot be reached, so authenticity stays Pending, never failed
  match        returns a record equal to the values read from the document
  mismatch     returns a record that differs in one value, to show check C15 in a demo

Every result says it is a MOCK (is_mock is always true). Comparison is plain Python.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from core.db import db
from services import normalise

MODES = ("unavailable", "match", "mismatch")
DEFAULT_MODE = "unavailable"
SOURCE = "MOCK issuer registry"

# Which document types an issuer registry holds, the number it is looked up by, and the values it
# returns to compare (CLAUDE.md, assumption A30)
REGISTRY_DOCUMENTS: dict[str, dict] = {
    "approval_certificate": {"issuer": "AICTE approval register", "key": "certificate_no",
                             "fields": ["institution_code", "issue_date", "expiry_date"]},
    "fire_noc": {"issuer": "State fire services NOC register", "key": "noc_no",
                 "fields": ["issue_date", "expiry_date"]},
    "land_document": {"issuer": "Land records office", "key": "survey_no",
                      "fields": ["registration_no", "land_area_sqm"]},
}


@dataclass
class RegistryResult:
    status: str                                   # match | mismatch | unavailable
    issuer: str
    record: Optional[dict]
    compared: list[dict] = field(default_factory=list)
    note: str = ""
    is_mock: bool = True


def mode() -> str:
    try:
        row = db.fetch_one("settings", key="registry_adapter_mode")
    except Exception:
        return DEFAULT_MODE
    value = (row or {}).get("value")
    return value if value in MODES else DEFAULT_MODE


def usable(f: Optional[dict]) -> bool:
    return bool(f) and f.get("field_value") is not None and f.get("review_state") != "needs_confirmation"


def _same(value_type: str, a: str, b: str) -> bool:
    if value_type in ("int", "number"):
        try:
            return Decimal(str(a)) == Decimal(str(b))
        except InvalidOperation:
            return a == b
    if value_type == "date":
        return a == b
    return normalise.identifier_key(a) == normalise.identifier_key(b)


def _altered(value_type: str, value: str) -> str:
    """A different value of the same kind, for the MOCK's mismatch mode."""
    if value_type == "date":
        d = date.fromisoformat(value)
        try:
            return d.replace(year=d.year - 1).isoformat()
        except ValueError:                         # 29 February
            return d.replace(year=d.year - 1, day=28).isoformat()
    if value_type in ("int", "number"):
        try:
            return str((Decimal(value) * Decimal("0.9")).quantize(Decimal("1")))
        except InvalidOperation:
            return value + "0"
    last = value[-1:]
    return value[:-1] + (str((int(last) + 1) % 10) if last.isdigit() else ("A" if last != "A" else "B"))


def compare(record: dict, fields: dict[str, dict], names: list[str]) -> list[dict]:
    """Each registry value beside the value read from the document. A value that was not read, or still
    waits for a person to confirm it, is listed but not compared."""
    out = []
    for name in names:
        f = fields.get(name)
        registry_value = record.get(name)
        row = {"field": name, "document_value": f.get("field_value") if f else None,
               "document_shown": (f.get("original_value") or f.get("field_value")) if f else None,
               "page_number": f.get("page_number") if f else None,
               "value_type": (f or {}).get("value_type") or "text", "registry_value": registry_value}
        if registry_value is None or not usable(f):
            row["same"] = None
        else:
            row["same"] = _same(row["value_type"], f["field_value"], str(registry_value))
        out.append(row)
    return out


def lookup(doc_type: str, fields: dict[str, dict], adapter_mode: Optional[str] = None) -> RegistryResult:
    """Ask the (MOCK) registry about one document. `fields` are its extracted values by name, and the
    key value must be usable (the caller checks)."""
    config = REGISTRY_DOCUMENTS[doc_type]
    adapter_mode = adapter_mode or mode()
    key_value = fields[config["key"]]["field_value"]
    if adapter_mode == "unavailable":
        return RegistryResult("unavailable", config["issuer"], None,
                              note="The MOCK registry is set to answer as unavailable, so nothing could be compared. "
                                   "This is not a failed check.")

    record = {config["key"]: key_value}
    for name in config["fields"]:
        f = fields.get(name)
        if usable(f):
            record[name] = f["field_value"]
    note = "MOCK record built from the values read from the document."
    if adapter_mode == "mismatch":
        changeable = [n for n in config["fields"] if n in record]
        if changeable:
            name = changeable[-1]
            record[name] = _altered(fields[name].get("value_type") or "text", record[name])
            note = "MOCK record set to differ from the document in one value, for demonstration."

    compared = compare(record, fields, config["fields"])
    status = "mismatch" if any(c["same"] is False for c in compared) else "match"
    return RegistryResult(status, config["issuer"], record, compared, note)
