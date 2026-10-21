from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_states_the_core_safety_principle():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ACTIVE" in resp.json()["principle"]
