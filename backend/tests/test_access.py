"""
Who can see what (build spec 4 and 5.2). The service role bypasses row-level security, so these
API checks are the lock; institution A must never see institution B's application or documents.
"""
import pytest

API = "/api/v1"


def test_institution_lists_only_its_own_applications(fake, client, as_user):
    as_user("institution_a")
    codes = [a["code"] for a in client.get(f"{API}/applications").json()]
    assert codes == ["INST-1001-2027-28-01"]


def test_reviewer_and_rule_admin_list_every_application(fake, client, as_user):
    for role in ("reviewer", "rule_admin"):
        as_user(role)
        assert len(client.get(f"{API}/applications").json()) == 2


@pytest.mark.parametrize("path", [
    "/applications/app-b",
    "/documents/doc-b",
    "/documents/doc-b/signed-url",
])
def test_another_institutions_records_read_as_not_found(fake, client, as_user, path):
    as_user("institution_a")
    assert client.get(f"{API}{path}").status_code == 404


def test_institution_cannot_upload_to_another_institutions_application(fake, client, as_user):
    as_user("institution_a")
    res = client.post(f"{API}/applications/app-b/documents/init",
                      json={"doc_type": "application_form", "filename": "form.pdf", "mime": "application/pdf", "size": 1000})
    assert res.status_code == 404
    assert not [d for d in fake.rows("documents") if d["application_id"] == "app-b" and d["id"] != "doc-b"]


def test_institution_cannot_finalize_or_submit_another_institutions_records(fake, client, as_user):
    as_user("institution_a")
    assert client.post(f"{API}/documents/doc-b/finalize").status_code == 404
    assert client.post(f"{API}/applications/app-b/submit").status_code == 404


def test_reviewer_opens_any_document(fake, client, as_user):
    as_user("reviewer")
    assert client.get(f"{API}/applications/app-b").status_code == 200
    assert client.get(f"{API}/documents/doc-b").status_code == 200
    link = client.get(f"{API}/documents/doc-b/signed-url").json()
    assert link["url"].startswith("https://storage.test/sign/") and link["expires_in"] <= 600


def test_extracted_values_are_for_reviewers_not_institutions(fake, client, as_user):
    as_user("institution_b")
    assert client.get(f"{API}/documents/doc-b/fields").status_code == 403
    as_user("reviewer")
    assert client.get(f"{API}/documents/doc-b/fields").status_code == 200


@pytest.mark.parametrize("role", ["reviewer", "rule_admin"])
def test_only_institutions_create_applications_and_upload(fake, client, as_user, role):
    as_user(role)
    assert client.post(f"{API}/applications", json={"category": "new_institution", "academic_year": "2027-28"}).status_code == 403
    res = client.post(f"{API}/applications/app-a/documents/init",
                      json={"doc_type": "application_form", "filename": "form.pdf", "mime": "application/pdf", "size": 1000})
    assert res.status_code == 403


def test_rules_are_for_rule_admins(fake, client, as_user):
    for role, expected in (("institution_a", 403), ("reviewer", 403), ("rule_admin", 200)):
        as_user(role)
        assert client.get(f"{API}/rules").status_code == expected


def test_document_responses_never_include_the_storage_path(fake, client, as_user):
    as_user("reviewer")
    body = client.get(f"{API}/applications/app-b").json()
    assert all("storage_path" not in d for d in body["documents"])
    assert "storage_path" not in client.get(f"{API}/documents/doc-b").json()


def test_routes_need_a_token(client):
    for path in ("/applications", "/documents/doc-b", "/rules", "/audit/verify", "/reference"):
        assert client.get(f"{API}{path}").status_code in (401, 403)


def test_demo_accounts_are_public_and_all_proofpath_demo(client):
    accounts = client.get(f"{API}/demo/accounts").json()
    assert {a["role"] for a in accounts} == {"institution", "reviewer", "rule_admin"}
    assert all(a["email"].endswith("@proofpath.demo") for a in accounts)
