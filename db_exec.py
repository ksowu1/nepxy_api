

# db_exec.py
from __future__ import annotations

from typing import Any, Optional, Sequence

from psycopg2.extensions import connection as Connection

from db import get_conn
from services.db_errors import raise_http_from_db_error


def db_fetchone(conn: Connection, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[tuple]:
    """
    Execute on the provided connection (important: preserves app.user_id session var).
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    except Exception as e:
        raise_http_from_db_error(e)
        raise


def db_fetchall(conn: Connection, sql: str, params: Optional[Sequence[Any]] = None) -> list[tuple]:
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    except Exception as e:
        raise_http_from_db_error(e)
        raise


def db_execute(conn: Connection, sql: str, params: Optional[Sequence[Any]] = None) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
    except Exception as e:
        raise_http_from_db_error(e)
        raise


# optional convenience versions that open their own connection (DON'T use for secure actor-based calls)
def db_fetchone_newconn(sql: str, params: Optional[Sequence[Any]] = None) -> Optional[tuple]:
    with get_conn() as conn:
        return db_fetchone(conn, sql, params)


def db_fetchall_newconn(sql: str, params: Optional[Sequence[Any]] = None) -> list[tuple]:
    with get_conn() as conn:
        return db_fetchall(conn, sql, params)
