

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_google_token_invalid_401(monkeypatch):
    """
    POST /v1/auth/google with an invalid token should return 401.
    We monkeypatch Google verifier so we don't depend on network/Google.
    """
    # Patch verify_oauth2_token to raise like Google would on bad token
    from routes import auth_google

    def _raise(*args, **kwargs):
        raise Exception("bad token")

    monkeypatch.setattr(auth_google.google_id_token, "verify_oauth2_token", _raise)

    res = client.post("/v1/auth/google", json={"id_token": "not-a-real-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid Google ID token"

def test_google_token_invalid_returns_401(client, monkeypatch):
    from routes import auth_google

    def boom(*args, **kwargs):
        raise Exception("bad token")

    monkeypatch.setattr(auth_google.google_id_token, "verify_oauth2_token", boom)

    r = client.post("/v1/auth/google", json={"id_token": "bad"})
    assert r.status_code == 401
