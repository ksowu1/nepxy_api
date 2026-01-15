from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from db import get_conn
from deps.admin import require_admin
from db_session import set_db_actor
from deps.auth import CurrentUser


router = APIRouter(prefix="/v1/admin/reconcile", tags=["admin-reconcile"])


@router.get("/reports")
def list_reconcile_reports(limit: int = 20, admin: CurrentUser = Depends(require_admin)):
    limit = max(1, min(limit, 200))
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute(
                """
                SELECT id::text, run_at, summary, items
                FROM app.reconcile_reports
                ORDER BY run_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return {"reports": rows, "count": len(rows), "limit": limit}


@router.get("/reports/{report_id}")
def get_reconcile_report(report_id: str, admin: CurrentUser = Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, admin.user_id)
            cur.execute(
                """
                SELECT id::text, run_at, summary, items
                FROM app.reconcile_reports
                WHERE id = %s::uuid
                """,
                (report_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    return row
