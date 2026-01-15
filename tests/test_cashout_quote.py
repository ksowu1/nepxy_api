from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import _auth_headers, AuthedUser


def test_cashout_returns_quote_and_payout_includes_quote(
    client: TestClient, user1: AuthedUser, wallet1_xof: str
):
    payload = {
        "wallet_id": wallet1_xof,
        "amount_cents": 1250,
        "country": "BJ",
        "provider_ref": f"quote-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user1.token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data.get("transaction_id")
    assert data.get("external_ref")
    assert data.get("fee_cents") is not None
    assert data.get("fx_rate")
    assert data.get("receive_amount_minor") is not None
    assert data.get("corridor") == "US->BJ"

    tx_id = data["transaction_id"]
    payout = client.get(
        f"/v1/payouts/{tx_id}",
        headers=_auth_headers(user1.token),
    )
    assert payout.status_code == 200, payout.text
    payout_json = payout.json()
    quote = payout_json.get("quote")
    assert isinstance(quote, dict)
    assert quote.get("send_amount_cents") == payload["amount_cents"]
    assert quote.get("fee_cents") == data.get("fee_cents")
    assert quote.get("fx_rate")
    assert quote.get("receive_amount_minor") is not None
    assert quote.get("corridor") == "US->BJ"
    assert quote.get("provider") == "DIRECT"
