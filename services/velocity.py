from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from settings import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enabled(value: Optional[int]) -> bool:
    try:
        return int(value or 0) > 0
    except Exception:
        return False


def _raise_limit() -> None:
    raise HTTPException(status_code=429, detail="VELOCITY_LIMIT_EXCEEDED")


def check_cash_out_velocity(conn, *, user_id: str, amount_cents: int, phone_e164: str | None) -> None:
    since = _now() - timedelta(hours=24)
    max_count = int(getattr(settings, "MAX_CASHOUT_COUNT_PER_DAY", 0) or 0)
    max_amount = int(getattr(settings, "MAX_CASHOUT_PER_DAY_CENTS", 0) or 0)
    max_receivers = int(getattr(settings, "MAX_DISTINCT_RECEIVERS_PER_DAY", 0) or 0)

    with conn.cursor() as cur:
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
                    _raise_limit()


def check_cash_in_velocity(conn, *, user_id: str, amount_cents: int) -> None:
    max_amount = int(getattr(settings, "MAX_CASHIN_PER_DAY_CENTS", 0) or 0)
    if not _enabled(max_amount):
        return

    since = _now() - timedelta(hours=24)
    with conn.cursor() as cur:
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
            _raise_limit()
