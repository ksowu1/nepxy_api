

# app/workers/payout_worker.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional
import time
import uuid

import logging

from db import get_conn
from app.payouts.repository import (
    update_status,
    claim_pending_payouts,
    claim_stale_sent_payouts,
)
from app.providers.base import ProviderResult
from app.providers.mobile_money.factory import get_provider
from services.metrics import increment_payout_attempt

SUPPORTED_PROVIDERS = {"TMONEY", "FLOOZ", "MTN", "MTN_MOMO", "MOMO", "THUNES"}

logger = logging.getLogger("nexapay")

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
DEFAULT_STALE_SECONDS = 60

# Poll throttle for SENT status checks (separate from submission backoff)
POLL_BACKOFF_SECONDS = 60

MAX_ATTEMPTS_ERROR = "MAX_ATTEMPTS_EXCEEDED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_retry_at(attempt_count: int) -> datetime:
    # exponential backoff: 30, 60, 120, 240, ...
    delay = BASE_BACKOFF_SECONDS * (2 ** max(0, attempt_count - 1))
    return _now() + timedelta(seconds=delay)


def _http_status(resp: Any) -> Optional[int]:
    if isinstance(resp, dict):
        v = resp.get("http_status")
        return int(v) if v is not None else None
    return None


def _is_retryable_http_status(status: Optional[int]) -> bool:
    return status in {408, 425, 429, 500, 502, 503, 504}


def _normalize_result(r: Any) -> ProviderResult:
    """
    Supports:
    - ProviderResult (new)
    - SimpleNamespace/old style: ok, provider_tx_id/provider_ref, response, error
    """
    if isinstance(r, ProviderResult):
        return r

    ok = bool(getattr(r, "ok", False))
    provider_ref = getattr(r, "provider_ref", None) or getattr(r, "provider_tx_id", None)
    response = getattr(r, "response", None)
    error = getattr(r, "error", None)

    if ok:
        # Old providers treat send as success => confirmed.
        return ProviderResult(
            status="CONFIRMED",
            provider_ref=provider_ref,
            response=response,
            error=None,
            retryable=False,
        )

    status = _http_status(response)
    retryable = _is_retryable_http_status(status)
    return ProviderResult(
        status="FAILED",
        provider_ref=provider_ref,
        response=response,
        error=error,
        retryable=retryable,
    )


# --- Test helper provider (tests can monkeypatch get_provider() to return this) ---
class MockProvider:
    def __init__(self, succeed: bool = True):
        self.succeed = succeed

    def send_cashout(self, payout: dict):
        if self.succeed:
            return SimpleNamespace(ok=True, provider_tx_id=str(uuid.uuid4()), response={"http_status": 200}, error=None)
        return SimpleNamespace(ok=False, provider_tx_id=None, response={"http_status": 504}, error="Gateway timeout")

    def get_cashout_status(self, payout: dict):
        if self.succeed:
            return SimpleNamespace(ok=True, provider_tx_id=payout.get("provider_ref") or str(uuid.uuid4()), response={"http_status": 200}, error=None)
        return SimpleNamespace(ok=False, provider_tx_id=None, response={"http_status": 504}, error="Gateway timeout")


def process_once(*, batch_size: int = 50, stale_seconds: int = DEFAULT_STALE_SECONDS) -> int:
    processed = 0
    with get_conn() as conn:
        pending = claim_pending_payouts(conn, batch_size=batch_size)
        stale_sent = claim_stale_sent_payouts(conn, batch_size=batch_size, stale_after_seconds=stale_seconds)

        print(f"[worker] found_pending={len(pending)} found_stale_sent={len(stale_sent)}")

        # process each payout independently so one bad row doesn't kill the whole batch
        for p in pending:
            try:
                processed += 1
                _handle_pending(conn, p)
            except Exception as e:
                _mark_internal_error(conn, p, e, from_status="PENDING")

        for p in stale_sent:
            try:
                processed += 1
                _handle_sent(conn, p)
            except Exception as e:
                _mark_internal_error(conn, p, e, from_status="SENT")

        conn.commit()

    return processed


def _mark_terminal_max_attempts(conn, *, payout_id: int, from_status: str, provider_ref: str | None, attempt_count: int, provider_response=None) -> None:
    update_status(
        conn,
        payout_id=payout_id,
        from_status=from_status,
        new_status="FAILED",
        provider_ref=provider_ref,
        provider_response=provider_response,
        last_error=MAX_ATTEMPTS_ERROR,
        retryable=False,
        attempt_count=attempt_count,  # do NOT increment here (no submission happened)
        next_retry_at=None,
        touch_last_attempt_at=False,
    )


