from fastapi.testclient import TestClient

from main import create_app


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert "db_ok" in data


def test_readyz(client):
    r = client.get("/readyz")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ready" in data
    assert "db_ok" in data
    assert "migrations_ok" in data


def test_version_endpoint(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "test-sha")
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("STAGING_GATE_KEY", "test-gate")
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/version", headers={"X-Staging-Key": "test-gate"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("git_sha") == "test-sha"
    assert data.get("env") == "staging"
