"""Phase 5: signature and metadata checks (C13, C14) on real signed PDFs from the fictional demo PKI;
the rule lifecycle with four-eyes approval; the impact preview, which writes nothing; drafting a rule
from pasted text (grounded LLM reading or the rule-based fallback); and the audited settings."""
import pymupdf
import pytest

from seed import signing
from services import forensics, llm, rules as rules_service
from services.validation import evaluate, load_context, run_validation

API = "/api/v1"
CODE = "INST-1001-2027-28-01"


def _pdf(text: str = "Approval certificate AICTE/2025/0417", created: str = "D:20250401100000+05'30'",
         modified: str = "D:20250401100000+05'30'") -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.set_metadata({"title": "Demo", "creationDate": created, "modDate": modified})
    return doc.tobytes()


@pytest.fixture(scope="module")
def trusted():
    return [{"pem": signing.root_pem().decode(), "name": "Demo root"}]


# Forensics on real files ------------------------------------------------------------------------

def test_a_signature_by_a_trusted_issuer_reads_valid_and_its_metadata_clear(trusted):
    signed = signing.sign(_pdf(), "approval")
    result = forensics.check_signature(signed, forensics.MIME_PDF, trusted)
    assert result["status"] == "valid"
    assert "AICTE approval register signer" in result["signatures"][0]["signer"]
    assert forensics.check_metadata(signed, forensics.MIME_PDF, result)["status"] == "clear"


def test_a_signer_outside_the_trust_store_reads_untrusted_chain(trusted):
    result = forensics.check_signature(signing.sign(_pdf(), signing.UNLISTED), forensics.MIME_PDF, trusted)
    assert result["status"] == "untrusted_chain"


def test_an_empty_trust_store_trusts_nobody():
    assert forensics.check_signature(signing.sign(_pdf(), "approval"), forensics.MIME_PDF, [])["status"] == "untrusted_chain"


def test_a_page_changed_after_signing_reads_invalid_with_a_revision_after_the_signature(trusted):
    signed = signing.sign(_pdf(), "approval")
    changed = signing.change_after_signing(signed, _pdf("Approval certificate AICTE/2025/0417 valid to 31 March 2030"))
    result = forensics.check_signature(changed, forensics.MIME_PDF, trusted)
    assert result["status"] == "invalid"
    codes = [i["code"] for i in forensics.check_metadata(changed, forensics.MIME_PDF, result)["indicators"]]
    assert "updated_after_signing" in codes


def test_unsigned_and_unsupported_files():
    assert forensics.check_signature(_pdf(), forensics.MIME_PDF)["status"] == "unsigned"
    assert forensics.check_signature(b"\x89PNG", "image/png")["status"] == "unsupported"
    assert forensics.check_signature(b"not a pdf at all", forensics.MIME_PDF)["status"] == "unsupported"


def test_metadata_flags_a_creation_date_later_than_the_modification_date():
    data = _pdf(created="D:20260901100000+05'30'", modified="D:20250101100000+05'30'")
    result = forensics.check_metadata(data, forensics.MIME_PDF, forensics.check_signature(data, forensics.MIME_PDF))
    assert result["status"] == "indicators"
    assert [i["code"] for i in result["indicators"]] == ["created_after_modified"]
    assert "01/09/2026" in result["indicators"][0]["text"]


def test_load_certificate_rejects_a_file_that_is_not_one():
    with pytest.raises(ValueError):
        forensics.load_certificate(b"-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----\n")


# C13 and C14 ------------------------------------------------------------------------------------

