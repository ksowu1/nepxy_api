

# routes/auth_google.py
from __future__ import annotations

import os
import uuid
import logging
import secrets
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_conn
from security import create_access_token, create_session_refresh_token, hash_password

logger = logging.getLogger("nexapay")

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    id_token: str
    phone_e164: Optional[str] = None
    country: Optional[str] = None  # expects 2-letter like "TG", "BJ", etc.
    full_name: Optional[str] = None


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) else default


def _get_google_client_ids() -> List[str]:
    raw = _env("GOOGLE_CLIENT_IDS", "")
    if not raw:
        raise HTTPException(status_code=500, detail="Backend missing GOOGLE_CLIENT_IDS env var.")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifies the Google ID token and returns the claims.
    Requires google-auth installed.
    """
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"google-auth not installed/available: {e}")

    client_ids = _get_google_client_ids()
    req = google_requests.Request()

    last_err = None
    for aud in client_ids:
        try:
            claims = google_id_token.verify_oauth2_token(id_token, req, aud)
            return claims
        except Exception as e:
            last_err = e

    raise HTTPException(status_code=401, detail=f"Invalid Google token (audience mismatch). {last_err}")


def _normalize_phone_e164(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    raw = phone.strip().replace(" ", "")
    if not raw:
        return None
    # minimal normalization: ensure starts with '+'
    if not raw.startswith("+"):
        raw = "+" + raw
    # keep only + and digits
    cleaned = []
    for ch in raw:
        if ch == "+" or ch.isdigit():
            cleaned.append(ch)
    out = "".join(cleaned)
    if out == "+":
        return None
    return out


def _normalize_country(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    c = country.strip().upper()
    if len(c) != 2:
        return None
    return c


def _find_user_id_in_main_users(email: str) -> Optional[UUID]:
    """
    Main app users table is users.users (as used by /v1/auth/login).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM users.users
                WHERE email = %s
                LIMIT 1;
                """,
                (email,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def _register_google_user_in_main_users(
    *, email: str, phone_e164: str, full_name: Optional[str], country: str
) -> UUID:
    """
    Creates a real user in users.users via your existing secure function, so:
    - wallet ownership works
    - refresh sessions (auth.user_sessions) FK works
    - account is unified by email
    """
    # Google users don't have a password; we generate a random one and store its hash.
    random_pw = secrets.token_urlsafe(48)
    pw_hash = hash_password(random_pw)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT users.register_user_secure(
                      %s::text,
                      %s::text,
                      %s::text,
                      %s::ledger.country_code,
                      %s::text
                    );
                    """,
                    (email, phone_e164, full_name, country, pw_hash),
                )
                user_id = cur.fetchone()[0]
            conn.commit()
        return user_id
    except Exception as e:
        msg = str(e)
        # mirror your /register behavior
        if "DB_ERROR:" in msg:
            clean = msg.split("DB_ERROR:", 1)[1].strip()
            raise HTTPException(status_code=400, detail=clean)
        raise


def _issue_app_tokens(user_id: UUID) -> Dict[str, Any]:
    """
    CRITICAL: Use the SAME token issuance functions as /v1/auth/login.
    This guarantees get_current_user() will accept it.
    Refresh token is a DB-backed session token (not a JWT).
    """
    access = create_access_token(sub=str(user_id))
    refresh = create_session_refresh_token(user_id=user_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user_id": str(user_id),
    }


@router.post("/google")
def google_login(req: GoogleAuthRequest):
    claims = _verify_google_id_token(req.id_token)

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google token missing email.")

    # Optional but recommended
    if claims.get("email_verified") is False:
        raise HTTPException(status_code=401, detail="Google email not verified.")

    # 1) If user already exists in main users table, use it (unifies accounts by email)
    user_id = _find_user_id_in_main_users(email)

    # 2) If not, require minimal onboarding fields to create real app user
    if not user_id:
        phone = _normalize_phone_e164(req.phone_e164)
        country = _normalize_country(req.country)
        full_name = (req.full_name or claims.get("name") or "").strip() or None

        missing = []
        if not phone:
            missing.append("phone_e164")
        if not country:
            missing.append("country")

        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ONBOARDING_REQUIRED",
                    "missing": missing,
                    "message": "First-time Google sign-in requires phone_e164 and country to create your NepXy account.",
                    "email": email,
                },
            )

        user_id = _register_google_user_in_main_users(
            email=email,
            phone_e164=phone,
            full_name=full_name,
            country=country,
        )

    tokens = _issue_app_tokens(user_id)

    logger.info(
        "GOOGLE_LOGIN ok email=%s user_id=%s access_prefix=%s",
        email,
        str(user_id),
        (tokens.get("access_token") or "")[:12],
    )

    return tokens
