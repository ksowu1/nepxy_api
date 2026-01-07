

# services/payout_lookup.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from psycopg2.extras import RealDictCursor

from db import get_conn

def find_payout_by_refs(provider: str, provider_ref: str | None, external_ref: str | None) -> Optional[dict]:
    if not provider_ref and not external_ref:
        return None

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                  FROM app.mobile_money_payouts
                 WHERE provider = %s
                   AND (
                        (%s IS NOT NULL AND provider_ref = %s)
                     OR (%s IS NOT NULL AND external_ref = %s)
                   )
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (provider, provider_ref, provider_ref, external_ref, external_ref),
            )
            return cur.fetchone()
