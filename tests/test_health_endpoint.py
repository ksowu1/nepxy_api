from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_health_staging_requires_gate_header(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "test-gate")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/health")
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "STAGING_GATE_KEY_REQUIRED"


def test_health_staging_allows_gate_header(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "test-gate")
    monkeypatch.setenv("MM_MODE", "sandbox")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/health", headers={"X-Staging-Key": "test-gate"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("mm_mode") == "sandbox"
