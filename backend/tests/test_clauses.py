"""
Regulation clauses behind a finding and the draft explanation (services/clauses.py, routers/clauses.py).
Retrieval is plain keyword search; Groq is replaced by canned answers, and what is tested is which draft
reaches the reviewer: only one whose numbers, clauses and words all come from the record.
"""
import pytest

from services import clauses, llm

LIBRARY = [
    {"id": "c1", "clause_ref": "ILL-1.2", "source": "Illustrative", "heading": "Certificates in force", "is_illustrative": True,
     "body": "A certificate relied on in an application shall be in force on the date the application is examined. "
             "A certificate whose validity has ended is to be replaced by a current one.", "rule_codes": ["R-EXP-01"]},
    {"id": "c2", "clause_ref": "ILL-3.2", "source": "Illustrative", "heading": "Built-up area", "is_illustrative": True,
     "body": "The total built-up area declared shall agree, within the stated tolerance, with the sum of the room areas "
             "shown on the floor plan.", "rule_codes": ["R-AREA-01"]},
    {"id": "c3", "clause_ref": "ILL-1.3", "source": "Illustrative", "heading": "Dates on a certificate", "is_illustrative": True,
     "body": "The date until which a certificate is valid shall fall after the date on which it was issued.", "rule_codes": ["R-DATE-01"]},
    {"id": "c4", "clause_ref": "ILL-3.3", "source": "Illustrative", "heading": "Recent photographs", "is_illustrative": True,
     "body": "Photographs of the premises shall have been taken within twelve months before the date of examination.", "rule_codes": []},
]

RULE = {"rule_code": "R-EXP-01", "version": 1, "title": "Certificate expired",
        "description": "A certificate's validity has ended before the as-of date.", "params": {}}

FINDING = {
    "id": "f-1", "application_id": "app-b", "finding_type": "EXPIRED_DOCUMENT", "rule_code": "R-EXP-01", "rule_version": 1,
    "title": "Fire NOC validity has ended", "detail": "The Fire NOC is valid until 2026-03-31, before the as-of date 2026-11-01.",
    "evidence": [{"label": "Valid until", "shown_value": "31/03/2026", "page_number": 1, "document": {"original_name": "fire_noc.pdf"}}],
}


@pytest.fixture
def answer(monkeypatch):
    box = {"result": None, "calls": 0}

    def fake(system, content, **kw):
        box["calls"] += 1
        return box["result"]
    monkeypatch.setattr(llm, "_complete", fake)
    monkeypatch.setattr(llm, "llm_enabled", lambda: True)
    return box


# Retrieval --------------------------------------------------------------------------------------

def test_the_clause_a_rule_names_comes_first():
    found = clauses.retrieve(FINDING, RULE, LIBRARY)
    assert found[0]["clause_ref"] == "ILL-1.2" and found[0]["matched_by"] == "rule"
    assert len(found) <= clauses.MAX_CLAUSES


def test_keyword_search_finds_a_clause_no_rule_names():
    finding = {"finding_type": "PHOTO_METADATA", "rule_code": "R-NEW-01", "title": "Photograph taken more than twelve months ago"}
    found = clauses.retrieve(finding, None, LIBRARY)
    assert found and found[0]["clause_ref"] == "ILL-3.3" and found[0]["matched_by"] == "search"


def test_an_unrelated_finding_gets_no_clause():
    assert clauses.retrieve({"finding_type": "X", "rule_code": "R-X", "title": "Zebra"}, None, LIBRARY) == []
    assert clauses.retrieve(FINDING, RULE, []) == []


# What a draft must pass -------------------------------------------------------------------------

def _check(text, refs=("ILL-1.2",)):
    material = clauses._material(FINDING, RULE, LIBRARY[:1])
    return clauses.grounded(text, list(refs), material, {"ILL-1.2"})


def test_a_draft_from_the_record_passes_and_dates_may_be_rewritten():
    assert _check("The Fire NOC on page 1 was valid until 31/03/2026, before the as-of date. "
                  "Clause ILL-1.2 asks that a certificate be in force when the application is examined.")


def test_a_draft_with_a_number_not_in_the_record_fails():
    assert not _check("The Fire NOC lapsed 214 days before the as-of date.")


def test_a_draft_that_states_an_implication_fails():
    assert not _check("The Fire NOC looks fake.")
    assert not _check("The application should be rejected until a new Fire NOC is sent.")
    assert not _check("This breaches the requirement in clause ILL-1.2.")


def test_typographic_hyphens_in_a_draft_are_made_plain(answer):
    answer["result"] = {"text": "The Fire NOC was valid until 31/03/2026. Clause ILL\u20111.2 asks for certificates in force.",
                        "clause_refs": ["ILL-1.2"]}
    out = clauses.explain(FINDING, RULE, clauses.retrieve(FINDING, RULE, LIBRARY))
    assert out["by"] == "llm" and "ILL-1.2" in out["text"]


