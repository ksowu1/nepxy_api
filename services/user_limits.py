from __future__ import annotations

import logging

from typing import Any


logger = logging.getLogger("nexapay.limits")


_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app.user_limit_overrides (
  user_id uuid PRIMARY KEY,
  max_cashout_per_day_cents bigint,
  max_cashout_per_month_cents bigint,
  max_cashout_count_per_day integer,
  max_cashout_count_per_month integer,
  max_cashin_per_day_cents bigint,
  max_cashin_per_month_cents bigint,
  max_cashout_count_per_window integer,
  cashout_window_minutes integer,
  max_distinct_receivers_per_day integer,
  updated_at timestamptz NOT NULL DEFAULT now()
);
"""


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_TABLE_SQL)


def get_user_limit_override(conn, user_id: str) -> dict[str, Any]:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  user_id,
                  max_cashout_per_day_cents,
                  max_cashout_per_month_cents,
                  max_cashout_count_per_day,
                  max_cashout_count_per_month,
                  max_cashin_per_day_cents,
                  max_cashin_per_month_cents,
                  max_cashout_count_per_window,
                  cashout_window_minutes,
                  max_distinct_receivers_per_day,
                  updated_at
                FROM app.user_limit_overrides
                WHERE user_id = %s::uuid
                """,
                (str(user_id),),
            )
            row = cur.fetchone()
            if not row:
                return {}
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        logger.warning("user limit override lookup failed: %s", e)
        return {}


def upsert_user_limit_override(conn, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_table(conn)
    fields = [
        "max_cashout_per_day_cents",
        "max_cashout_per_month_cents",
        "max_cashout_count_per_day",
        "max_cashout_count_per_month",
        "max_cashin_per_day_cents",
        "max_cashin_per_month_cents",
        "max_cashout_count_per_window",
        "cashout_window_minutes",
        "max_distinct_receivers_per_day",
    ]
    values = [payload.get(f) for f in fields]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.user_limit_overrides (
              user_id,
              max_cashout_per_day_cents,
              max_cashout_per_month_cents,
              max_cashout_count_per_day,
              max_cashout_count_per_month,
              max_cashin_per_day_cents,
              max_cashin_per_month_cents,
              max_cashout_count_per_window,
              cashout_window_minutes,
              max_distinct_receivers_per_day,
              updated_at
            )
            VALUES (
              %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
            )
            ON CONFLICT (user_id) DO UPDATE
            SET
              max_cashout_per_day_cents = EXCLUDED.max_cashout_per_day_cents,
              max_cashout_per_month_cents = EXCLUDED.max_cashout_per_month_cents,
              max_cashout_count_per_day = EXCLUDED.max_cashout_count_per_day,
              max_cashout_count_per_month = EXCLUDED.max_cashout_count_per_month,
              max_cashin_per_day_cents = EXCLUDED.max_cashin_per_day_cents,
              max_cashin_per_month_cents = EXCLUDED.max_cashin_per_month_cents,
              max_cashout_count_per_window = EXCLUDED.max_cashout_count_per_window,
              cashout_window_minutes = EXCLUDED.cashout_window_minutes,
              max_distinct_receivers_per_day = EXCLUDED.max_distinct_receivers_per_day,
              updated_at = now()
            RETURNING
              user_id,
              max_cashout_per_day_cents,
              max_cashout_per_month_cents,
              max_cashout_count_per_day,
              max_cashout_count_per_month,
              max_cashin_per_day_cents,
              max_cashin_per_month_cents,
              max_cashout_count_per_window,
              cashout_window_minutes,
              max_distinct_receivers_per_day,
              updated_at
            """,
            [str(user_id), *values],
        )
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row)) if row else {}


def clear_user_limit_override(conn, user_id: str) -> None:
    _ensure_table(conn)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM app.user_limit_overrides WHERE user_id = %s::uuid",
            (str(user_id),),
        )
