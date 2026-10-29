"""Checks C1 to C6, one passing and one failing case each, plus statuses and priority (build spec 7 and 17)."""
from datetime import date

from services import priority, statuses
from services.validation import Context, evaluate

AS_OF = date(2026, 11, 1)
RULES = {code: {"rule_code": code, "version": 1} for code in
         ("R-DOC-REQ", "R-EXP-01", "R-DATE-01", "R-PAIR-01", "R-OCR-01", "R-DUP-01")}
DOC_TYPES = {
    "application_form": {"code": "application_form", "label": "Application form", "has_expiry": False},
    "approval_certificate": {"code": "approval_certificate", "label": "Approval certificate", "has_expiry": True},
    "fire_noc": {"code": "fire_noc", "label": "Fire NOC", "has_expiry": True},
    "faculty_list": {"code": "faculty_list", "label": "Faculty list", "has_expiry": False},
    "floor_plan": {"code": "floor_plan", "label": "Floor plan", "has_expiry": False},
}
PAIRS = [
    {"pair_code": "CERT_VALIDITY", "rule_code": "R-PAIR-01", "finding_type": "DATE_CONFLICT", "label": "Approval certificate validity",
     "doc_type_a": "application_form", "field_a": "declared_certificate_valid_until", "doc_type_b": "approval_certificate", "field_b": "expiry_date"},
    {"pair_code": "INST_CODE", "rule_code": "R-PAIR-01", "finding_type": "ID_MISMATCH", "label": "Institution code",
     "doc_type_a": "application_form", "field_a": "institution_code", "doc_type_b": "approval_certificate", "field_b": "institution_code"},
    {"pair_code": "FACULTY_COUNT", "rule_code": "R-PAIR-01", "finding_type": "COUNT_CONFLICT", "label": "Faculty count",
     "doc_type_a": "application_form", "field_a": "declared_faculty_count", "doc_type_b": "faculty_list", "field_b": "faculty_total"},
]


def doc(id_, doc_type, sha=None, status="passed", name=None):
    return {"id": id_, "doc_type": doc_type, "integrity_status": status, "sha256": sha or f"sha-{id_}", "version": 1,
            "original_name": name or f"{doc_type}.pdf", "integrity_note": "content is image/png" if status == "failed" else None}


def fld(name, value, original=None, vtype="text", page=1, state="auto", reason=None):
    return {"field_name": name, "field_value": value, "original_value": original or value, "value_type": vtype,
            "page_number": page, "review_state": state, "review_reason": reason}


def clean() -> dict:
    """A consistent application: every check passes."""
    return {
        "documents": [doc("form", "application_form"), doc("cert", "approval_certificate"), doc("noc", "fire_noc"),
                      doc("fac", "faculty_list"), doc("plan", "floor_plan")],
        "fields": {
            "form": [fld("institution_code", "INST-1001"), fld("declared_faculty_count", "24", vtype="int"),
                     fld("declared_certificate_valid_until", "2028-03-31", "31 March 2028", "date")],
            "cert": [fld("institution_code", "INST 1001"), fld("issue_date", "2025-04-01", vtype="date"),
                     fld("expiry_date", "2028-03-31", "31/03/2028", "date", page=2)],
            "noc": [fld("issue_date", "2026-01-10", vtype="date"), fld("expiry_date", "2027-01-09", vtype="date")],
            "fac": [fld("faculty_total", "24", vtype="int", page=3)],
        },
    }


def ctx(data: dict) -> Context:
    required = [{"doc_type": t, "mandatory": True} for t in ("application_form", "approval_certificate", "fire_noc", "faculty_list", "floor_plan")]
    return Context(application={"id": "app", "code": "APP-1"}, as_of=AS_OF, documents=data["documents"], fields=data["fields"],
                   doc_types=DOC_TYPES, required=required, pairs=PAIRS, rules=RULES, category_label="Extension of approval")


def keys(data) -> set[str]:
    return {f.key for f in evaluate(ctx(data))[0]}


def test_clean_application_has_no_findings():
    assert keys(clean()) == set()


def test_c1_missing_document():
    data = clean()
    data["documents"] = [d for d in data["documents"] if d["doc_type"] != "fire_noc"]
    assert keys(data) == {"MISSING_DOCUMENT|APP-1|fire_noc"}


