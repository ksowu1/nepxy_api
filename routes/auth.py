


# routes/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from uuid import UUID

from db import get_conn
from security import verify_password, create_access_token, hash_password
from schemas import RegisterRequest, RegisterResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
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
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    user_id, password_hash_db = row

    if not verify_password(body.password, password_hash_db):
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

    token = create_access_token(sub=str(user_id))
    return LoginResponse(access_token=token, user_id=user_id)


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest):
    pw_hash = hash_password(payload.password)
    full_name = payload.full_name or None

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT users.register_user_secure(
                      %s::text,            -- email
                      %s::text,            -- phone_e164
                      %s::text,            -- full_name
                      %s::ledger.country_code, -- country enum
                      %s::text             -- password_hash
                    );
                    """,
                    (payload.email, payload.phone_e164, full_name, payload.country, pw_hash),
                )
                user_id = cur.fetchone()[0]

        return RegisterResponse(user_id=user_id)

    except Exception as e:
        msg = str(e)

        # Bubble up DB_ERROR codes as clean 400s
        if "DB_ERROR:" in msg:
            clean = msg.split("DB_ERROR:", 1)[1].strip()
            raise HTTPException(status_code=400, detail=clean)

        raise
