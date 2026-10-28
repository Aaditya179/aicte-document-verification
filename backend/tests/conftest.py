import pytest
from fastapi.testclient import TestClient

from core import ratelimit
from core.db import Database, db
from core.security import AuthenticatedUser, get_current_user
from main import app
from tests.fakedb import FakeDB

INST_A, INST_B = "inst-a", "inst-b"

USERS = {
    "institution_a": AuthenticatedUser(id="user-inst-a", email="a@proofpath.demo", role="institution", institution_id=INST_A),
    "institution_b": AuthenticatedUser(id="user-inst-b", email="b@proofpath.demo", role="institution", institution_id=INST_B),
    "reviewer": AuthenticatedUser(id="user-reviewer", email="r@proofpath.demo", role="reviewer", aal="aal2"),
    "rule_admin": AuthenticatedUser(id="user-admin", email="ra@proofpath.demo", role="rule_admin", aal="aal2"),
    "rule_admin_2": AuthenticatedUser(id="user-admin-2", email="ra2@proofpath.demo", role="rule_admin", aal="aal2"),
}


@pytest.fixture
def fake(monkeypatch):
    """The API wired to an in-memory database holding two institutions with one application each."""
    f = FakeDB()
    monkeypatch.setattr(db, "table", f.table)
    monkeypatch.setattr(db, "rpc", f.rpc)
    monkeypatch.setattr(Database, "storage", property(lambda self: f.storage))
    ratelimit.reset()

    f.table("institutions").insert([
        {"id": INST_A, "code": "INST-1001", "name": "Aarohan Institute of Technology", "city": "Pune", "is_fictional": True},
        {"id": INST_B, "code": "INST-1002", "name": "Vindhya College of Engineering", "city": "Nagpur", "is_fictional": True},
    ]).execute()
    f.table("members").insert([
        {"user_id": u.id, "role": u.role, "institution_id": u.institution_id, "full_name": key} for key, u in USERS.items()
    ]).execute()
    f.table("document_types").insert([
        {"code": "application_form", "label": "Application form", "has_expiry": False, "signature_required": False, "is_photo": False},
        {"code": "infrastructure_photo", "label": "Infrastructure photo", "has_expiry": False, "signature_required": False, "is_photo": True},
    ]).execute()
    f.table("required_documents").insert([
        {"category": "extension_of_approval", "doc_type": "application_form", "mandatory": True},
    ]).execute()
    f.table("applications").insert([
        {"id": "app-a", "code": "INST-1001-2027-28-01", "institution_id": INST_A, "category": "extension_of_approval",
         "academic_year": "2027-28", "workflow_status": "draft", "admin_status": "pending", "created_at": "2026-10-01"},
        {"id": "app-b", "code": "INST-1002-2027-28-01", "institution_id": INST_B, "category": "extension_of_approval",
         "academic_year": "2027-28", "workflow_status": "draft", "admin_status": "pending", "created_at": "2026-10-02"},
    ]).execute()
    f.table("documents").insert([
        {"id": "doc-b", "application_id": "app-b", "doc_type": "application_form", "version": 1, "status": "current",
         "storage_path": "inst-b/app-b/doc-b-form.pdf", "mime": "application/pdf", "integrity_status": "passed",
         "processing_status": "done", "uploaded_at": "2026-10-02"},
    ]).execute()
    yield f
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def as_user():
    def use(key: str):
        app.dependency_overrides[get_current_user] = lambda: USERS[key]
    return use