def test_c1_document_that_failed_the_file_check_counts_as_missing():
    data = clean()
    data["documents"][2]["integrity_status"] = "failed"
    findings = evaluate(ctx(data))[0]
    assert [f.key for f in findings] == ["MISSING_DOCUMENT|APP-1|fire_noc"]
    assert "failed the file check" in findings[0].detail


def test_c2_expired_document():
    data = clean()
    data["fields"]["noc"][1] = fld("expiry_date", "2026-03-31", "31 March 2026", "date", page=1)
    findings = evaluate(ctx(data))[0]
    assert [f.key for f in findings] == ["EXPIRED_DOCUMENT|APP-1|fire_noc"]
    assert "31/03/2026" in findings[0].title and "01/11/2026" in findings[0].detail
    assert findings[0].evidence[0]["page_number"] == 1 and findings[0].evidence[0]["shown_value"] == "31 March 2026"


def test_c3_expiry_before_issue():
    data = clean()
    data["fields"]["noc"] = [fld("issue_date", "2027-05-01", vtype="date"), fld("expiry_date", "2027-01-01", vtype="date")]
    assert keys(data) == {"DATE_ORDER_INVALID|APP-1|fire_noc"}


def test_c4_date_conflict_cites_both_pages():
    data = clean()
    data["fields"]["form"][2] = fld("declared_certificate_valid_until", "2029-03-31", "31 March 2029", "date")
    findings = evaluate(ctx(data))[0]
    assert [f.key for f in findings] == ["DATE_CONFLICT|APP-1|CERT_VALIDITY"]
    a, b = findings[0].evidence
    assert (a["role"], a["shown_value"], a["page_number"]) == ("A", "31 March 2029", 1)
    assert (b["role"], b["shown_value"], b["page_number"]) == ("B", "31/03/2028", 2)
    assert "candidate for review" in findings[0].detail.lower()


def test_c4_count_conflict_and_id_mismatch():
    data = clean()
    data["fields"]["fac"] = [fld("faculty_total", "22", vtype="int", page=3)]
    data["fields"]["cert"][0] = fld("institution_code", "INST-1010")
    assert keys(data) == {"COUNT_CONFLICT|APP-1|FACULTY_COUNT", "ID_MISMATCH|APP-1|INST_CODE"}


def test_c4_ignores_separators_and_formatting():
    data = clean()   # "INST-1001" against "INST 1001", "31 March 2028" against "31/03/2028"
    assert not [k for k in keys(data) if k.startswith(("ID_MISMATCH", "DATE_CONFLICT"))]


def test_c5_value_needing_confirmation_is_listed_not_compared():
    data = clean()
    data["fields"]["cert"][2] = fld("expiry_date", "2029-08-03", "03/08/2029", "date", state="needs_confirmation",
                                    reason='"03/08/2029" could be 3 August 2029 or 8 March 2029')
    findings = evaluate(ctx(data))[0]
    assert [f.key for f in findings] == ["FIELD_NEEDS_CONFIRMATION|APP-1|approval_certificate.expiry_date"]
    assert "3 August 2029 or 8 March 2029" in findings[0].detail


def test_c6_duplicate_file():
    data = clean()
    data["documents"][4]["sha256"] = data["documents"][3]["sha256"] = "ab" * 32
    findings = evaluate(ctx(data))[0]
    assert [f.key for f in findings] == [f"DUPLICATE_FILE|APP-1|{'ab' * 8}"]
    assert {e["role"] for e in findings[0].evidence} == {"A", "B"}


def test_inactive_rule_does_not_run():
    data = clean()
    data["documents"] = [d for d in data["documents"] if d["doc_type"] != "fire_noc"]
    c = ctx(data)
    c.rules = {k: v for k, v in RULES.items() if k != "R-DOC-REQ"}
    findings, evaluated = evaluate(c)
    assert findings == [] and "MISSING_DOCUMENT" not in evaluated


def test_findings_never_state_a_conclusion():
    data = clean()
    data["documents"] = [d for d in data["documents"] if d["doc_type"] != "fire_noc"]
    data["fields"]["fac"] = [fld("faculty_total", "22", vtype="int")]
    text = " ".join(f.title + " " + f.detail for f in evaluate(ctx(data))[0]).lower()
    for word in ("fraud", "forged", "fake", "approve", "reject"):
        assert word not in text


