from __future__ import annotations

from fastapi.testclient import TestClient

import rate_limit
from main import create_app


def test_rate_limit_login_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MIN", "1")
    rate_limit._limiter = rate_limit.InMemoryRateLimiter()

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    payload = {"email": "nobody@example.com", "password": "bad"}
    r1 = client.post("/v1/auth/login", json=payload)
    assert r1.status_code in (401, 403), r1.text

    r2 = client.post("/v1/auth/login", json=payload)
    assert r2.status_code == 429, r2.text
    assert r2.json().get("detail") == "RATE_LIMITED"
