


import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from db import get_conn
from settings import settings


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token() -> str:
    # Long random token, safe to store on device
    return secrets.token_urlsafe(48)


def create_session_refresh_token(user_id: UUID, days: Optional[int] = None) -> str:
    """Creates a DB session row and returns the *raw* refresh token."""
    ttl_days = days or getattr(settings, "JWT_REFRESH_DAYS", 30)
    refresh = create_refresh_token()
    h = _hash_refresh(refresh)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=ttl_days)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO auth.user_sessions (user_id, refresh_token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (str(user_id), h, expires),
            )
        conn.commit()

    return refresh


def validate_refresh_token(refresh_token: str) -> Optional[UUID]:
    """Returns user_id if valid, else None."""
    h = _hash_refresh(refresh_token)
    now = datetime.now(timezone.utc)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id
                FROM auth.user_sessions
                WHERE refresh_token_hash = %s
                  AND revoked_at IS NULL
                  AND expires_at > %s
                LIMIT 1
                """,
                (h, now),
            )
            row = cur.fetchone()

        if row:
            user_id = row[0]
            with conn.cursor() as cur2:
                cur2.execute(
                    "UPDATE auth.user_sessions SET last_used_at = now() WHERE refresh_token_hash = %s",
                    (h,),
                )
            conn.commit()
            return user_id

    return None
