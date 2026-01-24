from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def _has_path(app, path: str) -> bool:
    return any(getattr(route, "path", "") == path for route in app.router.routes)


def test_debug_router_mounted_in_staging(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "test-gate-key")
    app = create_app()
    assert _has_path(app, "/debug/bootstrap-staging-users")


def test_debug_router_not_mounted_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    assert not _has_path(app, "/debug/bootstrap-staging-users")
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert not any(path.startswith("/debug/") for path in paths)

    r = client.get("/debug/me")
    assert r.status_code == 404, r.text


def test_debug_openapi_includes_bootstrap_staging_users(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "test-gate-key")
    app = create_app()
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/debug/bootstrap-staging-users" in paths


def test_debug_version_available_in_staging(monkeypatch):
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("GIT_SHA", "test-sha")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/debug/version")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["git_sha"] == "test-sha"
    assert body["env"] == "staging"


def test_debug_version_not_available_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/debug/version")
    assert r.status_code == 404, r.text
