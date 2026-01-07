def test_google_token_invalid_401(client, monkeypatch):
    # Import the module where verify_oauth2_token is used
    import routes.auth_google as auth_google

    def _raise(*args, **kwargs):
        raise Exception("bad token")

    monkeypatch.setattr(auth_google.google_id_token, "verify_oauth2_token", _raise)

    res = client.post("/v1/auth/google", json={"id_token": "not-a-real-token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid Google ID token"
