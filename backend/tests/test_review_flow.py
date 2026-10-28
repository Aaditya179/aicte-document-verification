"""A full run against the in-memory database: findings written once, reviewer actions kept across re-runs,
auto-closing, actions with reasons in the audit trail, and what an institution may see."""
import re
from pathlib import Path

from services.validation import run_validation

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[2]


def _setup(fake):
    """Aarohan's application submitted with a form saying 24 faculty and a faculty list totalling 22."""
    fake.table("document_types").insert([
        {"code": "faculty_list", "label": "Faculty list", "has_expiry": False, "signature_required": False, "is_photo": False},
    ]).execute()
    fake.table("categories").insert([{"code": "extension_of_approval", "label": "Extension of approval"}]).execute()
    fake.table("required_documents").insert([{"category": "extension_of_approval", "doc_type": "faculty_list", "mandatory": True}]).execute()
    fake.table("comparison_pairs").insert([{
        "pair_code": "FACULTY_COUNT", "rule_code": "R-PAIR-01", "finding_type": "COUNT_CONFLICT", "label": "Faculty count",
        "doc_type_a": "application_form", "field_a": "declared_faculty_count", "doc_type_b": "faculty_list", "field_b": "faculty_total"}]).execute()
    fake.table("rules").insert([{"rule_code": c, "version": 1, "status": "active", "effective_from": "2026-01-01", "effective_to": None}
                                for c in ("R-DOC-REQ", "R-PAIR-01", "R-OCR-01", "R-DUP-01")]).execute()
    fake.table("documents").insert([
        {"id": "form-a", "application_id": "app-a", "doc_type": "application_form", "version": 1, "status": "current",
         "integrity_status": "passed", "sha256": "1" * 64, "uploaded_at": "2026-10-01"},
        {"id": "fac-a", "application_id": "app-a", "doc_type": "faculty_list", "version": 1, "status": "current",
         "integrity_status": "passed", "sha256": "2" * 64, "uploaded_at": "2026-10-01"},
    ]).execute()
    fake.table("extracted_fields").insert([
        {"document_id": "form-a", "field_name": "declared_faculty_count", "field_value": "24", "original_value": "24",
         "value_type": "int", "page_number": 1, "review_state": "auto"},
        {"document_id": "fac-a", "field_name": "faculty_total", "field_value": "22", "original_value": "22",
         "value_type": "int", "page_number": 2, "review_state": "auto"},
    ]).execute()
    fake.table("applications").update({"workflow_status": "submitted", "review_deadline": "2026-12-31"}).eq("id", "app-a").execute()


def test_run_writes_findings_once_and_keeps_reviewer_actions(fake, client, as_user):
    _setup(fake)
    as_user("reviewer")
    first = client.post(f"{API}/applications/app-a/validate").json()
    assert first["summary"]["created"] == 1
    statuses = {s["key"]: s["value"] for s in first["statuses"]["statuses"]}
    assert statuses["consistency"] == "Conflict detected"
    assert fake.rows("applications")[0]["workflow_status"] == "under_review"

    finding = client.get(f"{API}/applications/app-a/findings").json()[0]
    assert finding["finding_key"] == "COUNT_CONFLICT|INST-1001-2027-28-01|FACULTY_COUNT"
    assert [(e["role"], e["shown_value"], e["page_number"]) for e in finding["evidence"]] == [("A", "24", 1), ("B", "22", 2)]

    res = client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "dismiss", "reason": "Two posts are vacant and advertised"})
    assert res.status_code == 200 and res.json()["status"] == "dismissed"

    again = client.post(f"{API}/applications/app-a/validate").json()
    assert again["summary"] == {"findings": 1, "created": 0, "reopened": 0, "still_open": 0, "auto_closed": 0}
    assert len(fake.rows("findings")) == 1 and fake.rows("findings")[0]["status"] == "dismissed"
    assert len(fake.rows("validation_runs")) == 2


def test_fixed_condition_auto_closes_and_returns_if_it_comes_back(fake, as_user):
    _setup(fake)
    run_validation("app-a", "full")
    fake.table("extracted_fields").update({"field_value": "24", "original_value": "24"}).eq("document_id", "fac-a").execute()
    assert run_validation("app-a", "full")["summary"]["auto_closed"] == 1
    assert fake.rows("findings")[0]["status"] == "auto_closed"
    fake.table("extracted_fields").update({"field_value": "21"}).eq("document_id", "fac-a").execute()
    assert run_validation("app-a", "full")["summary"]["reopened"] == 1
    assert fake.rows("findings")[0]["status"] == "open"


def test_preflight_writes_nothing(fake):
    _setup(fake)
    result = run_validation("app-a", "preflight")
    assert [f["key"] for f in result["findings"]] == ["COUNT_CONFLICT|INST-1001-2027-28-01|FACULTY_COUNT"]
    assert fake.rows("findings") == [] and fake.rows("validation_runs") == []


