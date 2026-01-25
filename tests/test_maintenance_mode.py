from __future__ import annotations

from fastapi.testclient import TestClient

import routes.webhooks as webhooks
from main import create_app


def test_maintenance_blocks_login(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "1")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "bad-pass"},
    )
    assert r.status_code == 503
    assert r.json().get("detail") == "MAINTENANCE_MODE"


def test_maintenance_allows_health(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "1")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/health")
    assert r.status_code == 200


def test_maintenance_allows_webhooks(monkeypatch):
    async def fake_handle(_req, *, provider: str):
        return {"ok": True, "provider": provider}

    monkeypatch.setenv("MAINTENANCE_MODE", "1")
    monkeypatch.setattr(webhooks, "_handle_mobile_money_webhook", fake_handle)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/v1/webhooks/tmoney", json={"status": "SUCCESS"})
    assert r.status_code != 503
