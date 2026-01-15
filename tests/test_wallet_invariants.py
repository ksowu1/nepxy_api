import uuid

from db import get_conn
from tests.conftest import _auth_headers


def _register_and_login(client) -> tuple[str, str]:
    email = f"pytest-inv-{uuid.uuid4().hex[:8]}@nexapay.io"
    password = "password123"
    phone = f"+2289{str(uuid.uuid4().int)[:7]}"

    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "phone_e164": phone,
            "country": "TG",
            "full_name": "Invariant Tester",
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
        "provider_ref": f"pytest-cashin-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-in/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text


def _cash_out(client, token: str, wallet_id: str, amount_cents: int) -> None:
    payload = {
        "wallet_id": wallet_id,
        "amount_cents": amount_cents,
        "country": "BJ",
        "provider": "TMONEY",
        "phone_e164": "+22890009911",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code == 200, r.text


def _ledger_sum(cur, wallet_id: str) -> int:
    cur.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN e.dc = 'CREDIT' THEN e.amount_cents
                WHEN e.dc = 'DEBIT' THEN -e.amount_cents
                ELSE 0
            END
        ), 0)
        FROM ledger.ledger_entries e
        JOIN ledger.ledger_transactions t ON t.id = e.transaction_id
        WHERE e.account_id = %s::uuid
          AND t.status IN ('POSTED','REVERSED');
        """,
        (wallet_id,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def test_wallet_invariant_passes_after_cash_in_out(client, admin_user):
    token, wallet_id = _register_and_login(client)
    _cash_in(client, token, wallet_id, 2000)
    _cash_out(client, token, wallet_id, 100)

    r = client.get(
        f"/debug/invariants/wallet/{wallet_id}",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    assert payload["wallet"]["wallet_id"] == wallet_id
    assert payload["wallet"]["diff_cents"] == 0


def test_wallet_invariant_detects_tamper(client, admin_user, user2, wallet2_xof):
    _cash_in(client, user2.token, wallet2_xof, 1500)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT available_cents FROM ledger.wallet_balances WHERE account_id = %s::uuid;",
                (wallet2_xof,),
            )
            row = cur.fetchone()
            if row is None:
                ledger_cents = _ledger_sum(cur, wallet2_xof)
                cur.execute(
                    """
                    INSERT INTO ledger.wallet_balances(account_id, available_cents, pending_cents, updated_at)
                    VALUES (%s::uuid, %s, 0, now());
                    """,
                    (wallet2_xof, ledger_cents),
                )
            cur.execute(
                """
                UPDATE ledger.wallet_balances
                SET available_cents = available_cents + 1
                WHERE account_id = %s::uuid;
                """,
                (wallet2_xof,),
            )

    r = client.get(
        f"/debug/invariants/wallet/{wallet2_xof}",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is False
    assert abs(payload["wallet"]["diff_cents"]) >= 1
