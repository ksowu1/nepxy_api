from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from db import get_conn
from services.reconcile import run_reconcile
from tests.conftest import _auth_headers, AuthedUser


def test_reconcile_flags_provider_mismatch(client: TestClient, user2: AuthedUser, funded_wallet2_xof: str):
    provider_ref = f"recon-confirm-{uuid.uuid4()}"
    payload = {
        "wallet_id": funded_wallet2_xof,
        "amount_cents": 1000,
        "country": "GH",
        "provider_ref": provider_ref,
        "provider": "MOMO",
        "phone_e164": "+233501234567",
    }
    r = client.post(
        "/v1/cash-out/mobile-money",
        json=payload,
        headers=_auth_headers(user2.token, idem=provider_ref),
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json().get("transaction_id")
    assert tx_id, "missing transaction_id"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app.mobile_money_payouts
                SET status = 'PENDING', provider_ref = %s, updated_at = now() - interval '5 minutes'
                WHERE transaction_id = %s::uuid
                """,
                (provider_ref, str(tx_id)),
            )
            cur.execute(
                """
                INSERT INTO app.mobile_money_payouts (
                  transaction_id, provider, phone_e164, provider_ref,
                  status, amount_cents, currency,
                  last_error, attempt_count, last_attempt_at, next_retry_at, retryable, provider_response,
                  created_at, updated_at
                )
                VALUES (
                  gen_random_uuid(), 'MOMO', %s, %s,
                  'PENDING', 1000, 'GHS',
                  NULL, 0, NULL, NULL, TRUE, NULL,
                  now() - interval '10 minutes', now() - interval '10 minutes'
                )
                """,
                ("+233501234567", provider_ref),
            )
        conn.commit()

    report = run_reconcile(stale_minutes=0, lookback_minutes=0)
    assert report["summary"]["status_mismatch"] >= 1
    categories = [item["category"] for item in report["items"]]
    assert "status_mismatch" in categories
