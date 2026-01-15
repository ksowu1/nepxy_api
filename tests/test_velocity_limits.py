import uuid
from datetime import datetime, timedelta, timezone

from settings import settings
import services.velocity as velocity

from tests.conftest import _auth_headers


def _register_and_login(client) -> tuple[str, str]:
    email = f"pytest-vel-{uuid.uuid4().hex[:8]}@nexapay.io"
    password = "password123"
    phone = f"+2289{str(uuid.uuid4().int)[:7]}"

    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "phone_e164": phone,
            "country": "TG",
            "full_name": "Velocity Tester",
        },
    )
    assert r.status_code in (200, 201, 409), r.text

    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = client.get("/v1/wallets", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    wallets = r.json().get("wallets") or r.json()
    wallet_id = wallets[0]["wallet_id"] if isinstance(wallets, list) else wallets["wallet_id"]
    return token, wallet_id


def _cash_in(client, token: str, wallet_id: str, amount_cents: int) -> None:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": f"vel-cashin-{uuid.uuid4()}",
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
        "provider_ref": f"vel-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": phone,
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text


def test_cash_out_count_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 2)
    monkeypatch.setattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0)
    monkeypatch.setattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0)

    token, wallet_id = _register_and_login(client)
    _cash_in(client, token, wallet_id, 1000)

    _cash_out(client, token, wallet_id, "+22890000001")
    _cash_out(client, token, wallet_id, "+22890000002")

    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"vel-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000003",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 429, r.text
    assert r.json().get("detail") == "VELOCITY_LIMIT_EXCEEDED"


def test_distinct_receivers_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 0)
    monkeypatch.setattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0)
    monkeypatch.setattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 1)

    token, wallet_id = _register_and_login(client)
    _cash_in(client, token, wallet_id, 1000)

    _cash_out(client, token, wallet_id, "+22890000011")

    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"vel-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000022",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 429, r.text
    assert r.json().get("detail") == "VELOCITY_LIMIT_EXCEEDED"


def test_limits_reset_after_window_moves(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 1)
    monkeypatch.setattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0)
    monkeypatch.setattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0)

    token, wallet_id = _register_and_login(client)
    _cash_in(client, token, wallet_id, 1000)

    _cash_out(client, token, wallet_id, "+22890000033")

    future = datetime.now(timezone.utc) + timedelta(days=2)
    monkeypatch.setattr(velocity, "_now", lambda: future)

    payload = {
        "wallet_id": wallet_id,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"vel-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000044",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text
