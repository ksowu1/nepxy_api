from __future__ import annotations

from typing import Any
from psycopg2.extras import Json


def write_audit_log(
    conn,
    *,
    actor_user_id: str,
    action: str,
    target_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.audit_log (actor_user_id, action, target_id, metadata)
            VALUES (%s::uuid, %s, %s, %s::jsonb);
            """,
            (
                actor_user_id,
                action,
                target_id,
                Json(metadata or {}),
            ),
        )
