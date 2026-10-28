from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/api/v1/health").json()["status"] == "healthy"


def test_case_routes_need_a_token():
    assert client.get("/api/v1/cases").status_code in (401, 403)
    assert client.get("/api/v1/patterns").status_code in (401, 403)
