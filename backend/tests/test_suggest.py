"""
AI suggestions for values the label patterns missed (services/suggest.py). Groq is replaced by canned
answers; what is tested is what gets kept: only a value on a line that is in the document, stored for a
person to confirm.
"""
import pytest

from services import llm, suggest
from services.extraction import PageText, extract_fields

PAGE = PageText(1, "\n".join([
    "FIRE SAFETY NO OBJECTION CERTIFICATE",
    "Institution Code: AIT-001",
    "Reference: FNOC-DEMO-77120",
    "Granted on the 15th of June, 2025",
    "This certificate remains in force until 14 June 2027.",
]), "PDF_TEXT", None)

TEMPLATES = [
    {"field_name": "noc_no", "value_type": "text", "regex": r"^\s*NOC (?:no\.?|number)\s*:\s*(\S+)", "required": True},
    {"field_name": "issue_date", "value_type": "date", "regex": r"^\s*Date of issue\s*:\s*(.+?)\s*$", "required": True},
    {"field_name": "expiry_date", "value_type": "date", "regex": r"^\s*Valid until\s*:\s*(.+?)\s*$", "required": True},
]


@pytest.fixture
def answer(monkeypatch):
    """Set what the model answers; None means the call failed."""
    box = {"fields": None, "calls": 0}

    def fake(system, content, **kw):
        box["calls"] += 1
        return None if box["fields"] is None else {"fields": box["fields"]}
    monkeypatch.setattr(llm, "_complete", fake)
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    return box


def run(pages=(PAGE,), templates=TEMPLATES):
    read = extract_fields(list(pages), templates)
    return {r["field_name"]: r for r in suggest.fill_missing(list(pages), templates, read, "Fire NOC")}


def test_grounded_values_are_kept_for_a_person_to_confirm(answer):
    answer["fields"] = [
        {"field_name": "noc_no", "value": "FNOC-DEMO-77120", "line": "Reference: FNOC-DEMO-77120", "page": 1},
        {"field_name": "expiry_date", "value": "14 June 2027", "line": "This certificate remains in force until 14 June 2027.", "page": 1},
    ]
    rows = run()
    assert rows["noc_no"]["field_value"] == "FNOC-DEMO-77120" and rows["expiry_date"]["field_value"] == "2027-06-14"
    for name in ("noc_no", "expiry_date"):
        assert rows[name]["source_method"] == "AI_SUGGESTED" and rows[name]["review_state"] == "needs_confirmation"
        assert rows[name]["page_number"] == 1 and "Suggested by AI from the line" in rows[name]["review_reason"]
    assert rows["issue_date"]["field_value"] is None          # not suggested: still not found


def test_a_value_not_in_the_document_is_dropped(answer):
    answer["fields"] = [{"field_name": "noc_no", "value": "FNOC-2025-001", "line": "NOC number: FNOC-2025-001", "page": 1}]
    assert run()["noc_no"]["field_value"] is None


def test_a_value_outside_its_quoted_line_is_dropped(answer):
    answer["fields"] = [{"field_name": "noc_no", "value": "AIT-001", "line": "Reference: FNOC-DEMO-77120", "page": 1}]
    assert run()["noc_no"]["field_value"] is None


def test_the_wrong_page_is_dropped(answer):
    answer["fields"] = [{"field_name": "noc_no", "value": "FNOC-DEMO-77120", "line": "Reference: FNOC-DEMO-77120", "page": 2}]
    assert run()["noc_no"]["field_value"] is None


def test_a_value_that_does_not_read_as_its_type_is_dropped(answer):
    # "the 15th of June, 2025" is in the line, but it is not a date the checks can compare
    answer["fields"] = [{"field_name": "issue_date", "value": "the 15th of June, 2025", "line": "Granted on the 15th of June, 2025", "page": 1}]
    assert run()["issue_date"]["field_value"] is None


def test_two_fields_from_one_line_and_value_are_both_dropped(answer):
    line = "This certificate remains in force until 14 June 2027."
    answer["fields"] = [{"field_name": "issue_date", "value": "14 June 2027", "line": line, "page": 1},
                        {"field_name": "expiry_date", "value": "14 June 2027", "line": line, "page": 1}]
    rows = run()
    assert rows["issue_date"]["field_value"] is None and rows["expiry_date"]["field_value"] is None


def test_without_the_model_reading_is_unchanged(answer):
    answer["fields"] = None                                   # Groq down, or no key
    rows = run()
    assert all(r["field_value"] is None and r["source_method"] is None for r in rows.values())


def test_nothing_is_asked_when_every_label_was_read(answer):
    page = PageText(1, "NOC number: FNOC/1\nDate of issue: 1 April 2025\nValid until: 31 March 2028", "PDF_TEXT", None)
    rows = run(pages=(page,))
    assert answer["calls"] == 0 and all(r["source_method"] == "PDF_TEXT" for r in rows.values())


def test_a_label_read_with_an_unreadable_value_is_left_for_the_reviewer(answer):
    page = PageText(1, "NOC number: FNOC/1\nDate of issue: soon\nValid until: 31 March 2028", "PDF_TEXT", None)
    answer["fields"] = [{"field_name": "issue_date", "value": "31 March 2028", "line": "Valid until: 31 March 2028", "page": 1}]
    rows = run(pages=(page,))
    assert answer["calls"] == 0 and rows["issue_date"]["original_value"] == "soon"