def test_a_draft_citing_a_clause_it_was_not_given_fails():
    assert not _check("The Fire NOC was valid until 31/03/2026.", refs=("ILL-9.9",))


def test_a_draft_longer_than_three_sentences_fails():
    assert not _check("One. Two. Three. Four.")


# The explanation --------------------------------------------------------------------------------

def test_a_grounded_draft_is_returned_as_written_by_ai(answer):
    answer["result"] = {"text": "The Fire NOC was valid until 31/03/2026. Clause ILL-1.2 asks for certificates in force.",
                        "clause_refs": ["ILL-1.2"]}
    out = clauses.explain(FINDING, RULE, clauses.retrieve(FINDING, RULE, LIBRARY))
    assert out["by"] == "llm" and out["clause_refs"] == ["ILL-1.2"]


@pytest.mark.parametrize("result", [None, {"text": "It lapsed 214 days early.", "clause_refs": []},
                                    {"text": "Looks forged.", "clause_refs": []}])
def test_otherwise_the_template_from_the_record_is_returned(answer, result):
    answer["result"] = result
    out = clauses.explain(FINDING, RULE, clauses.retrieve(FINDING, RULE, LIBRARY))
    assert out["by"] == "rules" and out["clause_refs"] == ["ILL-1.2"]
    assert out["text"].startswith(FINDING["detail"]) and "ILL-1.2 (Certificates in force)" in out["text"]
    assert clauses.grounded(out["text"], out["clause_refs"], clauses._material(FINDING, RULE, LIBRARY), {"ILL-1.2"})


def test_with_no_clause_the_model_is_not_asked(answer):
    out = clauses.explain(FINDING, RULE, [])
    assert answer["calls"] == 0 and out["by"] == "rules" and "no clause in the library yet" in out["text"]


# The API ----------------------------------------------------------------------------------------

API = "/api/v1"


@pytest.fixture
def seeded(fake):
    fake.table("rules").insert([{**RULE, "id": "r-1", "status": "active"}]).execute()
    fake.table("regulation_clauses").insert(LIBRARY).execute()
    fake.table("findings").insert([{k: v for k, v in FINDING.items() if k != "evidence"}
                                   | {"finding_key": "EXP|f", "status": "open", "is_cross_institution": False,
                                      "severity": "high", "created_at": "2026-10-02"}]).execute()
    return fake


def test_a_reviewer_sees_the_clauses_behind_a_finding(seeded, client, as_user):
    as_user("reviewer")
    body = client.get(f"{API}/findings/f-1/clauses").json()
    assert body["rule"]["title"] == "Certificate expired" and body["clauses"][0]["clause_ref"] == "ILL-1.2"


def test_an_institution_cannot_ask(seeded, client, as_user):
    as_user("institution_b")
    assert client.get(f"{API}/findings/f-1/clauses").status_code == 403
    assert client.post(f"{API}/findings/f-1/explanation").status_code == 403


def test_a_draft_is_recorded_in_the_audit_trail(seeded, client, as_user, answer):
    as_user("reviewer")
    body = client.post(f"{API}/findings/f-1/explanation").json()
    assert body["explanation"]["by"] == "rules"
    event = [e for e in seeded.rows("audit_events") if e["event_type"] == "explanation_drafted"][-1]
    assert event["entity_id"] == "f-1" and event["detail"]["clause_refs"] == ["ILL-1.2"]


def test_a_rule_administrator_adds_a_clause_with_a_reason(seeded, client, as_user):
    clause = {"clause_ref": "ILL-6.1", "source": "Illustrative", "heading": "Library hours",
              "body": "The library shall be open for at least the hours of instruction.", "rule_codes": ["r-exp-01"],
              "reason": "for the demonstration"}
    as_user("reviewer")
    assert client.post(f"{API}/admin/clauses", json=clause).status_code == 403
    as_user("rule_admin")
    res = client.post(f"{API}/admin/clauses", json=clause)
    assert res.status_code == 201 and res.json()["rule_codes"] == ["R-EXP-01"]
    assert client.post(f"{API}/admin/clauses", json=clause).status_code == 409
    assert client.post(f"{API}/admin/clauses", json={**clause, "clause_ref": "ILL-6.2", "rule_codes": ["R-NONE"]}).status_code == 422
    assert any(e["event_type"] == "clause_added" for e in seeded.rows("audit_events"))


def test_without_the_library_the_api_says_so(seeded, client, as_user, monkeypatch):
    monkeypatch.setattr(clauses, "load", lambda: None)
    as_user("reviewer")
    res = client.get(f"{API}/findings/f-1/clauses")
    assert res.status_code == 503 and "0009" in res.json()["detail"]
