from __future__ import annotations

from fastapi.testclient import TestClient

import routes.webhooks as webhooks
from main import create_app
from settings import settings


class _DummyConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        return None


def test_webhook_disabled_provider_ignored(monkeypatch):
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", "THUNES")
    monkeypatch.setattr(webhooks, "_log_both_tables", lambda *args, **kwargs: None)
    monkeypatch.setattr(webhooks, "get_conn", lambda: _DummyConn())
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/v1/webhooks/tmoney", json={"external_ref": "ext-1", "status": "SUCCESS"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ignored") is True
    assert body.get("reason") == "PROVIDER_DISABLED"
