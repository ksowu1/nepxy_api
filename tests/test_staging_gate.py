from tests.conftest import _auth_headers


def _enable_staging_gate(monkeypatch, *, with_key: bool = True) -> str:
    value = "secret-key"
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("ENV", "staging")
    if with_key:
        monkeypatch.setenv("STAGING_GATE_KEY", value)
    else:
        monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    return value


def test_staging_gate_requires_key_for_protected_path(client, monkeypatch):
    _ = _enable_staging_gate(monkeypatch)
    r = client.get("/v1/wallets")
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "STAGING_GATE_KEY_REQUIRED"


def test_staging_gate_allows_with_key(client, user1, monkeypatch):
    value = _enable_staging_gate(monkeypatch)
    headers = _auth_headers(user1.token)
    headers["X-Staging-Key"] = value
    r = client.get("/v1/wallets", headers=headers)
    assert r.status_code == 200, r.text


def test_staging_gate_skips_healthz(client, monkeypatch):
    _ = _enable_staging_gate(monkeypatch)
    r = client.get("/healthz")
    assert r.status_code == 200, r.text


def test_staging_gate_skips_readyz(client, monkeypatch):
    _ = _enable_staging_gate(monkeypatch)
    r = client.get("/readyz")
    assert r.status_code == 200, r.text


def test_staging_gate_skips_docs(client, monkeypatch):
    _ = _enable_staging_gate(monkeypatch)
    r = client.get("/docs")
    assert r.status_code == 200, r.text


def test_staging_gate_disabled_without_key(client, monkeypatch):
    _ = _enable_staging_gate(monkeypatch, with_key=False)
    r = client.get("/nonexistent-route")
    assert r.status_code == 404, r.text
