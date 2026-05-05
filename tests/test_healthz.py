from fastapi.testclient import TestClient

from app.main import app


def test_healthz_exposes_loaded_registry():
    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("model_type") in ("popularity", "two_tower")
    assert "version" in payload
def test_root_redirects_to_login_when_guest():
    with TestClient(app) as client:
        r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers.get("location") == "/login"
