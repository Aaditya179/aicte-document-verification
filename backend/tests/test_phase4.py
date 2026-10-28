"""Phase 4: the issuer registry (MOCK) and manual checks, each with its own state; check C15; the
Authenticity status (an unavailable source is Pending, never a failure); the registry mode setting;
and the institution's pre-flight, which stores nothing."""
import io

from PIL import Image

from services.validation import run_validation

API = "/api/v1"
CODE = "INST-1001-2027-28-01"
C15_KEY = f"REGISTRY_MISMATCH|{CODE}|approval_certificate"


def _certificate(fake, doc_id="cert-a", version=1):
    fake.table("documents").insert([{"id": doc_id, "application_id": "app-a", "doc_type": "approval_certificate", "version": version,
                                     "status": "current", "integrity_status": "passed", "sha256": doc_id * 8, "uploaded_at": f"2026-10-0{version}",
                                     "original_name": "certificate.pdf", "mime": "application/pdf"}]).execute()
    fake.table("extracted_fields").insert([
        {"id": f"{doc_id}-{n}", "document_id": doc_id, "field_name": n, "field_value": v, "original_value": o,
         "value_type": t, "page_number": 1, "review_state": "auto"}
        for n, v, o, t in (("certificate_no", "AICTE/2025/0417", "AICTE/2025/0417", "text"),
                           ("institution_code", "INST-1001", "INST-1001", "text"),
                           ("issue_date", "2025-04-01", "1 April 2025", "date"),
                           ("expiry_date", "2027-03-31", "31 March 2027", "date"))
    ]).execute()


def _submitted(fake):
    """app-a under review, with an approval certificate, R-REG-01 active and one full run done."""
    fake.table("settings").insert([{"key": "as_of", "value": {"mode": "fixed", "date": "2026-11-01"}}]).execute()
    fake.table("priority_weights").insert([{"key": "signature_or_registry", "weight": 30}]).execute()
    fake.table("document_types").insert([{"code": "approval_certificate", "label": "Approval certificate", "has_expiry": True,
                                          "signature_required": True, "is_photo": False}]).execute()
    fake.table("rules").insert([{"rule_code": "R-REG-01", "version": 1, "status": "active", "effective_from": "2026-01-01",
                                 "effective_to": None, "params": {}}]).execute()
    _certificate(fake)
    fake.table("applications").update({"workflow_status": "under_review", "review_deadline": "2026-12-01"}).eq("id", "app-a").execute()
    run_validation("app-a", "full")


def _mode(fake, mode):
    fake.table("settings").upsert({"key": "registry_adapter_mode", "value": mode}, on_conflict="key").execute()


def _authenticity(client):
    return next(s for s in client.get(f"{API}/applications/app-a/statuses").json()["statuses"] if s["key"] == "authenticity")


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(out, "PNG")
    return out.getvalue()


# Registry (MOCK) --------------------------------------------------------------------------------

def test_unavailable_registry_is_the_default_and_reads_pending_never_failed(fake, client, as_user):
    _submitted(fake)
    as_user("reviewer")
    assert _authenticity(client)["value"] == "Not yet verified"
    res = client.post(f"{API}/documents/cert-a/verify/registry")
    assert res.status_code == 200
    check = fake.rows("verification_checks")[-1]
    assert (check["method"], check["status"], check["is_mock"]) == ("REGISTRY", "unavailable", True)
    status = _authenticity(client)
    assert status["value"] == "Pending (source unavailable) (MOCK source)" and status["tone"] == "pending"
    assert "not a failure" in status["reasons"][0]
    assert not [f for f in fake.rows("findings") if f["finding_type"] == "REGISTRY_MISMATCH"]


def test_matching_record_reads_source_verified(fake, client, as_user):
    _submitted(fake)
    _mode(fake, "match")
    as_user("reviewer")
    assert client.post(f"{API}/documents/cert-a/verify/registry").json()["check"]["status"] == "match"
    assert _authenticity(client)["value"] == "Source verified (MOCK source)"


