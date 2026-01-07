

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from db import get_conn
from app.workers import payout_worker
from types import SimpleNamespace

@pytest.fixture(autouse=True)
def _cleanup_pytest_payouts():
    # Clean before
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM app.mobile_money_payouts WHERE provider_ref LIKE 'pytest-%'")
        conn.commit()
    yield
    # Clean after
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM app.mobile_money_payouts WHERE provider_ref LIKE 'pytest-%'")
        conn.commit()


def _insert_payout(
    *,
    provider: str,
    status: str = "PENDING",
    phone_e164: str | None = "+22890000000",
    provider_ref: str | None = None,
) -> uuid.UUID:
    """
    Inserts directly into app.mobile_money_payouts.

    NOTE: If transaction_id is FK-enforced, replace this helper with creating payout via cash-out endpoint.
    """
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
              NULL, 0, NULL, NULL, TRUE, NULL,
              %s, %s
            )
            """,
            (
                payout_id, tx_id, provider, (phone_e164 or ""), provider_ref,
                status, 1000, "XOF",
                now, now,
            ),
        )

        conn.commit()

    return payout_id



def _get_status(payout_id: uuid.UUID) -> tuple[str, int, str | None, str | None]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, attempt_count, provider_ref, last_error
            FROM app.mobile_money_payouts
            WHERE id = %s
            """,
            (payout_id,),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0], row[1], row[2], row[3]


def test_worker_pending_to_confirmed(monkeypatch):
    # Force provider success for supported providers
    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: payout_worker.MockProvider(succeed=True)
        if provider_name in payout_worker.SUPPORTED_PROVIDERS
        else None,
    )

    payout_id = _insert_payout(provider="TMONEY", status="PENDING", phone_e164="+22891112233")

    # Run up to 3 cycles in case other pending rows exist in the shared test DB
    status = None
    attempts = None
    provider_ref = None,
    last_error = None

    for _ in range(3):
        payout_worker.process_once(batch_size=500)
        status, attempts, provider_ref, last_error = _get_status(payout_id)
        if status == "CONFIRMED":
            break

    assert status == "CONFIRMED"
    assert provider_ref is not None
    assert last_error is None
    assert attempts >= 1


def test_worker_unsupported_provider_fails(monkeypatch):
    # Force get_provider to return None => unsupported => must FAIL
    monkeypatch.setattr(payout_worker, "get_provider", lambda provider_name: None)

    payout_id = _insert_payout(
        provider="UNKNOWN",
        status="PENDING",
        phone_e164="+22890001122",
        provider_ref=None,
    )

    # Run up to 3 cycles in case other pending rows exist in the shared test DB
    for _ in range(3):
        payout_worker.process_once(batch_size=500)
        status, attempts, provider_ref, last_error = _get_status(payout_id)
        if status == "FAILED":
            break

    assert status == "FAILED"
    assert provider_ref is None
    assert last_error is not None
    assert "Unsupported provider" in last_error
    assert attempts == 0


def test_worker_missing_phone_fails(monkeypatch):
    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: payout_worker.MockProvider(succeed=True)
        if provider_name in payout_worker.SUPPORTED_PROVIDERS
        else None,
    )

    payout_id = _insert_payout(provider="TMONEY", status="PENDING", phone_e164=None)

    payout_worker.process_once(batch_size=500)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "FAILED"
    assert last_error is not None
    assert "phone" in last_error.lower()
    assert attempts >= 1


