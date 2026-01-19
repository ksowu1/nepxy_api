import uuid


def _unique_phone() -> str:
    n = uuid.uuid4().int % 10_000_000
    return f"+1555{n:07d}"


def _register_payload(email: str, password: str) -> dict:
    return {
        "email": email,
        "password": password,
        "phone_e164": _unique_phone(),
        "full_name": "Invite Only Test",
        "country": "TG",
    }


def test_register_blocked_when_invite_only(client, monkeypatch):
    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_ALLOWLIST", "allowed@example.com")

    email = f"blocked-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/v1/auth/register", json=_register_payload(email, "password123"))
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "INVITE_ONLY_EMAIL_NOT_ALLOWED"


def test_register_allowed_when_allowlisted(client, monkeypatch):
    email = f"allowed-{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_ALLOWLIST", email)

    r = client.post("/v1/auth/register", json=_register_payload(email, "password123"))
    assert r.status_code in (200, 201), r.text


def test_login_blocked_when_invite_only(client, monkeypatch):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"

    monkeypatch.setenv("INVITE_ONLY", "false")
    r = client.post("/v1/auth/register", json=_register_payload(email, password))
    assert r.status_code in (200, 201), r.text

    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_ALLOWLIST", "someoneelse@example.com")
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "INVITE_ONLY_EMAIL_NOT_ALLOWED"


def test_google_login_blocked_when_invite_only(client, monkeypatch):
    import routes.auth_google as auth_google

    def _fake_verify(token, req, aud):
        return {"email": "google-blocked@example.com", "email_verified": True, "name": "Test User"}

    monkeypatch.setenv("INVITE_ONLY", "true")
    monkeypatch.setenv("INVITE_ALLOWLIST", "allowlisted@example.com")
    monkeypatch.setattr(auth_google.google_id_token, "verify_oauth2_token", _fake_verify)

    r = client.post("/v1/auth/google", json={"id_token": "fake-token"})
    assert r.status_code == 403, r.text
    assert r.json().get("detail") == "INVITE_ONLY_EMAIL_NOT_ALLOWED"
