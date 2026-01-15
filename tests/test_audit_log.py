import uuid

from db import get_conn
from tests.conftest import _auth_headers


def test_admin_payout_confirmed_writes_audit_log(client, admin_user, user1, wallet1_xof):
    idem = f"pytest-audit-cashout-{uuid.uuid4()}"
    payload_out = {
        "wallet_id": wallet1_xof,
        "amount_cents": 100,
        "country": "BJ",
        "provider_ref": f"audit-ref-{uuid.uuid4()}",
        "provider": "TMONEY",
        "phone_e164": "+22890000000",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload_out,
        headers=_auth_headers(user1.token, idem=idem),
    )
    assert r.status_code == 200, r.text
    tx_id = r.json()["transaction_id"]

    r2 = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/confirmed",
        headers=_auth_headers(admin_user.token, idem=f"pytest-admin-{uuid.uuid4()}"),
    )
    assert r2.status_code == 200, r2.text

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM app.audit_log
                WHERE action = 'PAYOUT_CONFIRMED'
                  AND target_id = %s
                """,
                (str(tx_id),),
            )
            row = cur.fetchone()
            assert row and row[0] >= 1
