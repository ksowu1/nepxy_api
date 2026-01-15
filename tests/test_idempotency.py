import uuid
from concurrent.futures import ThreadPoolExecutor

from db import get_conn
from tests.conftest import _auth_headers, _get_balance


def _cash_in(client, token: str, wallet_id: str, amount_cents: int, idem: str) -> str:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "TG",
        "provider_ref": f"pytest-cashin-{idem}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=idem),
    )
    assert r.status_code == 200, r.text
    return r.json()["transaction_id"]


def _cash_out(client, token: str, wallet_id: str, amount_cents: int, idem: str) -> str:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "BJ",
        "provider_ref": f"cashout-{idem}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=idem),
    )
    assert r.status_code == 200, r.text
    return r.json()["transaction_id"]


def test_cash_out_idempotency_reuse_returns_same_txn(client, user2, funded_wallet2_xof):
    idem = f"idem-{uuid.uuid4()}"
    tx1 = _cash_out(client, user2.token, funded_wallet2_xof, 100, idem)
    tx2 = _cash_out(client, user2.token, funded_wallet2_xof, 100, idem)
    assert tx1 == tx2

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM app.mobile_money_payouts WHERE transaction_id = %s::uuid",
            (tx1,),
        )
        assert cur.fetchone()[0] == 1


def test_cash_in_idempotency_does_not_double_credit(client, user2, wallet2_xof):
    before = _get_balance(client, user2.token, wallet2_xof)
    idem = f"idem-{uuid.uuid4()}"
    _cash_in(client, user2.token, wallet2_xof, 200, idem)
    _cash_in(client, user2.token, wallet2_xof, 200, idem)
    after = _get_balance(client, user2.token, wallet2_xof)
    assert after - before == 200


def test_concurrent_cash_out_same_key_single_txn(client, user2, funded_wallet2_xof):
    idem = f"idem-{uuid.uuid4()}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: _cash_out(client, user2.token, funded_wallet2_xof, 100, idem),
                range(2),
            )
        )

    assert results[0] == results[1]

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ledger.ledger_transactions WHERE idempotency_key = %s",
            (idem,),
        )
        assert cur.fetchone()[0] == 1