# Statuses ----------------------------------------------------------------------------------------

def _statuses(findings, documents=None, fields=None, checks=None, has_run=True):
    out = statuses.compute(has_run, findings, documents or [], fields or [], set(), checks or [])
    return {s["key"]: s["value"] for s in out["statuses"]}


def test_statuses_read_not_run_yet_before_the_first_run():
    assert set(_statuses([], has_run=False).values()) == {"Not run yet"}


def test_statuses_are_independent():
    conflict = {"finding_type": "COUNT_CONFLICT", "status": "open", "title": "Faculty count differs"}
    s = _statuses([conflict], documents=[doc("a", "application_form")])
    assert s == {"integrity": "Passed", "consistency": "Conflict detected", "authenticity": "Not yet verified",
                 "compliance": "Meets configured checks"}


def test_resolved_findings_do_not_count():
    resolved = {"finding_type": "MISSING_DOCUMENT", "status": "resolved", "title": "Fire NOC not received"}
    assert _statuses([resolved])["compliance"] == "Meets configured checks"
    assert _statuses([{**resolved, "status": "evidence_requested"}])["compliance"] == "Review required"


def test_unavailable_registry_is_pending_not_failure():
    checks = [{"document_id": "a", "method": "REGISTRY", "status": "unavailable", "is_mock": True, "checked_at": "1"}]
    assert _statuses([], checks=checks)["authenticity"] == "Pending (source unavailable) (MOCK source)"


def test_open_signature_finding_outweighs_a_valid_signature_elsewhere():
    # An unsigned affidavit (its type requires a signature) next to a validly signed certificate
    checks = [{"document_id": "a", "method": "SIGNATURE", "status": "valid", "checked_at": "1"},
              {"document_id": "b", "method": "SIGNATURE", "status": "unsigned", "checked_at": "1"}]
    unsigned = {"finding_type": "SIGNATURE_INVALID", "status": "open",
                "title": "Affidavit has no digital signature; this document type requires one"}
    assert _statuses([unsigned], checks=checks)["authenticity"] == "Signature missing"
    assert _statuses([{**unsigned, "status": "dismissed"}], checks=checks)["authenticity"] == "Signature valid"


def test_value_waiting_for_confirmation_is_inconclusive():
    fields = [{"doc_type": "approval_certificate", "field_name": "issue_date", "field_value": "2025-08-03",
               "review_state": "needs_confirmation"}]
    assert _statuses([], fields=fields)["consistency"] == "Inconclusive"


def test_administrative_status_is_always_pending():
    out = statuses.compute(True, [], [], [], set(), [])
    assert out["administrative"] == "Pending (authorised AICTE official)"


# Priority ----------------------------------------------------------------------------------------

WEIGHTS = {"missing_document": 30, "conflict": 20, "needs_confirmation": 10, "duplicate": 10}


def test_priority_composition_and_deadline_bonus():
    findings = [{"finding_type": "MISSING_DOCUMENT", "status": "open"},
                {"finding_type": "COUNT_CONFLICT", "status": "evidence_requested"},
                {"finding_type": "DUPLICATE_FILE", "status": "dismissed"}]
    p = priority.compute(findings, WEIGHTS, "2026-11-06", AS_OF)
    assert p["score"] == 30 + 20 + 5 + 20 and p["band"] == "High"
    assert [t["key"] for t in p["composition"]] == ["missing_document", "conflict", "additional", "deadline"]
    assert sum(t["contribution"] for t in p["composition"]) == p["score"]


def test_priority_caps_at_100_and_bands():
    many = [{"finding_type": "MISSING_DOCUMENT", "status": "open"}] * 5
    p = priority.compute(many, WEIGHTS, None, AS_OF)
    assert p["score"] == 100 and p["capped"]
    assert priority.compute([], WEIGHTS, "2026-11-12", AS_OF) == {**priority.compute([], WEIGHTS, "2026-11-12", AS_OF)}
    assert priority.compute([], WEIGHTS, "2026-11-12", AS_OF)["score"] == 10      # due in 11 days
    assert priority.band(59) == "Medium" and priority.band(29) == "Low"
