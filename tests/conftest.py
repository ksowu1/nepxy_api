

# tests/conftest.py
import os
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Union

import pytest
from fastapi.testclient import TestClient

from main import app


@dataclass
class AuthedUser:
    email: str
    password: str
    token: str
    user_id: str


@pytest.fixture(scope="session")
def client() -> TestClient:
    # In-process integration tests against FastAPI app (still uses your real DB).
    return TestClient(app)


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


def _auth_headers(token: str, idem: Optional[str] = None) -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _normalize_wallet_list(payload: Any) -> List[dict]:
    # Support either {"wallets":[...]} or [...] responses.
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
    """
    Cash-in to fund tests. Adjust payload keys if your API differs.
    """
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


@pytest.fixture(scope="session")
def user1(client: TestClient) -> AuthedUser:
    # receiver
    return _login(
        client,
        os.getenv("TEST_USER1_EMAIL", "test@nexapay.io"),
        os.getenv("TEST_USER1_PASSWORD", "password123"),
    )


@pytest.fixture(scope="session")
def user2(client: TestClient) -> AuthedUser:
    # sender
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
    """
    Ensure sender has funds so P2P tests are deterministic.
    Adjust MIN_BALANCE_CENTS as needed.
    """
    min_balance = int(os.getenv("TEST_MIN_SENDER_BALANCE_CENTS", "5000"))
    bal = _get_balance(client, user2.token, wallet2_xof)
    if bal < min_balance:
        _cash_in_momo(client, user2.token, wallet2_xof, min_balance - bal)
    return wallet2_xof
