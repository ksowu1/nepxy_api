

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from settings import settings
import psycopg2.extras
_pool: SimpleConnectionPool | None = None


def init_pool():
    """
    Initialize the PostgreSQL connection pool.
    Called once at app startup.
    """
    psycopg2.extras.register_uuid()
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.DATABASE_URL,
            connect_timeout=5,
        )


def close_pool():
    """
    Gracefully close all pooled connections.
    """
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    """
    Provides a transactional DB connection.
    Auto-commits on success, rolls back on error.
    """
    if _pool is None:
        init_pool()

    conn = _pool.getconn()

    try:
        # Safety: never allow long-running queries
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5000ms';")
            cur.execute("SET idle_in_transaction_session_timeout = '5000ms';")
            cur.execute("SET application_name = 'nexapay_api';")

        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        _pool.putconn(conn)
