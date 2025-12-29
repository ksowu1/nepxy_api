

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import hashlib
import secrets
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext

from settings import settings
from db import get_conn

pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256"],
    deprecated="auto",
)

# -----------------------
# Password hashing
# -----------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

# -----------------------
# Access tokens (JWT)
# -----------------------
def create_access_token(sub: str, minutes: Optional[int] = None) -> str:
    exp_minutes = minutes or settings.JWT_ACCESS_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError:
        return {}

# -----------------------
# Refresh token sessions
# -----------------------
def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def create_session_refresh_token(user_id: UUID, days: Optional[int] = None) -> str:
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

        if not row:
            return None

        user_id = row[0]
        with conn.cursor() as cur2:
            cur2.execute(
                "UPDATE auth.user_sessions SET last_used_at = now() WHERE refresh_token_hash = %s",
                (h,),
            )
        conn.commit()

        return user_id
