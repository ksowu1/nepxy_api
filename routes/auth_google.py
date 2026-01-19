

# routes/auth_google.py
from __future__ import annotations

import os
import logging
import secrets
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_conn
from security import create_access_token, create_session_refresh_token, hash_password
from services.invite_only import is_email_allowed, is_invite_only_enabled

# IMPORTANT: keep these imports at MODULE level so pytest can monkeypatch:
#   monkeypatch.setattr(routes.auth_google.google_id_token, "verify_oauth2_token", ...)
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

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
    """
    Preferred: GOOGLE_CLIENT_IDS="id1,id2,id3"
    Fallback: GOOGLE_WEB_CLIENT_ID / GOOGLE_ANDROID_CLIENT_ID / GOOGLE_IOS_CLIENT_ID

    In pytest, if none are configured, we allow audience=None so tests that monkeypatch
    verify_oauth2_token can still drive the 401 path (without failing 500).
    """
    raw = _env("GOOGLE_CLIENT_IDS", "")
    if raw:
        ids = [x.strip() for x in raw.split(",") if x.strip()]
        if ids:
            return ids

    # fallback (common pattern)
    fallbacks = [
        _env("GOOGLE_WEB_CLIENT_ID", ""),
        _env("GOOGLE_ANDROID_CLIENT_ID", ""),
        _env("GOOGLE_IOS_CLIENT_ID", ""),
    ]
    ids = [x for x in fallbacks if x]
    if ids:
        return ids

    # strict in non-test environments
    if not os.getenv("PYTEST_CURRENT_TEST"):
        raise HTTPException(status_code=500, detail="Backend missing Google client IDs configuration.")

    # pytest/dev: return empty list; caller will try aud=None once
    return []


def _verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verifies the Google ID token and returns the claims.

    CRITICAL:
    - do NOT import google_id_token/google_requests inside this function
      (it would bypass monkeypatching in tests)
    - do NOT run verification at import time
    """
    client_ids = _get_google_client_ids()
    req = google_requests.Request()

    # In tests/dev with no configured IDs, run once with audience=None
    audiences: List[Optional[str]] = client_ids if client_ids else [None]

    last_err: Optional[Exception] = None
    for aud in audiences:
        try:
            claims = google_id_token.verify_oauth2_token(id_token_str, req, aud)
            return claims
        except Exception as e:
            last_err = e

    # Keep message stable-ish for tests; don’t leak too much detail.
    raise HTTPException(status_code=401, detail="Invalid Google ID token") from last_err


def _normalize_phone_e164(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    raw = phone.strip().replace(" ", "")
    if not raw:
        return None
    if not raw.startswith("+"):
        raw = "+" + raw
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
        if "DB_ERROR:" in msg:
            clean = msg.split("DB_ERROR:", 1)[1].strip()
            raise HTTPException(status_code=400, detail=clean)
        raise


def _issue_app_tokens(user_id: UUID) -> Dict[str, Any]:
    """
    Use the SAME token issuance functions as /v1/auth/login so get_current_user() accepts it.
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

    if is_invite_only_enabled() and not is_email_allowed(email):
        raise HTTPException(status_code=403, detail="INVITE_ONLY_EMAIL_NOT_ALLOWED")

    user_id = _find_user_id_in_main_users(email)

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