def test_c15_mismatching_record_opens_a_finding_that_closes_when_the_document_is_replaced(fake, client, as_user):
    from services.pipeline import revalidate_after_replacement
    _submitted(fake)
    _mode(fake, "mismatch")
    as_user("reviewer")
    res = client.post(f"{API}/documents/cert-a/verify/registry").json()
    assert res["check"]["status"] == "mismatch" and res["validation"]["created"] == 1
    finding = next(f for f in fake.rows("findings") if f["finding_key"] == C15_KEY)
    assert finding["status"] == "open" and finding["severity"] == "high" and finding["rule_code"] == "R-REG-01"
    assert "31/03/2027" in finding["title"] and "31/03/2026" in finding["title"] and "(MOCK)" in finding["title"]
    evidence = [e for e in fake.rows("finding_evidence") if e["finding_id"] == finding["id"]]
    assert {(e["role"], e["document_id"], e["shown_value"]) for e in evidence} == {("A", "cert-a", "31/03/2027"), ("B", None, "31/03/2026")}
    status = _authenticity(client)
    assert status["value"] == "Source mismatch" and status["tone"] == "conflict"
    assert any(e["p_type"] == "validation_run" and e["p_detail"]["trigger"] == "registry_checked" for e in fake.audit)

    # A replacement has no registry answer yet: the finding closes and the mismatch no longer counts
    fake.table("documents").update({"status": "superseded"}).eq("id", "cert-a").execute()
    _certificate(fake, "cert-a2", version=2)
    revalidate_after_replacement(fake.rows("applications")[0])
    assert next(f for f in fake.rows("findings") if f["finding_key"] == C15_KEY)["status"] == "auto_closed"
    assert _authenticity(client)["value"] == "Not yet verified"


def test_c15_never_runs_in_pre_flight_or_without_registry_answers():
    from tests.test_phase3 import base
    from services.validation import evaluate
    ctx = base()
    ctx.rules = {**ctx.rules, "R-REG-01": {"rule_code": "R-REG-01", "version": 1, "params": {}}}
    ctx.registry = {"land": {"document_id": "land", "status": "mismatch", "is_mock": True, "response": {
        "issuer": "Land records office", "key": {"field": "survey_no", "value": "141/2"},
        "compared": [{"field": "land_area_sqm", "document_value": "20000", "document_shown": "20,000", "page_number": 1,
                      "value_type": "number", "registry_value": "18000", "same": False}]}}}
    assert {f.key for f in evaluate(ctx)[0]} == {"REGISTRY_MISMATCH|APP-1|land_document"}
    assert evaluate(ctx, include_cross=False)[0] == []
    ctx.registry = None
    assert evaluate(ctx)[0] == []


def test_registry_lookup_refuses_what_it_cannot_look_up(fake, client, as_user):
    _submitted(fake)
    fake.table("documents").insert([{"id": "form-a", "application_id": "app-a", "doc_type": "application_form", "version": 1,
                                     "status": "current", "integrity_status": "passed"}]).execute()
    as_user("reviewer")
    assert client.post(f"{API}/documents/form-a/verify/registry").status_code == 422
    fake.table("extracted_fields").update({"review_state": "needs_confirmation"}).eq("id", "cert-a-certificate_no").execute()
    assert client.post(f"{API}/documents/cert-a/verify/registry").status_code == 409
    fake.table("applications").update({"workflow_status": "draft"}).eq("id", "app-a").execute()
    assert client.post(f"{API}/documents/cert-a/verify/registry").status_code == 409
    for role in ("institution_a", "rule_admin"):
        as_user(role)
        assert client.post(f"{API}/documents/cert-a/verify/registry").status_code == 403


# Manual -----------------------------------------------------------------------------------------

def _manual(client, outcome, **files):
    return client.post(f"{API}/documents/cert-a/verify/manual", data={
        "outcome": outcome, "issuer": "AICTE Western Regional Office", "contact": "Phone call to the approvals desk",
        "note": "Desk officer read the register entry aloud"}, files=files or None)


def test_each_method_keeps_its_own_state(fake, client, as_user):
    _submitted(fake)
    as_user("reviewer")
    assert _manual(client, "pending").status_code == 200
    assert _authenticity(client)["value"] == "Manual verification pending"
    _mode(fake, "mismatch")
    client.post(f"{API}/documents/cert-a/verify/registry")
    _manual(client, "confirmed")
    # The manual confirmation does not overwrite the registry answer: the mismatch still shows
    methods = [(c["method"], c["status"]) for c in fake.rows("verification_checks")]
    assert methods == [("MANUAL", "manual_pending"), ("REGISTRY", "mismatch"), ("MANUAL", "manual_confirmed")]
    status = _authenticity(client)
    assert status["value"] == "Source mismatch"
    view = client.get(f"{API}/documents/cert-a/verification").json()
    assert [c["status"] for c in view["checks"]] == ["manual_confirmed", "mismatch", "manual_pending"]
    assert view["registry"] == {"supported": True, "issuer": "AICTE approval register", "key_field": "certificate_no",
                                "mode": "mismatch", "is_mock": True}


def test_issuer_not_confirming_reads_source_mismatch(fake, client, as_user):
    _submitted(fake)
    as_user("reviewer")
    _manual(client, "not_confirmed")
    status = _authenticity(client)
    assert status["value"] == "Source mismatch" and "did not confirm" in status["reasons"][0]


