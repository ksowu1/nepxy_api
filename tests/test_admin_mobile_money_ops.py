import uuid
from datetime import datetime, timezone

from db import get_conn
from tests.conftest import _auth_headers


def _insert_payout(
    *,
    status: str,
    provider: str = "TMONEY",
    retryable: bool = True,
    attempt_count: int = 0,
) -> uuid.UUID:
    payout_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        cur = conn.cursor()
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
              %s, %s
            )
            """,
            (
                payout_id,
                tx_id,
                provider,
                "+22890000000",
                f"pytest-{uuid.uuid4()}",
                status,
                1000,
                "XOF",
                "ERR" if status in ("FAILED", "RETRY") else None,
                int(attempt_count),
                retryable,
                now,
                now,
            ),
        )
        conn.commit()

    return tx_id


def test_admin_can_list_failed_payouts(client, admin_user):
    tx_id = _insert_payout(status="FAILED")
    r = client.get(
        "/v1/admin/mobile-money/payouts?status=FAILED",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    payloads = r.json()["payouts"]
    assert any(p["transaction_id"] == str(tx_id) for p in payloads)
    required = {
        "transaction_id",
        "status",
        "provider",
        "amount_cents",
        "currency",
        "phone_e164",
        "attempt_count",
        "last_error",
        "retryable",
        "next_retry_at",
        "provider_ref",
        "external_ref",
        "updated_at",
    }
    assert required.issubset(payloads[0].keys())


def test_non_admin_cannot_list_payouts(client, user2):
    r = client.get(
        "/v1/admin/mobile-money/payouts?status=FAILED",
        headers=_auth_headers(user2.token),
    )
    assert r.status_code == 403, r.text


def test_admin_retry_failed_payout_sets_pending(client, admin_user):
    tx_id = _insert_payout(status="FAILED", retryable=True, attempt_count=2)
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/retry",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["next_retry_at"] is not None
    assert body["attempt_count"] == 2

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, last_error, next_retry_at, retryable, attempt_count
            FROM app.mobile_money_payouts
            WHERE transaction_id = %s::uuid
            """,
            (str(tx_id),),
        )
        row = cur.fetchone()
        assert row[0] == "PENDING"
        assert row[1] is None
        assert row[2] is not None
        assert row[3] is True
        assert row[4] == 2


def test_retry_confirmed_payout_returns_409(client, admin_user):
    tx_id = _insert_payout(status="CONFIRMED")
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/retry",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 409, r.text
    assert r.json().get("detail") == "ALREADY_CONFIRMED"


def test_retry_non_retryable_returns_409(client, admin_user):
    tx_id = _insert_payout(status="FAILED", retryable=False)
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/retry",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 409, r.text
    assert r.json().get("detail") == "NOT_RETRYABLE"


def test_retry_non_retryable_with_force_succeeds(client, admin_user):
    tx_id = _insert_payout(status="FAILED", retryable=False, attempt_count=3)
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/retry",
        headers=_auth_headers(admin_user.token),
        json={"force": True, "reason": "manual retry"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["attempt_count"] == 3

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, last_error, next_retry_at, retryable, attempt_count
            FROM app.mobile_money_payouts
            WHERE transaction_id = %s::uuid
            """,
            (str(tx_id),),
        )
        row = cur.fetchone()
        assert row[0] == "PENDING"
        assert row[1] is None
        assert row[2] is not None
        assert row[3] is True
        assert row[4] == 3


def test_admin_webhook_events_for_payout(client, admin_user):
    tx_id = _insert_payout(status="PENDING")
    event_hash = uuid.uuid4().hex

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app.webhook_events (
              provider, external_ref, provider_ref, status_raw, payload, headers,
              received_at, payout_transaction_id, signature_valid, event_hash
            )
            VALUES (
              %s, %s, %s, %s, %s::jsonb, %s::jsonb,
              now(), %s::uuid, %s, %s
            )
            """,
            (
                "TMONEY",
                "ext-1",
                "prov-1",
                "SUCCESS",
                "{}",
                "{}",
                str(tx_id),
                True,
                event_hash,
            ),
        )
        conn.commit()

    r = client.get(
        f"/v1/admin/mobile-money/payouts/{tx_id}/webhook-events?limit=50",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    events = r.json()["events"]
    assert events, "Expected at least one webhook event"
    assert "signature_valid" in events[0]
    assert "event_hash" in events[0]
    assert "created_at" in events[0]
