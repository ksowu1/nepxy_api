

# tests/conftest.py

from __future__ import annotations

import os
import uuid
import random
from uuid import uuid4
from dataclasses import dataclass
from typing import Dict, Optional, Any, List

import pytest
from fastapi.testclient import TestClient

from main import app
from db import get_conn

# Optional: if you want to run the worker manually via python tests/conftest.py
from app.workers.payout_worker import run_forever


SYSTEM_OWNER_ID = os.getenv("SYSTEM_OWNER_ID", "00000000-0000-0000-0000-000000000001")

# Defaults (safe for local/dev tests)
os.environ.setdefault("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")
os.environ.setdefault("FLOOZ_WEBHOOK_SECRET", "dev_secret_flooz")
os.environ.setdefault("MOMO_WEBHOOK_SECRET", "dev_secret_momo")


@dataclass
class AuthedUser:
    email: str
    password: str
    token: str
    user_id: str


# ---------------------------
# Global defaults for tests
# ---------------------------

@pytest.fixture(autouse=True)
def _set_webhook_secrets(monkeypatch):
    """
    Make webhook secrets deterministic for the test suite.
    Individual tests can override with monkeypatch.setenv(...).
    """
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", os.getenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney"))
    monkeypatch.setenv("FLOOZ_WEBHOOK_SECRET", os.getenv("FLOOZ_WEBHOOK_SECRET", "dev_secret_flooz"))
    monkeypatch.setenv("MOMO_WEBHOOK_SECRET", os.getenv("MOMO_WEBHOOK_SECRET", "dev_secret_momo"))


# ---------------------------
# Client + Auth Helpers
# ---------------------------

@pytest.fixture(scope="session")
def client() -> TestClient:
    # Needed so tests can assert 500s instead of pytest re-raising server exceptions
    return TestClient(app, raise_server_exceptions=False)


def _auth_headers(token: str, idem: Optional[str] = None) -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _login(client: TestClient, email: str, password: str) -> AuthedUser:
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return AuthedUser(
        email=email,
        password=password,
        token=data["access_token"],
        user_id=data["user_id"],
    )


def _unique_test_phone() -> str:
    # +1555 is reserved for fictional numbers; keep it in a valid E.164 shape.
    n = uuid.uuid4().int % 10_000_000
    return f"+1555{n:07d}"


def _register_best_effort(client: TestClient, email: str, password: str) -> None:
    payload = {
        "email": email,
        "phone_e164": _unique_test_phone(),
        "full_name": "Admin User",
        "country": "TG",
        "password": password,
    }
    r = client.post("/v1/auth/register", json=payload)

    # Accept created/ok OR already exists
    if r.status_code in (200, 201, 409):
        return

    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text

    # Treat "already exists" as OK
    if r.status_code == 400 and ("EMAIL_TAKEN" in str(detail) or "PHONE_TAKEN" in str(detail)):
        return

    raise AssertionError(f"Register failed: {r.status_code} {r.text}")


# ---------------------------
# Wallet Helpers (used by existing tests)
# ---------------------------

def _normalize_wallet_list(payload: Any) -> List[dict]:
    if isinstance(payload, dict) and "wallets" in payload:
        return payload["wallets"] or []
    if isinstance(payload, list):
        return payload
    return []


def _get_xof_wallet_id(client: TestClient, token: str) -> str:
    r = client.get("/v1/wallets", headers=_auth_headers(token))
    assert r.status_code == 200, f"wallet list failed: {r.status_code} {r.text}"
    wallets = _normalize_wallet_list(r.json())
    assert wallets, "No wallets returned"

    for w in wallets:
        # some APIs use `wallet_id`, others use `id`
        if w.get("currency") == "XOF":
            return w.get("wallet_id") or w.get("id")

    first = wallets[0]
    return first.get("wallet_id") or first.get("id")


def _get_balance(client: TestClient, token: str, wallet_id: str) -> int:
    r = client.get(f"/v1/wallets/{wallet_id}/balance", headers=_auth_headers(token))
    assert r.status_code == 200, f"balance failed: {r.status_code} {r.text}"
    return int(r.json()["balance_cents"])


def _cash_in_mobile_money_best_effort(
    client: TestClient,
    token: str,
    wallet_id: str,
    amount_cents: int,
    country: str = "TG",
    provider: str = "MOMO",
) -> None:
    provider_ref = f"pytest-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": country,
        "provider_ref": provider_ref,
        "provider": provider,
    }
    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), f"cash-in failed: {r.status_code} {r.text}"


def _cash_in_momo(client: TestClient, token: str, wallet_id: str, amount_cents: int, country: str = "TG") -> None:
    return _cash_in_mobile_money_best_effort(
        client,
        token,
        wallet_id,
        amount_cents,
        country=country,
        provider="MOMO",
    )


# ---------------------------
# Base Test Users
# ---------------------------

@pytest.fixture(scope="session")
def user1(client: TestClient) -> AuthedUser:
    return _login(
        client,
        os.getenv("TEST_USER1_EMAIL", "test@nexapay.io"),
        os.getenv("TEST_USER1_PASSWORD", "password123"),
    )


