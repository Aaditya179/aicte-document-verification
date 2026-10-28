"""Request bodies. Every input is validated here before a route sees it."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    category: Literal["new_institution", "extension_of_approval"]
    academic_year: str = Field(..., pattern=r"^20\d{2}-\d{2}$", examples=["2027-28"])
    declared_total_area_sqm: Optional[float] = Field(None, gt=0, lt=10_000_000)


class UploadInit(BaseModel):
    doc_type: str = Field(..., max_length=40, pattern=r"^[a-z_]+$")
    filename: str = Field(..., min_length=1, max_length=200)
    mime: str = Field(..., max_length=100)
    size: int = Field(..., gt=0)
    # Photos only: what the photo shows
    category: Optional[Literal["lab", "classroom", "library", "other"]] = None

