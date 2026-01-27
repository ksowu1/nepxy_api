from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from settings import settings
from services.user_limits import get_user_limit_override
from services.risk import log_decline


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_start(ts: datetime) -> datetime:
    return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _enabled(value: Optional[int]) -> bool:
    try:
        return int(value or 0) > 0
    except Exception:
        return False


def _raise_limit(detail: str = "VELOCITY_LIMIT_EXCEEDED") -> None:
    raise HTTPException(status_code=429, detail=detail)


def check_cash_out_velocity(conn, *, user_id: str, amount_cents: int, phone_e164: str | None) -> None:
    now = _now()
    since = now - timedelta(hours=24)
    month_start = _month_start(now)
    overrides = get_user_limit_override(conn, user_id) or {}

    max_count = overrides.get("max_cashout_count_per_day")
    if max_count is None:
        max_count = getattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 0)

    max_amount = overrides.get("max_cashout_per_day_cents")
    if max_amount is None:
        max_amount = getattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0)

    max_receivers = overrides.get("max_distinct_receivers_per_day")
    if max_receivers is None:
        max_receivers = getattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0)

    max_count_month = overrides.get("max_cashout_count_per_month")
    if max_count_month is None:
        max_count_month = getattr(settings, "MAX_CASHOUT_COUNT_PER_MONTH", 0)

    max_amount_month = overrides.get("max_cashout_per_month_cents")
    if max_amount_month is None:
        max_amount_month = getattr(settings, "MAX_CASHOUT_PER_MONTH_CENTS", 0)

    window_count = overrides.get("max_cashout_count_per_window")
    if window_count is None:
        window_count = getattr(settings, "MAX_CASHOUT_COUNT_PER_WINDOW", 0)

    window_minutes = overrides.get("cashout_window_minutes")
    if window_minutes is None:
        window_minutes = getattr(settings, "CASHOUT_WINDOW_MINUTES", 0)

    with conn.cursor() as cur:
        if _enabled(window_count) and _enabled(window_minutes):
            window_since = now - timedelta(minutes=int(window_minutes))
            cur.execute(
                """
                SELECT COUNT(*)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHOUT'
                  AND created_at >= %s
                """,
                (user_id, window_since),
            )
            count = int(cur.fetchone()[0] or 0)
            if count >= int(window_count):
                log_decline(conn, user_id=user_id, reason="VELOCITY")
                _raise_limit("CASHOUT_VELOCITY_WINDOW_EXCEEDED")

        if _enabled(max_count):
            cur.execute(
                """
                SELECT COUNT(*)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHOUT'
                  AND created_at >= %s
                """,
                (user_id, since),
            )
            count = int(cur.fetchone()[0] or 0)
            if count >= max_count:
                log_decline(conn, user_id=user_id, reason="LIMIT_DAILY")
                _raise_limit()

        if _enabled(max_count_month):
            cur.execute(
                """
                SELECT COUNT(*)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHOUT'
                  AND created_at >= %s
                """,
                (user_id, month_start),
            )
            count = int(cur.fetchone()[0] or 0)
            if count >= max_count_month:
                log_decline(conn, user_id=user_id, reason="LIMIT_MONTHLY")
                _raise_limit()

        if _enabled(max_amount):
            cur.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHOUT'
                  AND created_at >= %s
                """,
                (user_id, since),
            )
            total = int(cur.fetchone()[0] or 0)
            if total + int(amount_cents) > max_amount:
                log_decline(conn, user_id=user_id, reason="LIMIT_DAILY")
                _raise_limit()

        if _enabled(max_amount_month):
            cur.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHOUT'
                  AND created_at >= %s
                """,
                (user_id, month_start),
            )
            total = int(cur.fetchone()[0] or 0)
            if total + int(amount_cents) > max_amount_month:
                log_decline(conn, user_id=user_id, reason="LIMIT_MONTHLY")
                _raise_limit()

        if _enabled(max_receivers) and phone_e164:
            cur.execute(
                """
                SELECT 1
                FROM app.mobile_money_payouts p
                JOIN ledger.ledger_transactions t ON t.id = p.transaction_id
                WHERE t.created_by = %s::uuid
                  AND t.type = 'CASHOUT'
                  AND p.created_at >= %s
                  AND p.phone_e164 = %s
                LIMIT 1
                """,
                (user_id, since, phone_e164),
            )
            already_used = cur.fetchone() is not None

            if not already_used:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT p.phone_e164)
                    FROM app.mobile_money_payouts p
                    JOIN ledger.ledger_transactions t ON t.id = p.transaction_id
                    WHERE t.created_by = %s::uuid
                      AND t.type = 'CASHOUT'
                      AND p.created_at >= %s
                      AND p.phone_e164 IS NOT NULL
                      AND p.phone_e164 <> ''
                    """,
                    (user_id, since),
                )
                distinct_count = int(cur.fetchone()[0] or 0)
                if distinct_count >= max_receivers:
                    log_decline(conn, user_id=user_id, reason="LIMIT_DAILY")
                    _raise_limit()


def check_cash_in_velocity(conn, *, user_id: str, amount_cents: int) -> None:
    now = _now()
    since = now - timedelta(hours=24)
    month_start = _month_start(now)
    overrides = get_user_limit_override(conn, user_id) or {}

    max_amount = overrides.get("max_cashin_per_day_cents")
    if max_amount is None:
        max_amount = getattr(settings, "MAX_CASHIN_PER_DAY_CENTS", 0)

    max_amount_month = overrides.get("max_cashin_per_month_cents")
    if max_amount_month is None:
        max_amount_month = getattr(settings, "MAX_CASHIN_PER_MONTH_CENTS", 0)

    if not _enabled(max_amount):
        if not _enabled(max_amount_month):
            return

    with conn.cursor() as cur:
        if _enabled(max_amount):
            cur.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHIN'
                  AND created_at >= %s
                """,
                (user_id, since),
            )
            total = int(cur.fetchone()[0] or 0)
            if total + int(amount_cents) > max_amount:
                log_decline(conn, user_id=user_id, reason="LIMIT_DAILY")
                _raise_limit()

        if _enabled(max_amount_month):
            cur.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM ledger.ledger_transactions
                WHERE created_by = %s::uuid
                  AND type = 'CASHIN'
                  AND created_at >= %s
                """,
                (user_id, month_start),
            )
            total = int(cur.fetchone()[0] or 0)
            if total + int(amount_cents) > max_amount_month:
                log_decline(conn, user_id=user_id, reason="LIMIT_MONTHLY")
                _raise_limit()
