import uuid
import hmac
import hashlib
import json
from datetime import datetime, timezone

from db import get_conn
from tests.conftest import _auth_headers


def _sign(body_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


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


def test_admin_webhook_events_for_payout(client, admin_user, user1, wallet1_xof, monkeypatch):
    monkeypatch.setenv("TMONEY_WEBHOOK_SECRET", "dev_secret_tmoney")

    cashin_ref = f"pytest-cashin-{uuid.uuid4()}"
    r = client.post(
        "/v1/cash-in/mobile-money",
        json={
            "wallet_id": wallet1_xof,
            "amount_cents": 2000,
            "country": "TG",
            "provider_ref": cashin_ref,
            "provider": "TMONEY",
        },
        headers=_auth_headers(user1.token, idem=cashin_ref),
    )
    assert r.status_code in (200, 201), r.text

    r = client.post(
        "/v1/cash-out/mobile-money",
        json={
            "wallet_id": wallet1_xof,
            "amount_cents": 100,
            "country": "BJ",
            "provider_ref": f"cashout-{uuid.uuid4()}",
            "provider": "TMONEY",
            "phone_e164": "+22890009911",
        },
        headers=_auth_headers(user1.token, idem=f"idem-{uuid.uuid4()}"),
    )
    assert r.status_code in (200, 201), r.text
    tx_id = r.json()["transaction_id"]

    payout = client.get(
        f"/v1/payouts/{tx_id}",
        headers=_auth_headers(user1.token),
    )
    assert payout.status_code == 200, payout.text
    ext = payout.json()["external_ref"]
    provider_ref = payout.json().get("provider_ref")

    body_obj = {"external_ref": ext, "status": "SUCCESS"}
    body_bytes = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _sign(body_bytes, "dev_secret_tmoney")

    r = client.post(
        "/v1/webhooks/tmoney",
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/v1/admin/mobile-money/payouts/{tx_id}/webhook-events?limit=50",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    events = body["events"]
    assert any((e.get("external_ref") == ext) or (provider_ref and e.get("provider_ref") == provider_ref) for e in events)


def test_admin_payout_confirm_audit_event(client, admin_user):
    tx_id = _insert_payout(status="PENDING")
    r = client.post(
        f"/v1/admin/mobile-money/payouts/{tx_id}/confirmed",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    request_id = r.headers.get("X-Request-ID")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT admin_user_id::text, action, entity_type, entity_id, request_id
            FROM audit.admin_events
            WHERE entity_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (str(tx_id),),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[0] == str(admin_user.user_id)
    assert row[1] == "PAYOUT_CONFIRMED"
    assert row[2] == "PAYOUT"
    assert row[3] == str(tx_id)
    assert row[4] == request_id

    r = client.get(
        f"/v1/admin/audit-events?entity_id={tx_id}&limit=5",
        headers=_auth_headers(admin_user.token),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["count"] >= 1
    assert any(e.get("entity_id") == str(tx_id) for e in payload.get("events", []))
