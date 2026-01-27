import json
import time
import uuid

from fastapi.testclient import TestClient

from db import get_conn
from main import create_app


def _sign(body_bytes: bytes, secret: str) -> str:
    import hmac
    import hashlib

    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _insert_thunes_payout(*, status: str, external_ref: str, provider_ref: str) -> uuid.UUID:
    payout_id = uuid.uuid4()
    tx_id = uuid.uuid4()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ledger.ledger_transactions (
              id, type, status, country, currency, amount_cents, description, idempotency_key, external_ref
            )
            VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                tx_id,
                "CASH_OUT",
                "PENDING",
                "GH",
                "GHS",
                1000,
                "pytest thunes",
                f"pytest-{uuid.uuid4()}",
                external_ref,
            ),
        )
        cur.execute(
            """
            INSERT INTO app.mobile_money_payouts (
              id, transaction_id, provider, phone_e164, provider_ref,
              status, amount_cents, currency,
              last_error, attempt_count, last_attempt_at, next_retry_at, retryable, provider_response,
              created_at, updated_at
            )
            VALUES (
              %s, %s, %s, %s, %s,
              %s, %s, %s,
              %s, %s, NULL, NULL, %s, NULL,
              now(), now()
            )
            """,
            (
                payout_id,
                tx_id,
                "THUNES",
                "+233200000000",
                provider_ref,
                status,
                1000,
                "GHS",
                None,
                0,
                True,
            ),
        )
        conn.commit()
    return tx_id


def test_thunes_webhook_flow_updates_payout_and_logs_event(client, admin, monkeypatch):
    monkeypatch.setenv("THUNES_WEBHOOK_SECRET", "dev_secret_thunes")

    external_ref = f"ext-{uuid.uuid4()}"
    provider_ref = f"thunes-{uuid.uuid4()}"
    tx_id = _insert_thunes_payout(status="PENDING", external_ref=external_ref, provider_ref=provider_ref)

    body_obj = {"external_ref": external_ref, "provider_ref": provider_ref, "status": "SUCCESSFUL"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_thunes")

    r = client.post(
        "/v1/webhooks/thunes",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200, r.text

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM app.mobile_money_payouts WHERE transaction_id = %s::uuid",
            (str(tx_id),),
        )
        row = cur.fetchone()
        assert row and row[0] == "CONFIRMED"

    from db import close_pool
    close_pool()

    admin_client = TestClient(create_app(), raise_server_exceptions=False)
    events = []
    for _ in range(5):
        r = admin_client.get(
            f"/v1/admin/mobile-money/payouts/{tx_id}/webhook-events?limit=50",
            headers={"Authorization": f"Bearer {admin.token}"},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        events = payload.get("events") or payload.get("items") or []
        if events:
            break
        time.sleep(0.1)
    assert events, payload
    refs = [e.get("external_ref") or e.get("provider_ref") for e in events]
    assert external_ref in refs or provider_ref in refs
