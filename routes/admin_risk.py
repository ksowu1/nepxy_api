from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg2.extras import RealDictCursor

from db import get_conn
from deps.admin import require_admin


router = APIRouter(prefix="/v1/admin/risk", tags=["admin", "risk"])


@router.get("/summary")
def risk_summary(window_hours: int = Query(24, ge=1, le=168), _admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT reason, COUNT(*)::int AS count
                FROM app.risk_declines
                WHERE created_at >= now() - (%s || ' hours')::interval
                GROUP BY reason
                """,
                (int(window_hours),),
            )
            by_reason = cur.fetchall() or []

            cur.execute(
                """
                SELECT user_id::text AS user_id, COUNT(*)::int AS count
                FROM app.risk_declines
                WHERE created_at >= now() - (%s || ' hours')::interval
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 20
                """,
                (int(window_hours),),
            )
            top_users = cur.fetchall() or []

    return {"window_hours": int(window_hours), "by_reason": by_reason, "top_users": top_users}
