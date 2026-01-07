



def test_refresh_token_invalid_401(client, monkeypatch):
    import routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "validate_refresh_token", lambda token: None)

    res = client.post("/v1/auth/refresh", json={"refresh_token": "bad-refresh"})
    assert res.status_code == 401
    assert res.json()["detail"] == "INVALID_REFRESH_TOKEN"