def _mark_internal_error(conn, p: dict, e: Exception, *, from_status: str) -> None:
    payout_id = p["id"]
    attempt_count = int(p.get("attempt_count") or 0)

    # Worker error (not provider response). Retry unless we've exhausted submission attempts.
    if attempt_count >= MAX_ATTEMPTS:
        _mark_terminal_max_attempts(
            conn,
            payout_id=payout_id,
            from_status=from_status,
            provider_ref=p.get("provider_ref"),
            attempt_count=attempt_count,
            provider_response=p.get("provider_response"),
        )
        return

    update_status(
        conn,
        payout_id=payout_id,
        from_status=from_status,
        new_status="SENT",
        provider_ref=None,  # COALESCE keeps existing
        provider_response=p.get("provider_response"),
        last_error=f"Worker exception: {type(e).__name__}: {e}",
        retryable=True,
        attempt_count=attempt_count,  # no submission happened, so don't increment
        next_retry_at=_next_retry_at(max(1, attempt_count)),
    )


def _handle_pending(conn, p: dict) -> None:
    payout_id = p["id"]
    current_status = (p.get("status") or "PENDING").strip().upper()
    provider_name = (p.get("provider") or "").strip().upper()
    attempt_count = int(p.get("attempt_count") or 0)

    # If we've already hit max submissions, stop retrying (terminal).
    if attempt_count >= MAX_ATTEMPTS:
        _mark_terminal_max_attempts(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            provider_ref=p.get("provider_ref"),
            attempt_count=attempt_count,
            provider_response=p.get("provider_response"),
        )
        return

    phone = (p.get("phone_e164") or "").strip()
    if not phone:
        attempt = attempt_count + 1  # <-- increment because worker processed it
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error="Missing phone_e164",
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    if provider_name not in SUPPORTED_PROVIDERS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error=f"Unsupported provider: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,  # never submitted
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    provider = get_provider(provider_name)
    if provider is None:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error=f"Provider adapter not configured: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    if provider_name == "MOMO" and (p.get("provider_ref") or "").strip():
        res = _normalize_result(provider.get_cashout_status(p))
        provider_ref = p.get("provider_ref")
        provider_response = res.response
        err = res.error
        logger.info(
            "momo payout poll payout_id=%s provider_ref=%s status=%s error=%s",
            payout_id,
            provider_ref,
            res.status,
            err,
        )

        if res.status == "CONFIRMED":
            update_status(
                conn,
                payout_id=payout_id,
                from_status=current_status,
                new_status="CONFIRMED",
                provider_ref=provider_ref,
                provider_response=provider_response,
                last_error=None,
                retryable=False,
                attempt_count=attempt_count,
                next_retry_at=None,
            )
            return

        if res.status == "FAILED":
            update_status(
                conn,
                payout_id=payout_id,
                from_status=current_status,
                new_status="FAILED",
                provider_ref=provider_ref,
                provider_response=provider_response,
                last_error=err or "FAILED",
                retryable=False,
                attempt_count=attempt_count,
                next_retry_at=None,
            )
            return

        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="SENT",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=err,
            retryable=True,
            attempt_count=attempt_count,
            next_retry_at=_now() + timedelta(seconds=POLL_BACKOFF_SECONDS),
        )
        return

    # SEND (this is the only place attempt_count increments)
    attempt = attempt_count + 1
    res = _normalize_result(provider.send_cashout(p))
    increment_payout_attempt(provider_name, res.status)
    if provider_name == "MOMO":
        logger.info(
            "momo payout send payout_id=%s status=%s provider_ref=%s error=%s",
            payout_id,
            res.status,
            res.provider_ref,
            res.error,
        )

    provider_response = res.response
    err = res.error
    returned_ref = res.provider_ref  # may be None

    if res.status == "CONFIRMED":
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="CONFIRMED",
            provider_ref=returned_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    # If a provider returns explicit "SENT" in new ProviderResult, respect it
    if res.status == "SENT":
        # If this submission hit the max, don't schedule another retry.
        if attempt >= MAX_ATTEMPTS:
            update_status(
                conn,
                payout_id=payout_id,
                from_status=current_status,
                new_status="FAILED",
                provider_ref=returned_ref,
                provider_response=provider_response,
                last_error=MAX_ATTEMPTS_ERROR,
                retryable=False,
                attempt_count=attempt,
                next_retry_at=None,
            )
            return

        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="SENT",
            provider_ref=returned_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    # FAILED
    if res.retryable and attempt < MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="SENT",
            provider_ref=None,  # preserve existing
            provider_response=provider_response,
            last_error=err or "Retryable failure",
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    # If we got here, it's either non-retryable OR we hit max attempts on a retryable failure.
    terminal_error = MAX_ATTEMPTS_ERROR if attempt >= MAX_ATTEMPTS else (err or "Non-retryable failure")
    update_status(
        conn,
        payout_id=payout_id,
        from_status=current_status,
        new_status="FAILED",
        provider_ref=None,
        provider_response=provider_response,
        last_error=terminal_error,
        retryable=False,
        attempt_count=attempt,
        next_retry_at=None,
    )


