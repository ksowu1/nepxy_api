
# app/workers/payout_worker.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import time
import uuid

from psycopg2.extras import RealDictCursor

from db import get_conn
from app.payouts.repository import update_status
from app.providers.mobile_money.factory import get_provider

# Tests expect this to exist
SUPPORTED_PROVIDERS = {"TMONEY", "FLOOZ", "MTN", "MTN_MOMO"}

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
DEFAULT_STALE_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_retry_at(attempt_count: int) -> datetime:
    # 30, 60, 120, 240, 480...
    delay = BASE_BACKOFF_SECONDS * (2 ** max(0, attempt_count - 1))
    return _now() + timedelta(seconds=delay)


def _http_status(resp: Any) -> Optional[int]:
    if isinstance(resp, dict):
        v = resp.get("http_status")
        return int(v) if v is not None else None
    return None


def _is_retryable(resp: Any) -> bool:
    s = _http_status(resp)
    # Treat these as transient
    return s in {408, 425, 429, 500, 502, 503, 504}


def _claim_pending(conn, *, limit: int) -> List[dict]:
    # Claim rows for this transaction using SKIP LOCKED
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM app.mobile_money_payouts
            WHERE status = 'PENDING'
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def _claim_stale_sent(conn, *, limit: int, stale_seconds: int) -> List[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM app.mobile_money_payouts
            WHERE status = 'SENT'
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
              AND updated_at <= (NOW() - (%s || ' seconds')::interval)
            ORDER BY updated_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT %s
            """,
            (stale_seconds, limit),
        )
        return list(cur.fetchall())


# --- Test helper provider (tests monkeypatch this) ---
class MockProvider:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed

    def send_cashout(self, payout: dict):
        if self.succeed:
            return SimpleNamespace(ok=True, provider_tx_id=str(uuid.uuid4()), response={"http_status": 200}, error=None)
        return SimpleNamespace(ok=False, provider_tx_id=None, response={"http_status": 504}, error="Gateway timeout")

    def get_cashout_status(self, payout: dict):
        # For tests, treat as confirmed when succeed=True
        if self.succeed:
            return SimpleNamespace(ok=True, provider_tx_id=payout.get("provider_ref") or str(uuid.uuid4()), response={"http_status": 200}, error=None)
        return SimpleNamespace(ok=False, provider_tx_id=None, response={"http_status": 504}, error="Gateway timeout")


def process_once(*, batch_size: int = 50, stale_seconds: int = DEFAULT_STALE_SECONDS) -> int:
    processed = 0
    with get_conn() as conn:
        pending = _claim_pending(conn, limit=batch_size)
        stale_sent = _claim_stale_sent(conn, limit=batch_size, stale_seconds=stale_seconds)

        print(f"[worker] found_pending={len(pending)} found_stale_sent={len(stale_sent)}")

        for p in pending:
            processed += 1
            _handle_pending(conn, p)

        for p in stale_sent:
            processed += 1
            _handle_sent(conn, p)

        try:
            conn.commit()
        except Exception:
            pass

    return processed


def _handle_pending(conn, p: dict) -> None:
    payout_id = p["id"]
    current_status = (p.get("status") or "PENDING").strip().upper()
    provider_name = (p.get("provider") or "").strip().upper()
    attempt_count = int(p.get("attempt_count") or 0)

    # Ensure locals always exist (prevents UnboundLocalError)
    provider_ref = p.get("provider_ref")
    provider_response = p.get("provider_response")
    err = None

    phone = (p.get("phone_e164") or "").strip()
    if not phone:
        # Missing phone: this IS an attempt (tests expect attempts >= 1)
        attempt = attempt_count + 1
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error="Missing phone_e164",
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    provider = get_provider(provider_name)
    if provider is None:
        # Unsupported provider: attempts MUST NOT increment (other tests expect 0)
        print(f"[worker] payout={payout_id} provider={provider_name} -> FAILED (unsupported)")
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=None,
            provider_response=None,
            last_error=f"Unsupported provider: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,  # unchanged
            next_retry_at=None,
        )
        return

    attempt = attempt_count + 1
    if attempt > MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error="Max attempts exceeded",
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    stable_ref = (p.get("provider_ref") or str(payout_id)).strip()

    # Try (or retry) sending
    res = provider.send_cashout(p)

    provider_response = getattr(res, "response", None)
    err = getattr(res, "error", None)

    # Only store provider_ref if provider actually returns one
    provider_ref = getattr(res, "provider_tx_id", None)

    if getattr(res, "ok", False):
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="CONFIRMED",
            provider_ref=provider_ref or stable_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    retryable = _is_retryable(provider_response)
    if retryable and attempt < MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="SENT",
            provider_ref=provider_ref,  # stays NULL if provider didn't give one
            provider_response=provider_response,
            last_error=err or "Retryable failure",
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    update_status(
        conn,
        payout_id=payout_id,
        from_status=current_status,
        new_status="FAILED",
        provider_ref=provider_ref,
        provider_response=provider_response,
        last_error=err or "Non-retryable failure",
        retryable=False,
        attempt_count=attempt,
        next_retry_at=None,
    )

def _handle_sent(conn, p: dict) -> None:
    payout_id = p["id"]
    provider_name = (p.get("provider") or "").strip().upper()
    attempt_count = int(p.get("attempt_count") or 0)

    phone = (p.get("phone_e164") or "").strip()
    if not phone:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error="Missing phone_e164",
            retryable=False,
            attempt_count=attempt_count,  # unchanged
            next_retry_at=None,
        )
        return

    provider = get_provider(provider_name)
    if provider is None:
        print(f"[worker] payout={payout_id} provider={provider_name} -> FAILED (unsupported)")
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="FAILED",
            provider_ref=None,
            provider_response=None,
            last_error=f"Unsupported provider: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,  # unchanged
            next_retry_at=None,
        )
        return

    # IMPORTANT for invariant test:
    # If SENT but no provider_ref, DO NOT POLL status. Re-send instead.
    if not (p.get("provider_ref") or "").strip():
        _resend_sent_missing_ref(conn, p, provider)
        return

    attempt = attempt_count + 1
    if attempt > MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error="Max attempts exceeded",
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    res = provider.get_cashout_status(p)
    provider_ref = getattr(res, "provider_tx_id", None) or p.get("provider_ref")
    provider_response = getattr(res, "response", None)
    err = getattr(res, "error", None)

    if getattr(res, "ok", False):
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="CONFIRMED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    retryable = _is_retryable(provider_response)
    if retryable and attempt < MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="SENT",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=err or "Retryable status failure",
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    update_status(
        conn,
        payout_id=payout_id,
        from_status="SENT",
        new_status="FAILED",
        provider_ref=provider_ref,
        provider_response=provider_response,
        last_error=err or "Non-retryable status failure",
        retryable=False,
        attempt_count=attempt,
        next_retry_at=None,
    )


def _resend_sent_missing_ref(conn, p: dict, provider) -> None:
    payout_id = p["id"]
    attempt_count = int(p.get("attempt_count") or 0)

    attempt = attempt_count + 1
    if attempt > MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="FAILED",
            provider_ref=None,
            provider_response=None,
            last_error="Max attempts exceeded (missing provider_ref)",
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    stable_ref = str(payout_id)
    res = provider.send_cashout(p)

    provider_ref = getattr(res, "provider_tx_id", None) or stable_ref
    provider_response = getattr(res, "response", None)
    err = getattr(res, "error", None)

    if getattr(res, "ok", False):
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="CONFIRMED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    retryable = _is_retryable(provider_response)
    if retryable and attempt < MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="SENT",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=err or "Retryable resend failure",
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    update_status(
        conn,
        payout_id=payout_id,
        from_status="SENT",
        new_status="FAILED",
        provider_ref=provider_ref,
        provider_response=provider_response,
        last_error=err or "Non-retryable resend failure",
        retryable=False,
        attempt_count=attempt,
        next_retry_at=None,
    )


def run_forever(*, poll_seconds: int = 5, batch_size: int = 50, stale_seconds: int = DEFAULT_STALE_SECONDS) -> None:
    print("[worker] payout worker started")
    while True:
        n = process_once(batch_size=batch_size, stale_seconds=stale_seconds)
        if n == 0:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
