"""
The as-of date that date checks compare against: today, or a fixed date so demos and the evaluation
give the same results every day.

The `as_of` row in proofpath.settings ({"mode": "fixed", "date": "2026-11-01"} or {"mode": "today"})
wins over the AS_OF_DATE_MODE and AS_OF_DATE environment settings, so the seed script and, later, the
rule administrator can set it without touching the server's environment.
"""
from datetime import date
from typing import Optional

from core.config import settings
from core.db import db


def _from_settings_table() -> Optional[date]:
    try:
        row = db.fetch_one("settings", key="as_of")
    except Exception:
        return None
    value = (row or {}).get("value") or {}
    if isinstance(value, dict) and value.get("mode") == "fixed" and value.get("date"):
        try:
            return date.fromisoformat(value["date"])
        except ValueError:
            return None
    if isinstance(value, dict) and value.get("mode") == "today":
        return date.today()
    return None


def as_of_date() -> date:
    stored = _from_settings_table()
    if stored:
        return stored
    if settings.AS_OF_DATE_MODE == "fixed" and settings.AS_OF_DATE:
        return settings.AS_OF_DATE
    return date.today()
