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
