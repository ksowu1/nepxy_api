from __future__ import annotations

from fastapi import APIRouter, Depends

from db import get_conn
from db_session import set_db_actor
from deps.admin import require_admin
from deps.auth import CurrentUser


router = APIRouter(prefix="/v1/admin/support", tags=["admin-support"])


def _like(q: str) -> str:
    return f"%{q}%"


@router.get("/search")
def admin_support_search(q: str, admin: CurrentUser = Depends(require_admin)):
    query = (q or "").strip()
    if not query:
        return {"users": [], "payouts": [], "webhook_events": []}

    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)

            cur.execute(
                """
                SELECT id::text, email, phone_e164, full_name, country, created_at
                FROM users.users
                WHERE email ILIKE %s OR phone_e164 ILIKE %s
                ORDER BY created_at DESC
                LIMIT 25
                """,
                (_like(query), _like(query)),
            )
            users = cur.fetchall()

            cur.execute(
                """
                SELECT
                  p.id::text AS payout_id,
                  p.transaction_id::text AS transaction_id,
                  p.status,
                  p.provider,
                  p.phone_e164,
                  p.provider_ref,
                  p.created_at,
                  tx.external_ref,
                  tx.amount_cents,
                  tx.currency
                FROM app.mobile_money_payouts p
                LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                WHERE p.transaction_id::text = %s
                   OR p.provider_ref ILIKE %s
                   OR p.phone_e164 ILIKE %s
                   OR tx.external_ref ILIKE %s
                ORDER BY p.created_at DESC
                LIMIT 50
                """,
                (query, _like(query), _like(query), _like(query)),
            )
            payouts = cur.fetchall()

            cur.execute(
                """
                SELECT id::text, provider, external_ref, provider_ref, status_raw, received_at
                FROM app.webhook_events
                WHERE external_ref ILIKE %s OR provider_ref ILIKE %s
                ORDER BY received_at DESC
                LIMIT 50
                """,
                (_like(query), _like(query)),
            )
            webhook_events = cur.fetchall()

    return {"users": users, "payouts": payouts, "webhook_events": webhook_events}