def test_every_action_needs_a_reason_and_is_audited(fake, client, as_user):
    _setup(fake)
    as_user("reviewer")
    client.post(f"{API}/applications/app-a/validate")
    finding = fake.rows("findings")[0]
    assert client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "resolve", "reason": "  "}).status_code == 422
    res = client.post(f"{API}/findings/{finding['id']}/actions",
                      json={"action": "request_evidence", "reason": "Upload the faculty list signed by the principal"})
    assert res.json()["status"] == "evidence_requested"
    assert fake.rows("evidence_requests")[0]["message"] == "Upload the faculty list signed by the principal"
    assert fake.rows("applications")[0]["workflow_status"] == "awaiting_institution"
    assert any(n["user_id"] == "user-inst-a" for n in fake.rows("notifications"))
    res = client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "resolve", "reason": "Signed list received by post"})
    assert res.json()["status"] == "resolved"
    assert client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "dismiss", "reason": "again"}).status_code == 409
    events = [e["p_type"] for e in fake.audit]
    assert events.count("validation_run") == 1 and "finding_request_evidence" in events and "finding_resolve" in events
    reasons = [a["reason"] for a in fake.rows("review_actions")]
    assert reasons == ["Upload the faculty list signed by the principal", "Signed list received by post"]


def test_institution_sees_only_findings_it_is_asked_about(fake, client, as_user):
    _setup(fake)
    as_user("reviewer")
    client.post(f"{API}/applications/app-a/validate")
    finding = fake.rows("findings")[0]
    as_user("institution_a")
    assert client.get(f"{API}/applications/app-a/findings").json() == []
    assert client.get(f"{API}/findings/{finding['id']}").status_code == 404
    as_user("reviewer")
    client.post(f"{API}/findings/{finding['id']}/actions", json={"action": "request_evidence", "reason": "Send the signed list"})
    as_user("institution_a")
    seen = client.get(f"{API}/applications/app-a/findings").json()
    assert [f["id"] for f in seen] == [finding["id"]] and seen[0]["actions"] == []
    assert seen[0]["evidence_requests"][0]["message"] == "Send the signed list"
    as_user("institution_b")
    assert client.get(f"{API}/applications/app-a/findings").status_code == 404


def test_institution_cannot_run_validation_or_act(fake, client, as_user):
    _setup(fake)
    as_user("institution_a")
    assert client.post(f"{API}/applications/app-a/validate").status_code == 403
    assert client.get(f"{API}/applications/app-a/casefile").status_code == 403
    as_user("rule_admin")
    assert client.post(f"{API}/applications/app-a/validate").status_code == 403


def test_draft_application_is_not_validated(fake, client, as_user):
    as_user("reviewer")
    assert client.post(f"{API}/applications/app-b/validate").status_code == 409


def test_case_file_carries_decision_line_disclaimers_and_rule_versions(fake, client, as_user):
    _setup(fake)
    as_user("reviewer")
    client.post(f"{API}/applications/app-a/validate")
    cf = client.get(f"{API}/applications/app-a/casefile").json()
    assert cf["final_decision"] == "Final decision: Pending (authorised AICTE official)"
    assert len(cf["disclaimers"]) == 2 and "MOCK" in cf["disclaimers"][1]
    assert {r["rule_code"] for r in cf["rule_versions"]} >= {"R-PAIR-01"}
    assert client.post(f"{API}/applications/app-a/casefile/snapshot").status_code == 201
    assert fake.audit[-1]["p_type"] == "case_file_snapshot"


def test_institution_audit_view_leaves_out_validation_runs(fake, client, as_user):
    _setup(fake)
    fake.audit.clear()
    fake.table("audit_events").insert([
        {"id": 1, "event_type": "document_finalized", "application_id": "app-a", "actor_id": "user-inst-a"},
        {"id": 2, "event_type": "validation_run", "application_id": "app-a", "actor_id": "user-reviewer"},
    ]).execute()
    as_user("institution_a")
    assert [e["event_type"] for e in client.get(f"{API}/audit?application_id=app-a").json()] == ["document_finalized"]
    assert client.get(f"{API}/audit").status_code == 422


def test_no_code_can_set_the_administrative_decision():
    """admin_status is fixed to 'pending' by a check constraint, and no backend code writes it."""
    migration = (ROOT / "supabase/migrations/0001_proofpath_schema.sql").read_text()
    assert "check (admin_status = 'pending')" in migration
    writers = []
    for path in (ROOT / "backend").rglob("*.py"):
        if ".venv" in path.parts or "tests" in path.parts:
            continue
        if re.search(r"[\"']admin_status[\"']\s*:", path.read_text()):
            writers.append(str(path.relative_to(ROOT)))
    assert writers == []
