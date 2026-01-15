from __future__ import annotations

import json
import hashlib
from typing import Any

from psycopg2.extensions import connection as PGConn


def request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_idempotency(
    conn: PGConn,
    *,
    user_id: str,
    idempotency_key: str,
    route_key: str,
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT request_hash, response_json, status_code
            FROM app.idempotency_keys
            WHERE user_id = %s::uuid
              AND idempotency_key = %s
              AND route_key = %s
            LIMIT 1
            """,
            (user_id, idempotency_key, route_key),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"request_hash": row[0], "response_json": row[1], "status_code": row[2]}


def idempotency_conflict(
    conn: PGConn,
    *,
    user_id: str,
    idempotency_key: str,
    route_key: str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM app.idempotency_keys
            WHERE user_id = %s::uuid
              AND idempotency_key = %s
              AND route_key <> %s
            LIMIT 1
            """,
            (user_id, idempotency_key, route_key),
        )
        return cur.fetchone() is not None


def store_idempotency(
    conn: PGConn,
    *,
    user_id: str,
    idempotency_key: str,
    route_key: str,
    request_hash_value: str,
    response_json: dict[str, Any],
    status_code: int = 200,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.idempotency_keys (
              user_id, idempotency_key, route_key,
              request_hash, response_json, status_code
            )
            VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (user_id, idempotency_key, route_key) DO NOTHING
            """,
            (
                user_id,
                idempotency_key,
                route_key,
                request_hash_value,
                json.dumps(response_json, default=str),
                int(status_code),
            ),
        )
    return get_idempotency(
        conn,
        user_id=user_id,
        idempotency_key=idempotency_key,
        route_key=route_key,
    ) or {"request_hash": request_hash_value, "response_json": response_json, "status_code": status_code}