def _under_review(fake, signature_required=True):
    fake.table("settings").insert([{"key": "as_of", "value": {"mode": "fixed", "date": "2026-11-01"}}]).execute()
    fake.table("document_types").insert([{"code": "approval_certificate", "label": "Approval certificate", "has_expiry": False,
                                          "signature_required": signature_required, "is_photo": False}]).execute()
    fake.table("rules").insert([
        {"id": f"rule-{c}", "rule_code": c, "version": 1, "status": "active", "effective_from": "2026-01-01", "effective_to": None,
         "params": {}, "check_type": t}
        for c, t in (("R-SIG-01", "signature"), ("R-META-01", "metadata"))
    ]).execute()
    fake.table("documents").insert([{"id": "cert-a", "application_id": "app-a", "doc_type": "approval_certificate", "version": 1,
                                     "status": "current", "integrity_status": "passed", "sha256": "c" * 64, "uploaded_at": "2026-10-01",
                                     "original_name": "certificate.pdf", "mime": "application/pdf",
                                     "storage_path": "inst-a/app-a/cert-a.pdf"}]).execute()
    fake.table("applications").update({"workflow_status": "under_review", "review_deadline": "2026-12-01"}).eq("id", "app-a").execute()


def _check(fake, method, status, response=None, doc="cert-a"):
    fake.table("verification_checks").insert([{"document_id": doc, "method": method, "status": status, "is_mock": False,
                                               "response": response or {}, "checked_at": "2026-10-20"}]).execute()


def _keys(fake, reviewer=True):
    application = fake.rows("applications")[0]
    return {f.key for f in evaluate(load_context(application, include_cross=False, reviewer=reviewer), include_cross=reviewer)[0]}


def test_c13_an_invalid_signature_is_a_high_finding_naming_the_signer(fake):
    _under_review(fake)
    _check(fake, "SIGNATURE", "invalid", {"note": "The signed content does not match the signature",
                                          "signatures": [{"signer": "Common Name: Approval signer"}]})
    application = fake.rows("applications")[0]
    findings = evaluate(load_context(application, include_cross=False, reviewer=True), include_cross=False)[0]
    f = next(f for f in findings if f.finding_type == "SIGNATURE_INVALID")
    assert f.key == f"SIGNATURE_INVALID|{CODE}|approval_certificate" and f.severity == "high"
    assert "Approval signer" in f.detail and f.rule_code == "R-SIG-01"


@pytest.mark.parametrize("status,required,flagged", [
    ("valid", True, False), ("unsupported", True, False), ("untrusted_chain", False, True),
    ("unsigned", True, True), ("unsigned", False, False),
])
def test_c13_which_signature_results_are_findings(fake, status, required, flagged):
    _under_review(fake, signature_required=required)
    _check(fake, "SIGNATURE", status)
    assert (f"SIGNATURE_INVALID|{CODE}|approval_certificate" in _keys(fake)) is flagged


def test_c13_a_document_not_checked_yet_is_not_a_finding(fake):
    _under_review(fake)
    assert not {k for k in _keys(fake) if k.startswith("SIGNATURE_INVALID")}


def test_c13_uses_the_latest_check_only(fake):
    _under_review(fake)
    _check(fake, "SIGNATURE", "invalid")
    fake.table("verification_checks").insert([{"document_id": "cert-a", "method": "SIGNATURE", "status": "valid", "is_mock": False,
                                               "response": {}, "checked_at": "2026-10-25"}]).execute()
    assert not {k for k in _keys(fake) if k.startswith("SIGNATURE_INVALID")}


def test_c14_metadata_indicators_are_a_low_finding_for_reviewers_but_not_in_preflight(fake):
    _under_review(fake)
    _check(fake, "METADATA", "indicators", {"indicators": [{"code": "created_after_modified", "text": "Creation date is later"}]})
    _check(fake, "SIGNATURE", "invalid")
    reviewer_keys = _keys(fake)
    assert any(k.startswith("METADATA_ANOMALY") for k in reviewer_keys), reviewer_keys
    institution_keys = _keys(fake, reviewer=False)
    assert not any(k.startswith("METADATA_ANOMALY") for k in institution_keys)
    assert f"SIGNATURE_INVALID|{CODE}|approval_certificate" in institution_keys      # pre-flight shows C13


