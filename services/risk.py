from __future__ import annotations

import logging
from uuid import uuid4

logger = logging.getLogger("nexapay.risk")


_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app.risk_declines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  reason text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        cur.execute(_TABLE_SQL)


def log_decline(conn, *, user_id: str, reason: str) -> None:
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app.risk_declines (id, user_id, reason, created_at)
                VALUES (%s::uuid, %s::uuid, %s, now())
                """,
                (str(uuid4()), str(user_id), reason),
            )
    except Exception as exc:
        logger.warning("risk decline log failed: %s", exc)
