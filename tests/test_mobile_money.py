

# tests/test_mobile_money.py

import uuid

from tests.conftest import _auth_headers


def test_cash_in_tmoney_success(client, user2, wallet2_xof):
    idem = f"pytest-tmoney-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet2_xof,
        "amount_cents": 200,
        "country": "TG",
        "provider_ref": f"tmoney-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }

    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 200, r.text
    assert "transaction_id" in r.json()


def test_cash_in_flooz_success(client, user2, wallet2_xof):
    idem = f"pytest-flooz-cashin-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet2_xof,
        "amount_cents": 200,
        "country": "TG",
        "provider_ref": f"flooz-ref-{uuid.uuid4()}",
        "provider": "FLOOZ",
        "phone_e164": "+22891000000",
    }

    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 200, r.text
    assert "transaction_id" in r.json()


def test_cash_out_tmoney_success(client, user2, funded_wallet2_xof):
    idem_in = f"pytest-seed-{uuid.uuid4()}"
    payload_in = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 300,
        "country": "TG",
        "provider_ref": f"seed-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }
    r1 = client.post(
        "/v1/cash-in/mobile-money",
        json=payload_in,
        headers=_auth_headers(user2.token, idem=idem_in),
    )
    assert r1.status_code == 200, r1.text

    idem_out = f"pytest-tmoney-cashout-{uuid.uuid4()}"
    payload_out = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "country": "TG",
        "provider_ref": f"cashout-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }
    r2 = client.post(
        "/v1/cash-out/mobile-money",
        json=payload_out,
        headers=_auth_headers(user2.token, idem=idem_out),
    )
    assert r2.status_code == 200, r2.text
    assert "transaction_id" in r2.json()


def test_idempotency_reuse_returns_same_txn(client, user2, wallet2_xof):
    idem = f"pytest-idem-{uuid.uuid4()}"
    payload = {
        "wallet_id": wallet2_xof,
        "amount_cents": 111,
        "country": "TG",
        "provider_ref": f"idem-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }

    r1 = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r2.status_code == 200, r2.text

    assert r1.json()["transaction_id"] == r2.json()["transaction_id"]


def test_cash_in_rejects_user_account_id_field(client, user2, wallet2_xof):
    """
    This locks the contract: payload must use wallet_id only.
    """
    idem = f"pytest-reject-old-field-{uuid.uuid4()}"
    payload = {
        "user_account_id": wallet2_xof,  # intentionally wrong
        "amount_cents": 200,
        "country": "TG",
        "provider_ref": f"bad-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }

    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 422, r.text