def test_preflight_lists_a_signature_finding_but_no_metadata_indicator(fake, client, as_user):
    _under_review(fake)
    fake.table("applications").update({"workflow_status": "draft"}).eq("id", "app-a").execute()
    _check(fake, "SIGNATURE", "untrusted_chain")
    _check(fake, "METADATA", "indicators", {"indicators": [{"code": "updated_after_signing", "text": "1 revision added"}]})
    as_user("institution_a")
    res = client.post(f"{API}/applications/app-a/preflight")
    assert res.status_code == 200, res.text
    types = {i["finding_type"] for i in res.json()["items"]}
    assert "SIGNATURE_INVALID" in types and "METADATA_ANOMALY" not in types


def test_recheck_signature_endpoint_records_both_checks_and_revalidates(fake, client, as_user, trusted):
    _under_review(fake)
    fake.table("settings").insert([{"key": "trust_store", "value": {"certificates": trusted}}]).execute()
    fake.storage.files["inst-a/app-a/cert-a.pdf"] = signing.sign(_pdf(), signing.UNLISTED)
    run_validation("app-a", "full")
    as_user("institution_a")
    assert client.post(f"{API}/documents/cert-a/verify/signature").status_code == 403
    as_user("reviewer")
    res = client.post(f"{API}/documents/cert-a/verify/signature")
    assert res.status_code == 200, res.text
    methods = {c["method"]: c["status"] for c in fake.rows("verification_checks")}
    assert methods == {"SIGNATURE": "untrusted_chain", "METADATA": "clear"}
    assert any(e["p_type"] == "signature_checked" for e in fake.audit)
    assert any(f["finding_type"] == "SIGNATURE_INVALID" and f["status"] == "open" for f in fake.rows("findings"))


# Rule lifecycle ---------------------------------------------------------------------------------

def _area_rule(fake):
    fake.table("settings").insert([{"key": "as_of", "value": {"mode": "fixed", "date": "2026-11-01"}}]).execute()
    fake.table("rules").insert([{"id": "area-1", "rule_code": "R-AREA-01", "version": 1, "status": "active", "check_type": "area_check",
                                 "title": "Built-up area", "description": "Rooms add up", "severity": "medium",
                                 "params": {"area_tolerance_pct": 1, "min_area_sqm": 0}, "effective_from": "2026-01-01",
                                 "effective_to": None, "created_by": "user-admin", "approved_by": "user-admin-2"}]).execute()


def _draft(client, **changes):
    res = client.post(f"{API}/rules", json={"from_rule_id": "area-1", "reason": "New minimum area", **changes})
    assert res.status_code == 201, res.text
    return res.json()


def test_rules_are_for_rule_administrators_only(fake, client, as_user):
    _area_rule(fake)
    for role in ("reviewer", "institution_a"):
        as_user(role)
        assert client.get(f"{API}/rules").status_code == 403


def test_full_lifecycle_with_four_eyes(fake, client, as_user):
    _area_rule(fake)
    as_user("rule_admin")
    draft = _draft(client, params={"min_area_sqm": 4000})
    assert (draft["version"], draft["status"], draft["params"]["min_area_sqm"]) == (2, "draft", 4000)
    assert draft["params"]["area_tolerance_pct"] == 1                                   # kept from version 1
    assert client.post(f"{API}/rules", json={"from_rule_id": "area-1", "reason": "again"}).status_code == 409

    rid = draft["id"]
    assert client.post(f"{API}/rules/{rid}/activate", json={"reason": "too soon"}).status_code == 409
    assert client.post(f"{API}/rules/{rid}/submit", json={"reason": "Ready"}).status_code == 200
    res = client.post(f"{API}/rules/{rid}/approve", json={"reason": "my own"})
    assert res.status_code == 403 and "another rule administrator" in res.json()["detail"]
    assert client.post(f"{API}/rules/{rid}/activate", json={"reason": "not approved"}).status_code == 409

    as_user("rule_admin_2")
    assert client.put(f"{API}/rules/{rid}", json={"title": "Changed"}).status_code == 409   # not a draft any more
    assert client.post(f"{API}/rules/{rid}/approve", json={"reason": "Checked against the clause"}).status_code == 200
    res = client.post(f"{API}/rules/{rid}/activate", json={"reason": "Start now"})
    assert res.status_code == 200, res.text

    by_id = {r["id"]: r for r in fake.rows("rules")}
    assert (by_id[rid]["status"], by_id[rid]["effective_from"], by_id[rid]["approved_by"]) == ("active", "2026-11-01", "user-admin-2")
    assert (by_id["area-1"]["status"], by_id["area-1"]["effective_to"]) == ("retired", "2026-10-31")
    events = [e["p_type"] for e in fake.audit]
    for e in ("rule_drafted", "rule_submitted", "rule_approved", "rule_activated"):
        assert e in events
    assert any(n["user_id"] == "user-admin-2" for n in fake.rows("notifications"))            # asked to approve