def test_worker_recovers_stale_sent(monkeypatch):
    # Force provider success for supported providers
    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: payout_worker.MockProvider(succeed=True)
        if provider_name in payout_worker.SUPPORTED_PROVIDERS
        else None,
    )

    payout_id = _insert_payout(
        provider="TMONEY",
        status="SENT",
        phone_e164="+22895556677",
        provider_ref=None,
    )

    # Make it stale by setting updated_at far in the past (last_attempt_at left NULL)
    from datetime import datetime, timedelta, timezone
    with get_conn() as conn:
        cur = conn.cursor()
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        cur.execute(
            """
            UPDATE app.mobile_money_payouts
            SET updated_at = %s
            WHERE id = %s
            """,
            (stale_time, payout_id),
        )
        conn.commit()

    # stale_seconds=120 means 10 minutes old qualifies
    payout_worker.process_once(batch_size=500, stale_seconds=120)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "CONFIRMED"
    assert provider_ref is not None
    assert last_error is None
    assert attempts >= 1


def test_worker_schedules_retry_then_fails_after_max_attempts(monkeypatch):
    # Provider always fails
    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: payout_worker.MockProvider(succeed=False)
        if provider_name in payout_worker.SUPPORTED_PROVIDERS
        else None,
    )

    payout_id = _insert_payout(
        provider="TMONEY",
        status="PENDING",
        phone_e164="+22890009911",
        provider_ref=None,
    )

    # First run -> should go SENT and schedule retry (status stays SENT)
    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status in ("SENT", "FAILED")  # should be SENT unless max_attempts==1
    assert attempts >= 1
    assert provider_ref is None
    assert last_error is not None

    # Force retry eligibility by setting next_retry_at in the past repeatedly,
    # until it hits MAX_ATTEMPTS and becomes FAILED.
    from db import get_conn
    from datetime import datetime, timezone, timedelta

    for _ in range(10):
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE app.mobile_money_payouts
                SET next_retry_at = %s
                WHERE id = %s AND status = 'SENT'
                """,
                (datetime.now(timezone.utc) - timedelta(seconds=1), payout_id),
            )
            conn.commit()

        payout_worker.process_once(batch_size=500, stale_seconds=0)
        status, attempts, provider_ref, last_error = _get_status(payout_id)
        if status == "FAILED":
            break

    assert status == "FAILED"
    assert attempts >= payout_worker.MAX_ATTEMPTS
    assert last_error is not None


def _get_retry_meta(payout_id: uuid.UUID):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, attempt_count, next_retry_at, last_error
            FROM app.mobile_money_payouts
            WHERE id = %s
            """,
            (payout_id,),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0], row[1], row[2], row[3]



def test_non_retryable_failure_fails_fast(monkeypatch):
    class Provider400:
        def send_cashout(self, payout):
            return SimpleNamespace(
                ok=False,
                error="Invalid phone format",
                response={"http_status": 400, "error": "invalid_phone"},
            )

    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: Provider400() if provider_name in payout_worker.SUPPORTED_PROVIDERS else None,
    )

    payout_id = _insert_payout(provider="TMONEY", status="PENDING", phone_e164="+22890009911", provider_ref=None)

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, next_retry_at, last_error = _get_retry_meta(payout_id)
    assert status == "FAILED"
    assert attempts >= 1
    assert next_retry_at is None
    assert last_error is not None
    assert "invalid" in last_error.lower() or "phone" in last_error.lower()


def test_retryable_failure_schedules_retry(monkeypatch):
    class Provider504:
        def send_cashout(self, payout):
            return SimpleNamespace(
                ok=False,
                error="Gateway timeout",
                response={"http_status": 504, "error": "timeout"},
            )

    monkeypatch.setattr(
        payout_worker,
        "get_provider",
        lambda provider_name: Provider504() if provider_name in payout_worker.SUPPORTED_PROVIDERS else None,
    )

    payout_id = _insert_payout(provider="TMONEY", status="PENDING", phone_e164="+22890009911", provider_ref=None)

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, next_retry_at, last_error = _get_retry_meta(payout_id)
    # Retryable errors keep it in SENT and schedule next_retry_at
    assert status == "SENT"
    assert attempts >= 1
    assert next_retry_at is not None
    assert last_error is not None
    assert "timeout" in last_error.lower() or "gateway" in last_error.lower()
