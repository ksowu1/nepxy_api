from __future__ import annotations

from db import get_conn


def test_cashout_limits_seeded():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT kyc_tier, daily_cashout_cents
                FROM limits.account_limits
                WHERE kyc_tier IN (1, 2);
                """
            )
            rows = {row[0]: row[1] for row in cur.fetchall()}

    assert rows.get(1, 0) > 0, "Missing cashout limit for KYC tier 1"
    assert rows.get(2, 0) > 0, "Missing cashout limit for KYC tier 2"