def test_only_the_author_edits_and_params_are_checked(fake, client, as_user):
    _area_rule(fake)
    as_user("rule_admin")
    rid = _draft(client)["id"]
    assert client.put(f"{API}/rules/{rid}", json={"params": {"min_area_sqm": -5}}).status_code == 422
    assert client.put(f"{API}/rules/{rid}", json={"params": {"similarity": 0.9}}).status_code == 422
    assert client.put(f"{API}/rules/{rid}", json={"severity": "critical"}).status_code == 422
    assert client.put(f"{API}/rules/{rid}", json={"params": {"min_area_sqm": 4200}}).json()["params"]["min_area_sqm"] == 4200
    as_user("rule_admin_2")
    assert client.put(f"{API}/rules/{rid}", json={"title": "Mine now"}).status_code == 403


def test_a_returned_version_goes_back_to_draft(fake, client, as_user):
    _area_rule(fake)
    as_user("rule_admin")
    rid = _draft(client)["id"]
    client.post(f"{API}/rules/{rid}/submit", json={"reason": "Ready"})
    assert client.post(f"{API}/rules/{rid}/return", json={"reason": "mine"}).status_code == 403
    as_user("rule_admin_2")
    assert client.post(f"{API}/rules/{rid}/return", json={"reason": "Cite the clause"}).json()["status"] == "draft"


def test_an_old_run_keeps_the_rule_version_it_used(fake, client, as_user):
    _area_rule(fake)
    fake.table("applications").update({"workflow_status": "under_review", "review_deadline": "2026-12-01",
                                       "declared_total_area_sqm": 3600}).eq("id", "app-a").execute()
    run_validation("app-a", "full")
    as_user("rule_admin")
    rid = _draft(client, params={"min_area_sqm": 4000})["id"]
    client.post(f"{API}/rules/{rid}/submit", json={"reason": "Ready"})
    as_user("rule_admin_2")
    client.post(f"{API}/rules/{rid}/approve", json={"reason": "Checked"})
    client.post(f"{API}/rules/{rid}/activate", json={"reason": "Start now"})
    run_validation("app-a", "full")
    runs = fake.rows("validation_runs")
    assert [r["rule_versions"]["R-AREA-01"] for r in runs] == [1, 2]
    assert any(f["finding_type"] == "AREA_BELOW_MINIMUM" and f["rule_version"] == 2 for f in fake.rows("findings"))


def test_impact_preview_reports_created_findings_and_writes_nothing(fake, client, as_user):
    _area_rule(fake)
    fake.table("applications").update({"workflow_status": "under_review", "declared_total_area_sqm": 3600}).eq("id", "app-a").execute()
    as_user("rule_admin")
    rid = _draft(client, params={"min_area_sqm": 4000})["id"]
    before = {t: len(fake.rows(t)) for t in ("findings", "validation_runs")}
    audit_before = len(fake.audit)
    res = client.get(f"{API}/rules/{rid}/impact")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] and body["compared_with"] == 1
    assert body["totals"]["created"] == 1 and body["totals"]["closed"] == 0
    assert body["applications"][0]["code"] == CODE
    assert body["applications"][0]["created"][0]["key"] == f"AREA_BELOW_MINIMUM|{CODE}|minimum"
    assert {t: len(fake.rows(t)) for t in before} == before and len(fake.audit) == audit_before


