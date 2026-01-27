from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from settings import settings
from tests.conftest import _auth_headers


def _cash_in(client, token: str, wallet_id: str, amount_cents: int) -> None:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": f"lim-cashin-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text


def _cash_out(client, token: str, wallet_id: str, phone: str) -> None:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"lim-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": phone,
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text


def _register_and_login(client: TestClient) -> tuple[str, str, str]:
    email = f"pytest-admin-limits-{uuid.uuid4().hex[:8]}@nexapay.io"
    password = "password123"
    phone = f"+2288{str(uuid.uuid4().int)[:7]}"

    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "phone_e164": phone,
            "country": "TG",
            "full_name": "Limits Tester",
        },
    )
    assert r.status_code in (200, 201, 409), r.text

    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    user_id = r.json()["user_id"]

    r = client.get("/v1/wallets", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    wallets = r.json().get("wallets") or r.json()
    wallet_id = wallets[0]["wallet_id"] if isinstance(wallets, list) else wallets["wallet_id"]
    return token, wallet_id, user_id


def test_admin_can_override_user_limits(admin, client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 0)
    monkeypatch.setattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0)
    monkeypatch.setattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0)

    user_token, wallet_id, user_id = _register_and_login(client)

    r = client.put(
        f"/v1/admin/limits/users/{user_id}",
        json={"max_cashout_count_per_day": 1},
        headers=_auth_headers(admin.token),
    )
    assert r.status_code == 200, r.text

    _cash_in(client, user_token, wallet_id, 1000)
    _cash_out(client, user_token, wallet_id, "+22881112233")

    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"lim-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22881112244",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user_token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 429, r.text
    assert r.json().get("detail") == "VELOCITY_LIMIT_EXCEEDED"
