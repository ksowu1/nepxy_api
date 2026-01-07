

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_refresh_token_invalid_401(monkeypatch):
    """
    POST /v1/auth/refresh with an invalid refresh token should return 401.
    """
    from routes import auth as auth_routes

    # Patch validate_refresh_token to return None (invalid)
    monkeypatch.setattr(auth_routes, "validate_refresh_token", lambda token: None)

    res = client.post("/v1/auth/refresh", json={"refresh_token": "bad-refresh"})
    assert res.status_code == 401
    assert res.json()["detail"] == "INVALID_REFRESH_TOKEN"