@pytest.fixture(scope="session")
def user2(client: TestClient) -> AuthedUser:
    return _login(
        client,
        os.getenv("TEST_USER2_EMAIL", "other@nexapay.io"),
        os.getenv("TEST_USER2_PASSWORD", "password123"),
    )


@pytest.fixture()
def wallet1_xof(client: TestClient, user1: AuthedUser) -> str:
    return _get_xof_wallet_id(client, user1.token)


@pytest.fixture()
def wallet2_xof(client: TestClient, user2: AuthedUser) -> str:
    return _get_xof_wallet_id(client, user2.token)


@pytest.fixture()
def funded_wallet2_xof(client: TestClient, user2: AuthedUser, wallet2_xof: str) -> str:
    min_balance = int(os.getenv("TEST_MIN_SENDER_BALANCE_CENTS", "5000"))
    bal = _get_balance(client, user2.token, wallet2_xof)
    if bal < min_balance:
        _cash_in_momo(client, user2.token, wallet2_xof, min_balance - bal)
    return wallet2_xof


# ---------------------------
# Admin User Fixture (FIXED)
# ---------------------------

def _promote_user_to_admin_direct(user_id: str) -> None:
    """
    Test-only promotion: write ADMIN role directly to users.user_roles.

    Why:
      - users.set_user_role_secure() likely requires require_admin(), which fails when no admin exists yet.
      - We keep tests deterministic and self-contained.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Ensure table exists (matches what we expect: users.user_roles)
            cur.execute("SELECT to_regclass('users.user_roles') IS NOT NULL;")
            ok = cur.fetchone()[0]
            assert ok, "Missing table users.user_roles"

            cur.execute(
                """
                INSERT INTO users.user_roles (user_id, role)
                VALUES (%s::uuid, 'ADMIN')
                ON CONFLICT (user_id) DO UPDATE
                  SET role = EXCLUDED.role;
                """,
                (str(user_id),),
            )
        conn.commit()


@pytest.fixture(scope="session")
def admin_user(client: TestClient) -> AuthedUser:
    base_email = os.getenv("TEST_ADMIN_EMAIL", "admin@nexapay.io")
    password = os.getenv("TEST_ADMIN_PASSWORD", "password123")

    # Try the configured email first
    _register_best_effort(client, email=base_email, password=password)

    try:
        admin = _login(client, base_email, password)
    except AssertionError:
        # If the email exists with a different password, use a unique email for tests
        unique_email = f"admin+pytest-{uuid.uuid4().hex[:8]}@nexapay.io"
        _register_best_effort(client, email=unique_email, password=password)
        admin = _login(client, unique_email, password)

    # Promote to admin in DB
    _promote_user_to_admin_direct(admin.user_id)

    # Re-login so JWT/claims reflect admin role
    admin = _login(client, admin.email, password)
    return admin


@pytest.fixture
def admin(admin_user):
    """
    Backward-compatible alias.
    Some tests expect fixture name `admin`.
    """
    return admin_user


# ---------------------------
# Cleanup between tests
# ---------------------------

@pytest.fixture(autouse=True)
def _clean_payouts_table():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("ALTER TABLE app.mobile_money_payouts ADD COLUMN IF NOT EXISTS quote jsonb;")
        cur.execute("TRUNCATE app.mobile_money_payouts RESTART IDENTITY CASCADE;")
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def _ensure_webhook_events_table():
    from db import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS app.webhook_events (
              id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
              provider text NOT NULL,
              external_ref text,
              provider_ref text,
              status_raw text,
              payload jsonb NOT NULL,
              payload_json jsonb,
              payload_summary jsonb,
              headers jsonb,
              received_at timestamptz NOT NULL DEFAULT now(),
              signature_valid boolean
            );
            """)
            cur.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS payload_json jsonb;")
            cur.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS payload_summary jsonb;")
            cur.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS signature_valid boolean;")
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def _ensure_idempotency_table():
    from db import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app.idempotency_keys (
                  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                  user_id uuid NOT NULL,
                  idempotency_key text NOT NULL,
                  route_key text NOT NULL,
                  request_hash text,
                  response_json jsonb NOT NULL,
                  status_code integer NOT NULL,
                  created_at timestamptz NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_idempotency_keys_user_route
                ON app.idempotency_keys (user_id, idempotency_key, route_key);
                """
            )
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def _ensure_audit_log_table():
    from db import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app.audit_log (
                  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                  actor_user_id uuid NOT NULL,
                  action text NOT NULL,
                  target_id text,
                  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                  created_at timestamptz NOT NULL DEFAULT now()
                );
                """
            )
        conn.commit()
    yield


@pytest.fixture(autouse=True)
def _ensure_country_gh_enum():
    from db import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'country_code'
                  AND e.enumlabel = 'GH';
                """
            )
            exists = cur.fetchone()
            if not exists:
                cur.execute("ALTER TYPE ledger.country_code ADD VALUE 'GH';")
        conn.commit()
    yield


# ---------------------------
# Optional manual runner
# ---------------------------

if __name__ == "__main__":
    run_forever(poll_seconds=5, batch_size=50, stale_seconds=60)
