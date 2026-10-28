"""The as-of date that date checks compare against: today, or a fixed date so demos are reproducible."""
from datetime import date

from core.config import settings


def as_of_date() -> date:
    if settings.AS_OF_DATE_MODE == "fixed" and settings.AS_OF_DATE:
        return settings.AS_OF_DATE
    return date.today()