def test_manual_check_with_attachment(fake, client, as_user):
    _submitted(fake)
    as_user("reviewer")
    assert _manual(client, "confirmed", attachment=("reply.txt", b"not a pdf", "text/plain")).status_code == 422
    res = _manual(client, "confirmed", attachment=("reply.png", _png(), "image/png"))
    assert res.status_code == 200
    check = fake.rows("verification_checks")[-1]
    path = check["response"]["attachment"]["path"]
    assert path.startswith("verification/app-a/cert-a/") and path in fake.storage.files
    shown = client.get(f"{API}/documents/cert-a/verification").json()["checks"][0]
    assert shown["response"]["attachment"] == {"name": "reply.png", "mime": "image/png", "size": len(_png())}
    assert client.get(f"{API}/verification-checks/{check['id']}/attachment").json()["url"].startswith("https://storage.test/sign/")
    assert any(e["p_type"] == "manual_check_recorded" and e["p_detail"]["attachment"] == "reply.png" for e in fake.audit)
    as_user("institution_a")
    assert client.get(f"{API}/documents/cert-a/verification").status_code == 403
    assert _manual(client, "confirmed").status_code == 403


def test_case_file_lists_every_check_with_its_answer(fake, client, as_user):
    _submitted(fake)
    as_user("reviewer")
    _manual(client, "pending")
    _mode(fake, "mismatch")
    client.post(f"{API}/documents/cert-a/verify/registry")
    doc = next(d for d in client.get(f"{API}/applications/app-a/casefile").json()["documents"] if d["id"] == "cert-a")
    assert [(v["method"], v["status"]) for v in doc["verification"]] == [("MANUAL", "manual_pending"), ("REGISTRY", "mismatch")]
    assert doc["verification"][1]["detail"] == "Differs: expiry date" and doc["verification"][1]["is_mock"]


# Setting ----------------------------------------------------------------------------------------

def test_only_a_rule_admin_changes_the_registry_mode(fake, client, as_user):
    as_user("reviewer")
    assert client.get(f"{API}/admin/settings/registry").json()["mode"] == "unavailable"
    assert client.put(f"{API}/admin/settings/registry", json={"mode": "match", "reason": "demo"}).status_code == 403
    as_user("rule_admin")
    assert client.put(f"{API}/admin/settings/registry", json={"mode": "live", "reason": "demo"}).status_code == 422
    assert client.put(f"{API}/admin/settings/registry", json={"mode": "match", "reason": "Demo of a verified source"}).json()["mode"] == "match"
    event = [e for e in fake.audit if e["p_type"] == "setting_changed"][-1]
    assert event["p_detail"] == {"from": "unavailable", "to": "match", "reason": "Demo of a verified source"}


# Pre-flight -------------------------------------------------------------------------------------

def test_pre_flight_lists_fixes_and_stores_nothing(fake, client, as_user):
    fake.table("settings").insert([{"key": "as_of", "value": {"mode": "fixed", "date": "2026-11-01"}}]).execute()
    fake.table("rules").insert([{"rule_code": c, "version": 1, "status": "active", "effective_from": "2026-01-01",
                                 "effective_to": None, "params": {}} for c in ("R-DOC-REQ", "R-EXP-01", "R-REG-01")]).execute()
    fake.table("document_types").insert([{"code": "approval_certificate", "label": "Approval certificate", "has_expiry": True,
                                          "signature_required": True, "is_photo": False}]).execute()
    _certificate(fake)
    fake.table("extracted_fields").update({"field_value": "2026-03-31", "original_value": "31 March 2026"}).eq("id", "cert-a-expiry_date").execute()
    fake.table("verification_checks").insert([{"document_id": "cert-a", "method": "REGISTRY", "status": "mismatch", "is_mock": True,
                                               "checked_at": "2026-10-20", "response": {"compared": [{"field": "expiry_date", "same": False}]}}]).execute()
    before = {t: len(fake.rows(t)) for t in ("validation_runs", "findings", "finding_evidence")}
    audit_before = len(fake.audit)

    as_user("institution_a")
    res = client.post(f"{API}/applications/app-a/preflight")
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] is False
    assert [(i["finding_type"], i["fix"]["step"], i["fix"].get("doc_type")) for i in body["items"]] == [
        ("EXPIRED_DOCUMENT", "documents", "approval_certificate"),
        ("MISSING_DOCUMENT", "documents", "application_form"),
    ]
    assert all(i["finding_type"] != "REGISTRY_MISMATCH" for i in body["items"])
    assert {t: len(fake.rows(t)) for t in before} == before and len(fake.audit) == audit_before

    as_user("institution_b")
    assert client.post(f"{API}/applications/app-a/preflight").status_code == 404
    as_user("reviewer")
    assert client.post(f"{API}/applications/app-a/preflight").status_code == 403
    fake.table("applications").update({"workflow_status": "under_review"}).eq("id", "app-a").execute()
    as_user("institution_a")
    assert client.post(f"{API}/applications/app-a/preflight").status_code == 409
