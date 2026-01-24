


# app/payouts/repository.py
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from psycopg2.extras import RealDictCursor

DEFAULT_BACKOFF_SECONDS = 60  # used when caller doesn't provide next_retry_at
TERMINAL_STATUSES = ("CONFIRMED", "FAILED")


def _adapt_json(value: Any):
    """
    psycopg2 can't adapt dict -> use psycopg2.extras.Json
    fallback to json.dumps for safety.
    """
    try:
        from psycopg2.extras import Json as Psycopg2Json
        return Psycopg2Json(value)
    except Exception:
        return json.dumps(value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==========================================================
# Claiming payouts for worker
# ==========================================================

def claim_pending_payouts(conn, *, batch_size: int) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        WITH picked AS (
          SELECT p.id
          FROM app.mobile_money_payouts p
          WHERE p.status = 'PENDING'
            AND (p.next_retry_at IS NULL OR p.next_retry_at <= now())
          ORDER BY p.created_at
          LIMIT %s
          FOR UPDATE SKIP LOCKED
        )
        SELECT
          p.id,
          p.transaction_id,
          COALESCE(NULLIF(btrim(upper(p.provider)), ''), btrim(upper(tx.provider))) AS provider,
          COALESCE(p.phone_e164, tx.phone_e164) AS phone_e164,
          p.request_id,
          p.provider_ref,
          p.attempt_count,
          p.last_attempt_at,
          p.next_retry_at,
          tx.amount_cents,
          tx.currency,
          tx.external_ref,
          tx.country
        FROM app.mobile_money_payouts p
        JOIN picked ON picked.id = p.id
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        """,
        (batch_size,),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def claim_stale_sent_payouts(conn, *, batch_size: int, stale_after_seconds: int) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        WITH picked AS (
          SELECT p.id
          FROM app.mobile_money_payouts p
          WHERE p.status = 'SENT'
            AND (p.next_retry_at IS NULL OR p.next_retry_at <= now())
            AND (
              (p.last_attempt_at IS NOT NULL AND p.last_attempt_at <= (now() - (%s || ' seconds')::interval))
              OR
              (p.last_attempt_at IS NULL AND p.updated_at <= (now() - (%s || ' seconds')::interval))
            )
          ORDER BY p.next_retry_at NULLS FIRST, p.updated_at
          LIMIT %s
          FOR UPDATE SKIP LOCKED
        )
        SELECT
          p.id,
          p.transaction_id,
          COALESCE(NULLIF(btrim(upper(p.provider)), ''), btrim(upper(tx.provider))) AS provider,
          COALESCE(p.phone_e164, tx.phone_e164) AS phone_e164,
          p.request_id,
          p.provider_ref,
          p.attempt_count,
          p.last_attempt_at,
          p.next_retry_at,
          tx.amount_cents,
          tx.currency,
          tx.external_ref,
          tx.country
        FROM app.mobile_money_payouts p
        JOIN picked ON picked.id = p.id
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        """,
        (stale_after_seconds, stale_after_seconds, batch_size),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ==========================================================
# Updates
# ==========================================================

def update_status(
    conn,
    *,
    payout_id: int,
    new_status: str,
    from_status: Optional[str] = None,
    provider_ref: Optional[str] = None,
    provider_response: Optional[dict[str, Any]] = None,
    last_error: Optional[str] = None,
    retryable: Optional[bool] = None,
    attempt_count: Optional[int] = None,
    next_retry_at: Optional[datetime] = None,
    touch_last_attempt_at: bool = True,
) -> bool:
    cur = conn.cursor()

    effective_next_retry_at = next_retry_at
    if effective_next_retry_at is None and new_status in {"SENT", "RETRY"} and retryable is True:
        effective_next_retry_at = _utcnow() + timedelta(seconds=DEFAULT_BACKOFF_SECONDS)

    resp = _adapt_json(provider_response) if provider_response is not None else None

    if from_status is None:
        cur.execute(
            """
            UPDATE app.mobile_money_payouts
            SET
              status = %s,
              provider_ref = COALESCE(%s, provider_ref),
              provider_response = COALESCE(%s::jsonb, provider_response),
              last_error = %s,
              retryable = COALESCE(%s, retryable),
              attempt_count = COALESCE(%s, attempt_count),
              last_attempt_at = CASE WHEN %s THEN now() ELSE last_attempt_at END,
              next_retry_at = %s,
              updated_at = now()
            WHERE id = %s
            """,
            (
                new_status,
                provider_ref,
                resp,
                last_error,
                retryable,
                attempt_count,
                touch_last_attempt_at,
                effective_next_retry_at,
                payout_id,
            ),
        )
    else:
        cur.execute(
            """
            UPDATE app.mobile_money_payouts
            SET
              status = %s,
              provider_ref = COALESCE(%s, provider_ref),
              provider_response = COALESCE(%s::jsonb, provider_response),
              last_error = %s,
              retryable = COALESCE(%s, retryable),
              attempt_count = COALESCE(%s, attempt_count),
              last_attempt_at = CASE WHEN %s THEN now() ELSE last_attempt_at END,
              next_retry_at = %s,
              updated_at = now()
            WHERE id = %s
              AND status = %s
            """,
            (
                new_status,
                provider_ref,
                resp,
                last_error,
                retryable,
                attempt_count,
                touch_last_attempt_at,
                effective_next_retry_at,
                payout_id,
                from_status,
            ),
        )

    return cur.rowcount == 1


def update_status_by_provider_ref(
    conn,
    *,
    provider_ref: str,
    new_status: str,
    provider_response: Optional[dict[str, Any]] = None,
    last_error: Optional[str] = None,
    retryable: Optional[bool] = None,
    next_retry_at: Optional[datetime] = None,
    allow_terminal_override: bool = False,
    provider: str | None = None,  # accepted for compatibility, IGNORED
) -> bool:
    """
    Update by provider_ref.
    NOTE: provider param is ignored to allow cross-provider webhook updates.
    """
    cur = conn.cursor()
    resp_json = _adapt_json(provider_response) if provider_response is not None else None

    terminal_guard_sql = ""
    if not allow_terminal_override:
        terminal_guard_sql = "AND status NOT IN ('CONFIRMED','FAILED')"

    cur.execute(
        f"""
        UPDATE app.mobile_money_payouts
        SET
          status = %s,
          provider_response =
            COALESCE(provider_response, '{{}}'::jsonb) || COALESCE(%s::jsonb, '{{}}'::jsonb),
          last_error = %s,
          retryable = COALESCE(%s, retryable),
          next_retry_at = %s,
          updated_at = now()
        WHERE provider_ref = %s
        {terminal_guard_sql}
        """,
        (
            new_status,
            resp_json,
            last_error,
            retryable,
            next_retry_at,
            provider_ref,
        ),
    )
    return cur.rowcount == 1


def update_status_by_payout_id_merge(
    conn,
    *,
    payout_id,  # UUID
    new_status: str,
    provider_response: Optional[dict[str, Any]] = None,
    last_error: Optional[str] = None,
    retryable: Optional[bool] = None,
    next_retry_at: Optional[datetime] = None,
    allow_terminal_override: bool = False,
) -> bool:
    """
    Update by payout UUID id and merge provider_response jsonb.
    """
    cur = conn.cursor()
    resp_json = _adapt_json(provider_response) if provider_response is not None else None

    terminal_guard_sql = ""
    if not allow_terminal_override:
        terminal_guard_sql = "AND status NOT IN ('CONFIRMED','FAILED')"

    cur.execute(
        f"""
        UPDATE app.mobile_money_payouts
        SET
          status = %s,
          provider_response =
            COALESCE(provider_response, '{{}}'::jsonb) || COALESCE(%s::jsonb, '{{}}'::jsonb),
          last_error = %s,
          retryable = COALESCE(%s, retryable),
          next_retry_at = %s,
          updated_at = now()
        WHERE id = %s
        {terminal_guard_sql}
        """,
        (
            new_status,
            resp_json,
            last_error,
            retryable,
            next_retry_at,
            payout_id,  # UUID passthrough
        ),
    )
    return cur.rowcount == 1


def update_status_by_any_ref(
    conn,
    *,
    provider_ref: str | None,
    external_ref: str | None,
    new_status: str,
    provider_response: Optional[dict[str, Any]] = None,
    last_error: Optional[str] = None,
    retryable: Optional[bool] = None,
    next_retry_at: Optional[datetime] = None,
    allow_terminal_override: bool = False,
    provider: str | None = None,  # accepted for compatibility, IGNORED
) -> bool:
    """
    Update by provider_ref first; if not updated, try external_ref fallback.

    NOTE: provider param is ignored to allow cross-provider webhook updates.
    """
    if provider_ref:
        ok = update_status_by_provider_ref(
            conn,
            provider_ref=provider_ref,
            new_status=new_status,
            provider_response=provider_response,
            retryable=retryable,
            last_error=last_error,
            next_retry_at=next_retry_at,
            allow_terminal_override=allow_terminal_override,
            provider=provider,  # ignored inside
        )
        if ok:
            return True

    if external_ref:
        payout = get_payout_by_external_ref(conn, external_ref)
        if not payout:
            return False

        return update_status_by_payout_id_merge(
            conn,
            payout_id=payout["id"],
            new_status=new_status,
            provider_response=provider_response,
            retryable=retryable,
            last_error=last_error,
            next_retry_at=next_retry_at,
            allow_terminal_override=allow_terminal_override,
        )

    return False


# ==========================================================
# Reads
# ==========================================================

def get_payout_by_transaction_id(conn, transaction_id: UUID) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            select
              p.id,
              p.transaction_id,
              p.provider,
              p.status,
              p.attempt_count,
              p.retryable,
              p.provider_ref,
              tx.external_ref as external_ref,
              p.request_id,
              p.last_error,
              p.last_attempt_at,
              p.next_retry_at,
              p.provider_response,
              p.created_at,
              p.updated_at
            from app.mobile_money_payouts p
            join ledger.ledger_transactions tx on tx.id = p.transaction_id
            where p.transaction_id = %s
            """,
            (transaction_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_payout_by_provider_ref(conn, provider_ref: str, *, provider: str | None = None) -> dict | None:
    provider_filter = ""
    params = [provider_ref]
    if provider:
        provider_filter = "AND upper(p.provider) = upper(%s)"
        params.append(provider)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            select
              p.id,
              p.transaction_id,
              p.provider_ref,
              p.status,
              p.updated_at
            from app.mobile_money_payouts p
            where p.provider_ref = %s
            {provider_filter}
            order by p.updated_at desc
            limit 1
            """,
            tuple(params),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_payout_by_external_ref(conn, external_ref: str, provider: str | None = None) -> dict | None:
    """
    external_ref lives on ledger.ledger_transactions, so join to find the payout.
    NOTE: provider param accepted for compatibility but intentionally ignored
    (tests expect cross-provider webhook handling).
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            select
              p.id,
              p.transaction_id,
              p.provider_ref,
              p.status,
              tx.external_ref
            from app.mobile_money_payouts p
            join ledger.ledger_transactions tx on tx.id = p.transaction_id
            where tx.external_ref = %s
            order by p.updated_at desc
            limit 1
            """,
            (external_ref,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_payout_by_any_ref(conn, *, provider_ref: str | None, external_ref: str | None, provider: str | None = None) -> dict | None:
    if provider_ref:
        row = get_payout_by_provider_ref(conn, provider_ref, provider=provider)
        if row:
            return row
    if external_ref:
        return get_payout_by_external_ref(conn, external_ref, provider=provider)
    return None
