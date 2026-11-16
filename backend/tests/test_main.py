from fastapi.testclient import TestClient

from app.main import app, PACKAGES

def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True

def test_all_routers_included():
    assert len(PACKAGES) == 13
