from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/api/v1/health").json()["status"] == "healthy"
