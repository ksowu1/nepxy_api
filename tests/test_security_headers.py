def test_security_headers_present(client):
    r = client.get("/healthz")
    assert r.status_code == 200, r.text
    headers = {k.lower(): v for k, v in r.headers.items()}

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "no-referrer"
    assert "content-security-policy" in headers


def test_cors_allows_localhost_in_dev(client):
    r = client.get("/healthz", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
