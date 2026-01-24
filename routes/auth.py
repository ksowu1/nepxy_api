


# routes/auth.py
from fastapi import APIRouter, HTTPException, Request
import logging
from pydantic import BaseModel, EmailStr
from uuid import UUID

from db import get_conn
from security import (
    verify_password,
    create_access_token,
    hash_password,
    create_session_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
)
from schemas import RegisterRequest, RegisterResponse
from services.invite_only import is_email_allowed, is_invite_only_enabled
from rate_limit import rate_limit_enabled, rate_limit_login_per_min, rate_limit_or_429

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = logging.getLogger("nexapay.auth")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _enforce_invite_only(email: str) -> None:
    if not is_invite_only_enabled():
        return
    if not is_email_allowed(email):
        raise HTTPException(status_code=403, detail="INVITE_ONLY_EMAIL_NOT_ALLOWED")


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, req: Request):
    if rate_limit_enabled():
        client_ip = req.client.host if req.client else "unknown"
        email_key = str(body.email).strip().lower()
        limit = rate_limit_login_per_min()
        rate_limit_or_429(key=f"login:ip:{client_ip}", limit=limit, window_seconds=60)
        rate_limit_or_429(key=f"login:email:{email_key}", limit=limit, window_seconds=60)
    _enforce_invite_only(body.email)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, password_hash
                FROM users.users
                WHERE email = %s
                LIMIT 1;
                """,
                (body.email,),
            )
            row = cur.fetchone()

    if not row:
        logger.info(
            "auth_login_invalid request_id=%s email=%s",
            getattr(req.state, "request_id", None),
            str(body.email),
        )
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    user_id, password_hash_db = row

    if not verify_password(body.password, password_hash_db):
        logger.info(
            "auth_login_invalid request_id=%s email=%s",
            getattr(req.state, "request_id", None),
            str(body.email),
        )
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    access = create_access_token(sub=str(user_id))
    refresh = create_session_refresh_token(user_id=user_id)
    return LoginResponse(access_token=access, refresh_token=refresh, user_id=user_id)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest, req: Request):
    user_id = validate_refresh_token(body.refresh_token)
    if not user_id:
        logger.info(
            "auth_refresh_invalid request_id=%s",
            getattr(req.state, "request_id", None),
        )
        raise HTTPException(status_code=401, detail="INVALID_REFRESH_TOKEN")

    access = create_access_token(sub=str(user_id))
    revoke_refresh_token(body.refresh_token)
    new_refresh = create_session_refresh_token(user_id=user_id)
    return RefreshResponse(access_token=access, refresh_token=new_refresh)


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest):
    _enforce_invite_only(payload.email)

    pw_hash = hash_password(payload.password)
    full_name = payload.full_name or None

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
                    (payload.email, payload.phone_e164, full_name, payload.country, pw_hash),
                )
                user_id = cur.fetchone()[0]

        return RegisterResponse(user_id=user_id)

    except Exception as e:
        msg = str(e)
        if "DB_ERROR:" in msg:
            clean = msg.split("DB_ERROR:", 1)[1].strip()
            raise HTTPException(status_code=400, detail=clean)
        raise
