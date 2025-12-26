
# tests/conftest.py

import os
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Any, List

import pytest
from fastapi.testclient import TestClient

from main import app
from db import get_conn


SYSTEM_OWNER_ID = os.getenv("SYSTEM_OWNER_ID", "00000000-0000-0000-0000-000000000001")


@dataclass
class AuthedUser:
    email: str
    password: str
    token: str
    user_id: str


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


def _register_best_effort(client: TestClient, email: str, password: str) -> None:
    payload = {
        "email": email,
        "phone_e164": "+15550000000",
        "full_name": "Admin User",
        "country": "TG",
        "password": password,
    }
    r = client.post("/v1/auth/register", json=payload)

    # Accept: created/ok OR already exists
    if r.status_code in (200, 201, 409):
        return

    # Your DB sometimes returns 400 EMAIL_TAKEN when already exists
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text

    if r.status_code == 400 and "EMAIL_TAKEN" in str(detail):
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
        if w.get("currency") == "XOF":
            return w["wallet_id"]

    return wallets[0]["wallet_id"]


def _get_balance(client: TestClient, token: str, wallet_id: str) -> int:
    r = client.get(f"/v1/wallets/{wallet_id}/balance", headers=_auth_headers(token))
    assert r.status_code == 200, f"balance failed: {r.status_code} {r.text}"
    return int(r.json()["balance_cents"])


def _cash_in_momo(
    client: TestClient,
    token: str,
    wallet_id: str,
    amount_cents: int,
    country: str = "TG",
) -> None:
    provider_ref = f"pytest-cashin-{uuid.uuid4()}"
    payload = {
        "user_account_id": wallet_id,
        "amount_cents": amount_cents,
        "country": country,
        "provider_ref": provider_ref,
    }
    r = client.post(
        "/v1/cash-in/momo",
        json=payload,
        headers=_auth_headers(token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), f"cash-in failed: {r.status_code} {r.text}"


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
      - users.set_user_role_secure() requires require_admin(), which fails when no admin exists yet.
      - We keep tests deterministic and self-contained.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Ensure table exists (matches what you found: users.user_roles)
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
    email = os.getenv("TEST_ADMIN_EMAIL", "admin@nexapay.io")
    password = os.getenv("TEST_ADMIN_PASSWORD", "password123")

    _register_best_effort(client, email=email, password=password)

    admin = _login(client, email, password)

    # Promote directly via table users.user_roles
    _promote_user_to_admin_direct(admin.user_id)

    # Re-login so token/claims reflect admin (if your JWT encodes roles)
    admin = _login(client, email, password)
    return admin

