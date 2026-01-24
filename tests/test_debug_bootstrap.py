from __future__ import annotations

from fastapi.testclient import TestClient

from db import get_conn
from main import create_app
from tests.conftest import _register_best_effort


def _bootstrap_headers(secret: str) -> dict[str, str]:
    return {"X-Bootstrap-Secret": secret}


def test_debug_bootstrap_admin_grants_role(client, monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin@nexapay.io"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("MM_MODE", "sandbox")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("ADMIN_EMAIL", email)
    _register_best_effort(client, email, "password123")

    r = client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "ADMIN"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM users.user_roles WHERE user_id = %s::uuid;",
                (r.json()["user_id"],),
            )
            row = cur.fetchone()
    assert row and row[0] == "ADMIN"


def test_debug_bootstrap_admin_rejects_bad_secret(client, monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-bad@nexapay.io"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("MM_MODE", "sandbox")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("ADMIN_EMAIL", email)
    _register_best_effort(client, email, "password123")

    r = client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers("wrong"),
        json={"email": email},
    )
    assert r.status_code == 403, r.text


def test_debug_bootstrap_admin_not_allowed_in_production(client, monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-prod@nexapay.io"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("MM_MODE", "real")
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("ADMIN_EMAIL", email)
    _register_best_effort(client, email, "password123")

    r = client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email},
    )
    assert r.status_code == 404, r.text


def test_debug_bootstrap_admin_can_reset_password(monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-reset@nexapay.io"
    old_password = "old-password"
    new_password = "NewAdminPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", email)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    _register_best_effort(local_client, email, old_password)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": new_password},
    )
    assert r.status_code == 200, r.text

    login = local_client.post(
        "/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert login.status_code == 200, login.text


def test_debug_bootstrap_admin_creates_user_and_sets_password(monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-create@nexapay.io"
    password = "CreateAdminPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", password)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text

    login = local_client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text


def test_debug_bootstrap_admin_strips_password_whitespace(monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-trim@nexapay.io"
    password_raw = "TrimPass1! "
    password_trimmed = "TrimPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password_raw},
    )
    assert r.status_code == 200, r.text

    login = local_client.post(
        "/v1/auth/login",
        json={"email": email, "password": password_trimmed},
    )
    assert login.status_code == 200, login.text


def test_debug_bootstrap_admin_verify_failure(monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-admin-bad-hash@nexapay.io"
    password = "BadHashPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)

    import routes.debug as debug_routes

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    _register_best_effort(local_client, email, "old-password")

    monkeypatch.setattr(debug_routes, "hash_password", lambda _: "bad-hash")
    monkeypatch.setattr(debug_routes, "verify_password", lambda *_: False)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert r.status_code == 500, r.text
    body = r.json()
    assert body.get("detail", {}).get("detail") == "BOOTSTRAP_PASSWORD_VERIFY_FAILED"
    assert body.get("detail", {}).get("email") == email


def test_hash_password_verify_round_trip():
    from security import hash_password, verify_password

    password = "RoundTripPass1!"
    pw_hash = hash_password(password)
    assert verify_password(password, pw_hash) is True


def test_debug_bootstrap_verify_after_bootstrap_admin(monkeypatch):
    secret = "bootstrap-secret"
    email = "bootstrap-verify@nexapay.io"
    password = "VerifyPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", password)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text

    verify = local_client.post(
        "/debug/bootstrap-verify",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert verify.status_code == 200, verify.text
    body = verify.json()
    assert body["db_ok"] is True
    assert body["self_ok"] is True
    assert body["user_id"]
    assert body["prefix"]

    login = local_client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text


def test_debug_auth_probe_after_bootstrap_admin(monkeypatch):
    secret = "bootstrap-secret"
    email = "auth-probe@nexapay.io"
    password = "AuthProbePass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", email)
    monkeypatch.setenv("ADMIN_PASSWORD", password)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    r = local_client.post(
        "/debug/bootstrap-admin",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text

    probe = local_client.post(
        "/debug/auth-probe",
        headers=_bootstrap_headers(secret),
        json={"email": email, "password": password},
    )
    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert body["ok"] is True
    assert body["db_ok"] is True
    assert body["self_ok"] is True
    assert body["hash_len"] > 0
    assert body["hash_prefix"]
    assert body["pw_len"] == len(password)
    assert body["pw_strip_changed"] is False
    assert body["pw_sha12"]
    assert body["pw_has_crlf"] is False

    login = local_client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text


def test_debug_bootstrap_staging_users_updates_passwords(client, monkeypatch):
    secret = "bootstrap-secret"
    admin_email = "staging-admin@nexapay.io"
    user_email = "staging-user@nexapay.io"
    admin_password = "NewAdminPass1!"
    user_password = "NewUserPass1!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    monkeypatch.setenv("ADMIN_PASSWORD", admin_password)
    monkeypatch.setenv("USER_EMAIL", user_email)
    monkeypatch.setenv("USER_PASSWORD", user_password)

    local_client = TestClient(create_app(), raise_server_exceptions=False)

    _register_best_effort(local_client, admin_email, "old-password")
    _register_best_effort(local_client, user_email, "old-password")

    r = local_client.post(
        "/debug/bootstrap-staging-users",
        headers={"X-Bootstrap-Admin-Secret": secret},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["admin"]["email"] == admin_email
    assert body["user"]["email"] == user_email

    admin_login = local_client.post(
        "/v1/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    assert admin_login.status_code == 200, admin_login.text

    user_login = local_client.post(
        "/v1/auth/login",
        json={"email": user_email, "password": user_password},
    )
    assert user_login.status_code == 200, user_login.text

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM users.user_roles WHERE user_id = %s::uuid;",
                (body["admin"]["user_id"],),
            )
            row = cur.fetchone()
    assert row and row[0] == "ADMIN"


def test_debug_bootstrap_staging_users_not_allowed_in_prod(client, monkeypatch):
    secret = "bootstrap-secret"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_SECRET", secret)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("STAGING_GATE_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", "admin-prod@nexapay.io")
    monkeypatch.setenv("ADMIN_PASSWORD", "AdminPass1!")
    monkeypatch.setenv("USER_EMAIL", "user-prod@nexapay.io")
    monkeypatch.setenv("USER_PASSWORD", "UserPass1!")

    local_client = TestClient(create_app(), raise_server_exceptions=False)
    r = local_client.post(
        "/debug/bootstrap-staging-users",
        headers={"X-Bootstrap-Admin-Secret": secret},
    )
    assert r.status_code == 404, r.text
