"""
Synthetic documents for the seeded dataset (build spec section 14). Everything is fictional.

Each document prints one "Label: value" pair per line, the format the extraction templates in
0003_seed_reference.sql read, under a banner saying it is synthetic. PDFs are drawn with PyMuPDF and
photos with Pillow, so the dataset needs no other tools. Generation is deterministic: the same
AppSpec always gives byte-identical files, so ground_truth.json stays valid across runs.
"""
import io
import random
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pymupdf
from PIL import Image, ImageDraw

BANNER = "SYNTHETIC DEMO DOCUMENT - fictional institution, not an AICTE record"


@dataclass
class Person:
    code: str
    name: str
    designation: str
    qualification: str
    masked_id: str
    start: date
    end: Optional[date] = None


@dataclass
class AppSpec:
    """Everything printed in one application's documents. Scenarios change one value from a clean spec."""
    seq: int                                   # drives the photo seed and the identifiers
    inst_code: str
    inst_name: str
    city: str
    category: str                              # new_institution or extension_of_approval
    academic_year: str
    declared_faculty: int
    faculty_total: int
    faculty: list[Person]
    declared_area_sqm: int
    survey_no: str
    land_area_sqm: int
    certificate_no: str
    certificate_code: str                      # institution code printed on the certificate
    cert_issue: str                            # printed exactly as given
    cert_expiry: str
    form_cert_valid_until: str
    form_code: str
    noc_no: str
    form_noc_no: str
    noc_issue: str
    noc_expiry: str
    affidavit_date: str
    photo_taken: datetime
    photo_categories: tuple = ("lab", "classroom", "library")
    skip: set = field(default_factory=set)     # document types left out
    duplicate_of: dict = field(default_factory=dict)  # doc_type -> photo category whose file it reuses


def _pdf(title: str, lines: list[str]) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 40), BANNER, fontsize=8, color=(0.4, 0.4, 0.4))
    page.insert_text((50, 80), title, fontsize=16)
    y = 120
    for line in lines:
        if y > 800:
            page = doc.new_page(width=595, height=842)
            page.insert_text((50, 40), BANNER, fontsize=8, color=(0.4, 0.4, 0.4))
            y = 80
        page.insert_text((50, y), line, fontsize=11)
        y += 20
    # Fixed metadata so the same spec always gives the same bytes and SHA-256
    doc.set_metadata({"producer": "ProofPath synthetic generator", "creator": "ProofPath", "creationDate": "D:20260901000000",
                      "modDate": "D:20260901000000", "title": title})
    return doc.tobytes(garbage=3, deflate=True, no_new_id=True)


def application_form(s: AppSpec) -> bytes:
    kind = "New institution" if s.category == "new_institution" else "Extension of approval"
    lines = [
        f"Institution code: {s.form_code}",
        f"Institution name: {s.inst_name}",
        f"City: {s.city}",
        f"Academic year: {s.academic_year}",
        f"Number of faculty: {s.declared_faculty}",
        f"Total built-up area: {s.declared_area_sqm:,} sq m",
        f"Fire NOC number: {s.form_noc_no}",
        f"Survey number: {s.survey_no}",
    ]
    if s.category == "extension_of_approval":
        lines.insert(6, f"Approval valid until: {s.form_cert_valid_until}")
    return _pdf(f"Application form - {kind.lower()}", lines)


def approval_certificate(s: AppSpec) -> bytes:
    return _pdf("Approval certificate", [
        f"Certificate number: {s.certificate_no}",
        f"Institution code: {s.certificate_code}",
        f"Institution name: {s.inst_name}",
        f"Date of issue: {s.cert_issue}",
        f"Valid until: {s.cert_expiry}",
    ])


def fire_noc(s: AppSpec) -> bytes:
    return _pdf("Fire safety no objection certificate", [
        f"NOC number: {s.noc_no}",
        f"Premises: {s.inst_name}, {s.city}",
        f"Date of issue: {s.noc_issue}",
        f"Valid until: {s.noc_expiry}",
    ])


def land_document(s: AppSpec) -> bytes:
    return _pdf("Registered land document", [
        f"Registration number: REG/{s.city[:3].upper()}/{2019 + s.seq % 5}/{3000 + s.seq}",
        f"Survey number: {s.survey_no}",
        f"Land area: {s.land_area_sqm:,} sq m",
        f"Owner: {s.inst_name}",
    ])


def faculty_list(s: AppSpec) -> bytes:
    def d(x: Optional[date]) -> str:
        return x.strftime("%d/%m/%Y") if x else ""
    rows = ["Code | Name | Designation | Qualification | Masked ID | Period start | Period end"]
    rows += [f"{p.code} | {p.name} | {p.designation} | {p.qualification} | {p.masked_id} | {d(p.start)} | {d(p.end)}" for p in s.faculty]
    rows += ["", f"Total faculty: {s.faculty_total}"]
    return _pdf("Faculty list (named members shown; total covers all posts)", rows)


def affidavit(s: AppSpec) -> bytes:
    return _pdf("Affidavit", [
        f"Institution code: {s.form_code}",
        f"I, the principal of {s.inst_name}, state that the information in this application is correct.",
        f"Date: {s.affidavit_date}",
        "Place: " + s.city,
    ])


def floor_plan(s: AppSpec) -> bytes:
    return _pdf("Floor plan (summary)", [f"Premises: {s.inst_name}", f"Total built-up area: {s.declared_area_sqm:,} sq m",
                                         "Ground floor: labs and library", "First floor: classrooms"])


def photo(s: AppSpec, category: str) -> bytes:
    """A synthetic room photo. The seed depends on the application and category, so every photo differs."""
    rng = random.Random(f"{s.seq}-{category}")
    img = Image.new("RGB", (1200, 800), tuple(rng.randint(150, 235) for _ in range(3)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, rng.randint(480, 620), 1200, 800], fill=tuple(rng.randint(60, 160) for _ in range(3)))
    for _ in range(rng.randint(5, 9)):
        x, y = rng.randint(0, 1000), rng.randint(60, 600)
        w, h = rng.randint(60, 320), rng.randint(40, 260)
        shape = d.rectangle if rng.random() < 0.7 else d.ellipse
        shape([x, y, x + w, y + h], fill=tuple(rng.randint(0, 255) for _ in range(3)))
    exif = Image.Exif()
    exif[0x8769] = {36867: s.photo_taken.strftime("%Y:%m:%d %H:%M:%S")}
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, exif=exif.tobytes())
    return buf.getvalue()


PDF_BUILDERS = {
    "application_form": application_form,
    "approval_certificate": approval_certificate,
    "fire_noc": fire_noc,
    "land_document": land_document,
    "faculty_list": faculty_list,
    "affidavit": affidavit,
    "floor_plan": floor_plan,
}
