import uuid

from db import get_conn
from settings import settings
from tests.conftest import _auth_headers


def test_cash_out_auto_selects_provider_from_destination_country(client, user2, funded_wallet2_xof, monkeypatch):
    monkeypatch.setattr(settings, "MM_ENABLED_PROVIDERS", "MOMO,THUNES")
    idem = f"pytest-auto-provider-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "destination_country": "GH",
        "provider_ref": f"auto-ref-{uuid.uuid4()}",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 200, r.text
    txn_id = r.json()["transaction_id"]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provider FROM app.mobile_money_payouts WHERE transaction_id=%s::uuid",
                (txn_id,),
            )
            row = cur.fetchone()
    assert row, "Expected payout row"
    assert row[0] == "MOMO"


def test_cash_out_rejects_unsupported_delivery_method(client, user2, funded_wallet2_xof):
    idem = f"pytest-bad-method-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 100,
        "destination_country": "GH",
        "delivery_method": "NEPXY_WALLET",
        "provider_ref": f"bad-method-ref-{uuid.uuid4()}",
        "provider": "MOMO",
        "phone_e164": "+233201234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=idem),
    )
    assert r.status_code == 400, r.text
    assert r.json().get("detail") == "DELIVERY_METHOD_UNSUPPORTED"
