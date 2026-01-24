from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from psycopg2.extras import RealDictCursor

from db import get_conn
from deps.admin import require_admin

router = APIRouter(prefix="/v1/admin", tags=["admin_audit"])


@router.get("/audit-events")
def list_admin_audit_events(
    limit: int = Query(50, ge=1, le=200),
    entity_id: str | None = Query(None),
    _admin=Depends(require_admin),
):
    where = []
    params: list[Any] = []

    if entity_id:
        where.append("entity_id = %s")
        params.append(entity_id.strip())

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT
          id::text AS id,
          created_at,
          admin_user_id::text AS admin_user_id,
          action,
          entity_type,
          entity_id,
          metadata,
          request_id
        FROM audit.admin_events
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []

    events = []
    for row in rows:
        events.append(
            {
                "id": row["id"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "admin_user_id": row["admin_user_id"],
                "action": row["action"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "metadata": row.get("metadata") or {},
                "request_id": row.get("request_id"),
            }
        )

    return {"events": events, "count": len(events), "limit": limit}
