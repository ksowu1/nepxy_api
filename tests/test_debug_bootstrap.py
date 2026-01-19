from __future__ import annotations

from db import get_conn
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
