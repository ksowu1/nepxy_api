

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


def _get_provider_response(payout_id: uuid.UUID):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT provider_response
            FROM app.mobile_money_payouts
            WHERE id = %s
            """,
            (payout_id,),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0]


def _insert_ledger_tx(*, tx_id: uuid.UUID, amount_cents: int, currency: str, country: str = "GH"):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ledger.ledger_transactions (
              id, type, status, country, currency, amount_cents, description, idempotency_key, external_ref
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tx_id,
                "CASH_OUT",
                "PENDING",
                country,
                currency,
                amount_cents,
                "pytest momo",
                f"pytest-{uuid.uuid4()}",
                f"pytest-ext-{uuid.uuid4()}",
            ),
        )
        conn.commit()


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


def test_worker_momo_status_successful_transitions(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")
    from app.providers.mobile_money import factory
    factory._PROVIDER_CACHE.clear()

    def fake_post(url, headers=None, auth=None, json=None):
        assert url.endswith("/disbursement/token/")
        return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123", "expires_in": 3600})

    def fake_get(url, headers=None):
        assert url.endswith("/disbursement/v1_0/transfer/pytest-momo-ref")
        return SimpleNamespace(status_code=200, json=lambda: {"status": "SUCCESSFUL"})

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)
    monkeypatch.setattr("services.providers.momo.requests.get", fake_get)

    payout_id = _insert_payout(
        provider="MOMO",
        status="SENT",
        phone_e164="+233200000000",
        provider_ref="pytest-momo-ref",
    )

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "CONFIRMED"
    assert provider_ref == "pytest-momo-ref"
    assert last_error is None
    provider_response = _get_provider_response(payout_id)
    assert provider_response.get("stage") == "poll"


def test_worker_momo_transfer_creates_sent_and_saves_response(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")
    from app.providers.mobile_money import factory
    factory._PROVIDER_CACHE.clear()

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            assert json["currency"] == "GHS"
            return SimpleNamespace(
                status_code=202,
                json=lambda: {"status": "PENDING", "referenceId": "momo-transfer-ref"},
                text="",
            )
        raise AssertionError("unexpected url")

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)

    payout_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    _insert_ledger_tx(tx_id=tx_id, amount_cents=1000, currency="GHS", country="GH")

    provider_ref = None
    with get_conn() as conn:
        cur = conn.cursor()
        now = datetime.now(timezone.utc)
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
                payout_id,
                tx_id,
                "MOMO",
                "+233200000000",
                provider_ref,
                "PENDING",
                1000,
                "GHS",
                now,
                now,
            ),
        )
        conn.commit()

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "SENT"
    assert provider_ref == "momo-transfer-ref"
    assert last_error is None
    provider_response = _get_provider_response(payout_id)
    assert provider_response is not None
    assert provider_response.get("stage") == "create"
    assert provider_response.get("http_status") == 202
    assert provider_response.get("body", {}).get("status") == "PENDING"

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ledger.ledger_transactions WHERE id = %s", (tx_id,))
        conn.commit()


def test_worker_momo_status_failed_marks_failed(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")
    from app.providers.mobile_money import factory
    factory._PROVIDER_CACHE.clear()

    def fake_post(url, headers=None, auth=None, json=None):
        return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123", "expires_in": 3600})

    def fake_get(url, headers=None):
        return SimpleNamespace(status_code=200, json=lambda: {"status": "FAILED"})

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)
    monkeypatch.setattr("services.providers.momo.requests.get", fake_get)

    payout_id = _insert_payout(
        provider="MOMO",
        status="SENT",
        phone_e164="+233200000000",
        provider_ref="pytest-momo-failed",
    )

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "FAILED"
    assert provider_ref == "pytest-momo-failed"
    assert last_error is not None
    provider_response = _get_provider_response(payout_id)
    assert provider_response.get("stage") == "poll"


def test_worker_momo_sent_uses_status_only(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")
    from app.providers.mobile_money import factory
    factory._PROVIDER_CACHE.clear()

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123", "expires_in": 3600})
        raise AssertionError("transfer creation should not be called for SENT payouts")

    def fake_get(url, headers=None):
        return SimpleNamespace(status_code=200, json=lambda: {"status": "PENDING"})

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)
    monkeypatch.setattr("services.providers.momo.requests.get", fake_get)

    payout_id = _insert_payout(
        provider="MOMO",
        status="SENT",
        phone_e164="+233200000000",
        provider_ref="pytest-momo-sent",
    )

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "SENT"
    assert provider_ref == "pytest-momo-sent"
    provider_response = _get_provider_response(payout_id)
    assert provider_response.get("stage") == "poll"


def test_worker_momo_pending_with_ref_still_creates(monkeypatch):
    monkeypatch.setenv("MOMO_ENV", "sandbox")
    monkeypatch.setenv("MOMO_API_USER_ID", "user-123")
    monkeypatch.setenv("MOMO_API_KEY", "key-123")
    monkeypatch.setenv("MOMO_DISBURSE_SUB_KEY", "sub-123")
    from app.providers.mobile_money import factory
    factory._PROVIDER_CACHE.clear()

    def fake_post(url, headers=None, auth=None, json=None):
        if url.endswith("/disbursement/token/"):
            return SimpleNamespace(status_code=200, json=lambda: {"access_token": "token-123", "expires_in": 3600})
        if url.endswith("/disbursement/v1_0/transfer"):
            return SimpleNamespace(
                status_code=202,
                json=lambda: {"status": "PENDING", "referenceId": "momo-ref-reuse"},
                text="",
            )
        raise AssertionError("unexpected url")

    monkeypatch.setattr("services.providers.momo.requests.post", fake_post)

    payout_id = uuid.uuid4()
    tx_id = uuid.uuid4()
    _insert_ledger_tx(tx_id=tx_id, amount_cents=1000, currency="GHS", country="GH")

    with get_conn() as conn:
        cur = conn.cursor()
        now = datetime.now(timezone.utc)
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
                payout_id,
                tx_id,
                "MOMO",
                "+233200000000",
                "pytest-momo-pending",
                "PENDING",
                1000,
                "GHS",
                now,
                now,
            ),
        )
        conn.commit()

    payout_worker.process_once(batch_size=500, stale_seconds=0)

    status, attempts, provider_ref, last_error = _get_status(payout_id)
    assert status == "SENT"
    assert provider_ref == "momo-ref-reuse"
    provider_response = _get_provider_response(payout_id)
    assert provider_response.get("stage") == "create"

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ledger.ledger_transactions WHERE id = %s", (tx_id,))
        conn.commit()


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