def _handle_sent(conn, p: dict) -> None:
    """
    Polling does NOT increment attempt_count.
    attempt_count is strictly number of send_cashout submissions.

    Polling should NOT touch last_attempt_at (use touch_last_attempt_at=False),
    so stale detection continues to mean "stale since last submission".
    """
    payout_id = p["id"]
    current_status = (p.get("status") or "SENT").strip().upper()
    provider_name = (p.get("provider") or "").strip().upper()
    attempt_count = int(p.get("attempt_count") or 0)

    if provider_name not in SUPPORTED_PROVIDERS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error=f"Unsupported provider: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    provider = get_provider(provider_name)
    if provider is None:
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=p.get("provider_ref"),
            provider_response=p.get("provider_response"),
            last_error=f"Provider adapter not configured: {provider_name}",
            retryable=False,
            attempt_count=attempt_count,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    # Invariant: SENT must have provider_ref. If missing, resend instead of polling.
    if not (p.get("provider_ref") or "").strip():
        _resend_sent_missing_ref(conn, p, provider)
        return

    res = _normalize_result(provider.get_cashout_status(p))

    provider_ref = p.get("provider_ref")  # keep existing; do NOT synthesize
    provider_response = res.response
    err = res.error

    if res.status == "CONFIRMED":
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="CONFIRMED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt_count,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    if res.status == "FAILED":
        update_status(
            conn,
            payout_id=payout_id,
            from_status=current_status,
            new_status="FAILED",
            provider_ref=provider_ref,
            provider_response=provider_response,
            last_error=err or "FAILED",
            retryable=False,
            attempt_count=attempt_count,
            next_retry_at=None,
            touch_last_attempt_at=False,
        )
        return

    # Unknown/in-flight -> keep SENT + schedule next poll (avoid tight loop)
    update_status(
        conn,
        payout_id=payout_id,
        from_status=current_status,
        new_status="SENT",
        provider_ref=provider_ref,
        provider_response=provider_response,
        last_error=err,
        retryable=True,
        attempt_count=attempt_count,
        next_retry_at=_now() + timedelta(seconds=POLL_BACKOFF_SECONDS),
        touch_last_attempt_at=False,
    )


def _resend_sent_missing_ref(conn, p: dict, provider) -> None:
    payout_id = p["id"]
    attempt_count = int(p.get("attempt_count") or 0)

    # If we've already hit max submissions, stop retrying.
    if attempt_count >= MAX_ATTEMPTS:
        _mark_terminal_max_attempts(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            provider_ref=None,
            attempt_count=attempt_count,
            provider_response=p.get("provider_response"),
        )
        return

    attempt = attempt_count + 1
    res = _normalize_result(provider.send_cashout(p))
    increment_payout_attempt((p.get("provider") or "").strip().upper(), res.status)

    provider_response = res.response
    err = res.error
    returned_ref = res.provider_ref  # may be None

    if res.status == "CONFIRMED":
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="CONFIRMED",
            provider_ref=returned_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=False,
            attempt_count=attempt,
            next_retry_at=None,
        )
        return

    if res.status == "SENT":
        if attempt >= MAX_ATTEMPTS:
            update_status(
                conn,
                payout_id=payout_id,
                from_status="SENT",
                new_status="FAILED",
                provider_ref=returned_ref,
                provider_response=provider_response,
                last_error=MAX_ATTEMPTS_ERROR,
                retryable=False,
                attempt_count=attempt,
                next_retry_at=None,
            )
            return

        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="SENT",
            provider_ref=returned_ref,
            provider_response=provider_response,
            last_error=None,
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    # FAILED
    if res.retryable and attempt < MAX_ATTEMPTS:
        update_status(
            conn,
            payout_id=payout_id,
            from_status="SENT",
            new_status="SENT",
            provider_ref=None,  # keep missing ref (COALESCE preserves if any)
            provider_response=provider_response,
            last_error=err or "Retryable resend failure",
            retryable=True,
            attempt_count=attempt,
            next_retry_at=_next_retry_at(attempt),
        )
        return

    terminal_error = MAX_ATTEMPTS_ERROR if attempt >= MAX_ATTEMPTS else (err or "Non-retryable resend failure")
    update_status(
        conn,
        payout_id=payout_id,
        from_status="SENT",
        new_status="FAILED",
        provider_ref=None,
        provider_response=provider_response,
        last_error=terminal_error,
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