def test_impact_is_not_offered_for_an_active_version_or_the_extraction_rule(fake, client, as_user):
    _area_rule(fake)
    fake.table("rules").insert([{"id": "ocr-1", "rule_code": "R-OCR-01", "version": 1, "status": "draft", "check_type": "extraction",
                                 "params": {"min_confidence": 0.8}}]).execute()
    as_user("rule_admin")
    assert client.get(f"{API}/rules/area-1/impact").status_code == 409
    assert client.get(f"{API}/rules/ocr-1/impact").json()["available"] is False


# Drafting from pasted text ----------------------------------------------------------------------

CLAUSE = "The total built-up area shall be not less than 4,500 sq m for an institution of this intake."
TEXT = f"Section 3. Infrastructure. {CLAUSE} Rooms are listed in the annexure."


def test_draft_from_text_falls_back_to_rules_without_the_llm(fake, client, as_user, monkeypatch):
    _area_rule(fake)
    monkeypatch.setattr(llm, "_complete", lambda *a, **k: None)
    as_user("rule_admin")
    res = client.post(f"{API}/rules/draft-from-text", json={"text": TEXT, "source_reference": "Illustrative handbook 3.2"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["drafted_by"] == "rules"
    assert body["rule"]["status"] == "draft" and body["rule"]["params"]["min_area_sqm"] == 4500
    assert body["rule"]["clause"] == CLAUSE
    assert any(e["p_type"] == "rule_drafted_from_text" for e in fake.audit)


def test_a_grounded_llm_draft_is_used(fake, monkeypatch):
    monkeypatch.setattr(llm, "_complete", lambda *a, **k: {"check_type": "area_check", "params": {"min_area_sqm": 4500},
                                                            "title": "Minimum built-up area", "description": "d", "clause": CLAUSE})
    draft, how = rules_service.draft_from_text(TEXT, {"area_check": {}})
    assert how == "llm" and draft["params"] == {"min_area_sqm": 4500.0}


@pytest.mark.parametrize("bad", [
    {"clause": "The total built-up area shall be at least 5,000 sq m.", "params": {"min_area_sqm": 5000}},   # not in the text
    {"clause": CLAUSE, "params": {"min_area_sqm": 5000}},                                                     # number not in clause
    {"clause": CLAUSE, "params": {"min_area_sqm": 4500}, "check_type": "unknown_check"},
])
def test_an_ungrounded_llm_draft_is_replaced_by_the_rule_based_reading(fake, monkeypatch, bad):
    monkeypatch.setattr(llm, "_complete", lambda *a, **k: {"check_type": "area_check", "title": "t", "description": "d", **bad})
    draft, how = rules_service.draft_from_text(TEXT, {"area_check": {}})
    assert how == "rules" and draft["params"] == {"min_area_sqm": 4500.0}


def test_text_with_no_threshold_is_refused(fake, client, as_user, monkeypatch):
    _area_rule(fake)
    monkeypatch.setattr(llm, "_complete", lambda *a, **k: None)
    as_user("rule_admin")
    res = client.post(f"{API}/rules/draft-from-text", json={"text": "Institutions shall maintain a clean campus at all times.",
                                                              "source_reference": "Illustrative"})
    assert res.status_code == 422


# Settings ---------------------------------------------------------------------------------------

def test_settings_changes_are_for_rule_administrators_and_audited(fake, client, as_user):
    fake.table("priority_weights").insert([{"key": "severity", "weight": 40}, {"key": "deadline", "weight": 20}]).execute()
    as_user("reviewer")
    assert client.get(f"{API}/admin/settings").status_code == 200
    assert client.put(f"{API}/admin/settings/as-of", json={"mode": "today", "reason": "Live"}).status_code == 403
    as_user("institution_a")
    assert client.get(f"{API}/admin/settings").status_code == 403

    as_user("rule_admin")
    assert client.put(f"{API}/admin/settings/as-of", json={"mode": "fixed", "reason": "Demo"}).status_code == 422
    res = client.put(f"{API}/admin/settings/as-of", json={"mode": "fixed", "date": "2026-11-01", "reason": "Repeatable demo"})
    assert res.json()["effective"] == "2026-11-01"
    assert client.put(f"{API}/admin/settings/priority-weights", json={"weights": {"severity": 101}, "reason": "x y"}).status_code == 422
    assert client.put(f"{API}/admin/settings/priority-weights", json={"weights": {"nope": 1}, "reason": "x y"}).status_code == 422
    client.put(f"{API}/admin/settings/priority-weights", json={"weights": {"severity": 50, "deadline": 20}, "reason": "Severity first"})
    assert {w["key"]: w["weight"] for w in fake.rows("priority_weights")} == {"severity": 50, "deadline": 20}

    changes = [e["p_detail"] for e in fake.audit if e["p_type"] == "setting_changed"]
    assert changes[0]["to"] == {"mode": "fixed", "date": "2026-11-01"} and changes[0]["reason"] == "Repeatable demo"
    assert changes[1] == {"from": {"severity": 40}, "to": {"severity": 50}, "reason": "Severity first"}


def test_checklist_and_document_type_flags(fake, client, as_user):
    fake.table("categories").insert([{"code": "extension_of_approval", "label": "Extension of approval"}]).execute()
    as_user("rule_admin")
    body = {"category": "extension_of_approval", "doc_type": "infrastructure_photo", "required": True, "reason": "Photos needed"}
    assert len(client.put(f"{API}/admin/settings/checklist", json=body).json()) == 2
    assert len(client.put(f"{API}/admin/settings/checklist", json={**body, "required": False}).json()) == 1
    res = client.put(f"{API}/admin/settings/document-types/application_form", json={"signature_required": True, "reason": "Signed forms"})
    assert res.json()["signature_required"] is True
    assert client.put(f"{API}/admin/settings/document-types/nope", json={"has_expiry": True, "reason": "x y"}).status_code == 404


def test_template_patterns_are_checked_before_saving(fake, client, as_user):
    fake.table("extraction_templates").insert([{"id": "t-1", "doc_type": "application_form", "field_name": "institution_code",
                                                "regex": r"Code:\s*(\S+)", "group_index": 1, "required": True}]).execute()
    as_user("rule_admin")
    assert client.put(f"{API}/admin/settings/templates/t-1", json={"regex": "Code:\\s*([", "reason": "typo"}).status_code == 422
    assert client.put(f"{API}/admin/settings/templates/t-1", json={"regex": "Code:\\s*\\S+", "reason": "no group"}).status_code == 422
    res = client.put(f"{API}/admin/settings/templates/t-1", json={"regex": "Institution code:\\s*(\\S+)", "reason": "Wording changed"})
    assert res.status_code == 200 and res.json()["regex"] == "Institution code:\\s*(\\S+)"


def test_trust_store_add_and_remove(fake, client, as_user):
    pem = signing.root_pem()
    as_user("rule_admin")
    res = client.post(f"{API}/admin/settings/trust-store", files={"certificate": ("root.pem", pem)},
                      data={"name": "Demo root", "reason": "Trust the demo issuers"})
    assert res.status_code == 201, res.text
    fingerprint = res.json()["fingerprint"]
    assert "pem" not in res.json() and res.json()["is_ca"] is True
    assert client.post(f"{API}/admin/settings/trust-store", files={"certificate": ("root.pem", pem)},
                       data={"name": "Again", "reason": "Twice"}).status_code == 409
    assert client.post(f"{API}/admin/settings/trust-store", files={"certificate": ("x.pem", b"nonsense")},
                       data={"name": "Bad", "reason": "Not one"}).status_code == 422
    assert len(forensics.trust_store()) == 1
    assert client.post(f"{API}/admin/settings/trust-store/{fingerprint}/remove", json={"reason": "No longer used"}).json() == []
    assert forensics.trust_store() == []
    assert sum(e["p_type"] == "setting_changed" for e in fake.audit) == 2
