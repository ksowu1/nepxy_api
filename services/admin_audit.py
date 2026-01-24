from __future__ import annotations

from typing import Any

from psycopg2.extras import Json


def log_admin_event(
    cur,
    *,
    admin_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO audit.admin_events (
            admin_user_id,
            action,
            entity_type,
            entity_id,
            metadata,
            request_id
        )
        VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s);
        """,
        (
            admin_user_id,
            action,
            entity_type,
            entity_id,
            Json(metadata or {}),
            request_id,
        ),
    )
