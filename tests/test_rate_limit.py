from __future__ import annotations

import pytest
from fastapi import HTTPException

import rate_limit


def _maybe_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    if rate_limit.rate_limit_enabled():
        rate_limit.rate_limit_or_429(key=key, limit=limit, window_seconds=window_seconds)


def test_rate_limit_disabled_no_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    rate_limit._limiter = rate_limit.InMemoryRateLimiter()

    _maybe_rate_limit("test:key", limit=1, window_seconds=60)
    _maybe_rate_limit("test:key", limit=1, window_seconds=60)


def test_rate_limit_enabled_exceeding_limit_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "1")
    rate_limit._limiter = rate_limit.InMemoryRateLimiter()

    _maybe_rate_limit("test:key", limit=2, window_seconds=60)
    _maybe_rate_limit("test:key", limit=2, window_seconds=60)

    with pytest.raises(HTTPException) as exc:
        _maybe_rate_limit("test:key", limit=2, window_seconds=60)

    err = exc.value
    assert err.status_code == 429
    assert err.detail == "RATE_LIMITED"
    assert err.headers and "Retry-After" in err.headers


def test_rate_limit_middleware_returns_request_id(monkeypatch):
    from fastapi.testclient import TestClient

    from main import create_app

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MIN", "1")
    rate_limit._limiter = rate_limit.InMemoryRateLimiter()

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    client.post("/v1/auth/refresh")
    r = client.post("/v1/auth/refresh")
    assert r.status_code == 429, r.text
    assert r.headers.get("X-Request-ID")
