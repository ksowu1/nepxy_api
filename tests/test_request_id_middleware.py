from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_request_id_added_when_missing():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    req_id = resp.headers.get("X-Request-ID")
    assert req_id


def test_request_id_echoed_when_present():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health", headers={"X-Request-ID": "client-request-id"})
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("X-Request-ID") == "client-request-id"


def test_request_id_present_on_staging_gate_403(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "gate-secret")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post("/v1/auth/login", json={"email": "user@example.com", "password": "bad"})
    assert resp.status_code == 403, resp.text
    assert resp.headers.get("X-Request-ID")
