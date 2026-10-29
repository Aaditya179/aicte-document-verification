"""
The label patterns in migration 0006: each still reads the wording of the seeded documents, also reads
the common variants ("Issue Date", "Expiry Date", a Fire NOC's "Certificate Number"), and does not pick
up a neighbouring line.
"""
import re
from pathlib import Path

import pytest

from services.extraction import PageText, extract_fields

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "0006_label_variants.sql"
LATER = [MIGRATIONS / "0007_label_variants_2.sql"]          # each updates some of 0006's patterns
ROW = re.compile(r"\('(\w+)', '(\w+)',\s*'([^']*)'\)")


def templates(doc_type: str) -> list[dict]:
    """The pattern in force for each field: 0006, then any later migration that changes it."""
    latest = {}
    for path in [MIGRATION] + LATER:
        latest.update({(d, f): r for d, f, r in ROW.findall(path.read_text())})
    return [{"doc_type": d, "field_name": f, "regex": r, "required": True,
             "value_type": "date" if f.endswith("_date") or f.endswith("valid_until") else "text"}
            for (d, f), r in latest.items() if d == doc_type]


def read(doc_type: str, lines: list[str]) -> dict:
    fields = extract_fields([PageText(1, "\n".join(lines), "PDF_TEXT", None)], templates(doc_type))
    return {f["field_name"]: f["original_value"] for f in fields}


def test_every_template_of_0003_is_updated():
    seeded = re.findall(r"\('(\w+)', '(\w+)', +'(?:text|int|number|date)'", (MIGRATION.parent / "0003_seed_reference.sql").read_text())
    assert sorted((d, f) for d, f, _ in ROW.findall(MIGRATION.read_text())) == sorted(seeded)


# Wording of seed/make_documents.py, which the evaluation depends on
SEEDED = {
    "application_form": (["Institution code: INST-1001", "Institution name: Aarohan Institute of Technology",
                          "Number of faculty: 24", "Total built-up area: 5,200 sq m", "Approval valid until: 31/03/2028",
                          "Fire NOC number: FNOC/2025/118", "Survey number: 112/4A"],
                         {"institution_code": "INST-1001", "institution_name": "Aarohan Institute of Technology",
                          "declared_faculty_count": "24", "declared_total_area_sqm": "5,200",
                          "declared_certificate_valid_until": "31/03/2028", "declared_fire_noc_no": "FNOC/2025/118",
                          "survey_no": "112/4A"}),
    "approval_certificate": (["Certificate number: AICTE/2025/0142", "Institution code: INST-1001",
                              "Institution name: Aarohan", "Date of issue: 1 April 2025", "Valid until: 31 March 2028"],
                             {"certificate_no": "AICTE/2025/0142", "institution_code": "INST-1001",
                              "issue_date": "1 April 2025", "expiry_date": "31 March 2028"}),
    "fire_noc": (["NOC number: FNOC/2025/118", "Premises: Aarohan, Pune", "Date of issue: 15 June 2025",
                  "Valid until: 14 June 2027"],
                 {"noc_no": "FNOC/2025/118", "issue_date": "15 June 2025", "expiry_date": "14 June 2027"}),
    "land_document": (["Registration number: REG/PUN/2021/3001", "Survey number: 112/4A", "Land area: 20,000 sq m"],
                      {"registration_no": "REG/PUN/2021/3001", "survey_no": "112/4A", "land_area_sqm": "20,000"}),
    "faculty_list": (["F-001 | A Name | Professor | PhD | XXXX1234 | 01/07/2020 | ", "", "Total faculty: 24"],
                     {"faculty_total": "24"}),
    "affidavit": (["Institution code: INST-1001", "I, the principal of Aarohan, state that this is correct.",
                   "Date: 2 September 2026", "Place: Pune"],
                  {"institution_code": "INST-1001", "affidavit_date": "2 September 2026"}),
}


@pytest.mark.parametrize("doc_type", sorted(SEEDED))
def test_seeded_wording_reads_as_before(doc_type):
    lines, expected = SEEDED[doc_type]
    assert read(doc_type, lines) == expected


def test_fire_noc_as_institutions_write_it():
    got = read("fire_noc", ["FIRE SAFETY NO OBJECTION CERTIFICATE", "Institution Name: Aarohan Institute of Technology",
                            "Institution Code: AIT-001", "Certificate Number: FNOC-DEMO-77120",
                            "Issue Date: 15 June 2025", "Expiry Date: 14 June 2027",
                            "Issuing Authority: Fictional Fire Services Department"])
    assert got == {"noc_no": "FNOC-DEMO-77120", "issue_date": "15 June 2025", "expiry_date": "14 June 2027"}


@pytest.mark.parametrize("issue,expiry", [
    ("Issue Date: 1 April 2025", "Expiry Date: 31 March 2028"),
    ("Issued on - 1 April 2025", "Valid till: 31 March 2028"),
    ("Date of Issuance: 1 April 2025", "Valid up to: 31 March 2028"),
    ("Date of issue: 1 April 2025", "Date of expiry: 31 March 2028"),
])
def test_approval_certificate_date_labels(issue, expiry):
    got = read("approval_certificate", ["Approval Certificate No: AICTE-DEMO-2025-0142", "Institute Code: AIT-001", issue, expiry])
    assert got == {"certificate_no": "AICTE-DEMO-2025-0142", "institution_code": "AIT-001",
                   "issue_date": "1 April 2025", "expiry_date": "31 March 2028"}


def test_other_lines_are_not_picked_up():
    # Neither the institution code nor the issuing authority is a NOC number or a date
    got = read("fire_noc", ["Institution Code: AIT-001", "Issuing Authority: Fire Services"])
    assert got == {"noc_no": None, "issue_date": None, "expiry_date": None}


# The files a tester uploaded on 29/10/2026, as PyMuPDF reads them
def test_application_form_with_declared_labels():
    got = read("application_form", ["Institution Name: Aarohan Institute of Technology", "Institution Code: AIT-001",
                                    "Declared Faculty Count: 6", "Declared Total Area (sq m): 5200",
                                    "Declared Approval Certificate Number: AICTE-DEMO-2025-0142",
                                    "Declared Approval Valid Until: 31 March 2028", "Application Date: 12 September 2026"])
    assert got == {"institution_code": "AIT-001", "institution_name": "Aarohan Institute of Technology",
                   "declared_faculty_count": "6", "declared_total_area_sqm": "5200",
                   "declared_certificate_valid_until": "31 March 2028", "declared_fire_noc_no": None, "survey_no": None}


def test_approval_certificate_as_uploaded():
    got = read("approval_certificate", ["Institution Name: Aarohan Institute of Technology", "Institution Code: AIT-001",
                                        "Certificate Number: AICTE-DEMO-2025-0142", "Issue Date: 01 April 2025",
                                        "Expiry Date: 31 March 2028", "Issuing Authority: Fictional Regional Approval Office"])
    assert got == {"certificate_no": "AICTE-DEMO-2025-0142", "institution_code": "AIT-001",
                   "issue_date": "01 April 2025", "expiry_date": "31 March 2028"}


def test_land_document_with_a_lettered_survey_number():
    got = read("land_document", ["Survey Number: SY-DEMO-448/2", "Total Land Area (sq m): 5200",
                                 "Owner: Aarohan Education Trust (Fictional)", "Issue Date: 03 March 2020"])
    assert got == {"survey_no": "SY-DEMO-448/2", "registration_no": None, "land_area_sqm": "5200"}
