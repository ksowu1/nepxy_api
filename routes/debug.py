from __future__ import annotations

import os
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr

from db import get_conn
from deps.auth import get_current_user, CurrentUser
from deps.admin import require_admin
from schemas import WalletInvariantListResponse, WalletInvariantResponse
from security import hash_password
from security import verify_password
from services.ledger_invariants import (
    assert_wallet_balance_matches_ledger,
    list_wallet_balance_invariants,
)


router = APIRouter(prefix="/debug", tags=["debug"])


class BootstrapAdminRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = None


class BootstrapAdminResponse(BaseModel):
    ok: bool
    user_id: UUID
    role: str = "ADMIN"

class BootstrapVerifyRequest(BaseModel):
    email: EmailStr
    password: str


class BootstrapVerifyResponse(BaseModel):
    ok: bool
    db_ok: bool
    self_ok: bool
    user_id: UUID
    prefix: str

class DebugVersionResponse(BaseModel):
    git_sha: str
    env: str
    environment: str
    mm_mode: str


class AuthProbeRequest(BaseModel):
    email: EmailStr
    password: str


class AuthProbeResponse(BaseModel):
    ok: bool
    db_ok: bool
    self_ok: bool
    user_id: UUID
    email: EmailStr
    hash_prefix: str
    hash_len: int
    hash_is_null: bool
    pw_len: int
    pw_strip_changed: bool
    pw_sha12: str
    pw_has_crlf: bool

class BootstrapStagingUserStatus(BaseModel):
    email: EmailStr
    user_id: UUID
    created: bool
    updated: bool
    role: str


class BootstrapStagingUsersResponse(BaseModel):
    ok: bool
    admin: BootstrapStagingUserStatus
    user: BootstrapStagingUserStatus


def _require_dev() -> None:
    if (os.getenv("ENV") or "dev").strip().lower() != "dev":
        raise HTTPException(status_code=404, detail="Not found")


def _bootstrap_allowed() -> bool:
    env = (os.getenv("ENV") or "dev").strip().lower()
    mode = (os.getenv("MM_MODE") or "sandbox").strip().lower()
    return mode == "sandbox" or env in {"dev", "staging"}


def _bootstrap_secret() -> str | None:
    secret = os.getenv("BOOTSTRAP_ADMIN_SECRET")
    return secret.strip() if secret and secret.strip() else None


def _bootstrap_staging_allowed() -> bool:
    env = (os.getenv("ENV") or "").strip().lower()
    env2 = (os.getenv("ENVIRONMENT") or "").strip().lower()
    gate = os.getenv("STAGING_GATE_KEY")
    return env == "staging" or env2 == "staging" or (gate and gate.strip())


def _bootstrap_phone(email: str, attempt: int = 0) -> str:
    seed = f"{email}:{attempt}".encode("utf-8")
    digits = str(int(hashlib.sha1(seed).hexdigest(), 16) % 10_000_000).zfill(7)
    return f"+2332{digits}"

def _normalize_password(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _ensure_user_with_password(
    *,
    cur,
    email: str,
    password: str,
    full_name: str,
    country: str,
) -> tuple[UUID, bool, bool]:
    pw_hash = hash_password(password)
    cur.execute("SELECT id FROM users.users WHERE email = %s LIMIT 1;", (email,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        cur.execute(
            "UPDATE users.users SET password_hash = %s WHERE id = %s;",
            (pw_hash, user_id),
        )
        _sync_optional_auth_credentials(cur, user_id, email, pw_hash)
        return user_id, False, True

    for attempt in range(3):
        phone = _bootstrap_phone(email, attempt)
        try:
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
                (email, phone, full_name, country, pw_hash),
            )
            user_id = cur.fetchone()[0]
            _sync_optional_auth_credentials(cur, user_id, email, pw_hash)
            return user_id, True, False
        except Exception as exc:
            msg = str(exc)
            if "DB_ERROR: PHONE_TAKEN" in msg and attempt < 2:
                continue
            if "DB_ERROR: EMAIL_TAKEN" in msg:
                cur.execute("SELECT id FROM users.users WHERE email = %s LIMIT 1;", (email,))
                row = cur.fetchone()
                if row:
                    user_id = row[0]
                    cur.execute(
                        "UPDATE users.users SET password_hash = %s WHERE id = %s;",
                        (pw_hash, user_id),
                    )
                    _sync_optional_auth_credentials(cur, user_id, email, pw_hash)
                    return user_id, False, True
            raise

    raise HTTPException(status_code=500, detail="Failed to bootstrap user")


def _table_has_column(cur, schema: str, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
        LIMIT 1;
        """,
        (schema, table, column),
    )
    return bool(cur.fetchone())


def _sync_optional_auth_credentials(cur, user_id: UUID, email: str, pw_hash: str) -> None:
    cur.execute("SELECT to_regclass('auth.users');")
    if not cur.fetchone()[0]:
        return

    schema = "auth"
    table = "users"
    if not _table_has_column(cur, schema, table, "email"):
        return

    password_column = None
    for candidate in ("password_hash", "hashed_password", "password"):
        if _table_has_column(cur, schema, table, candidate):
            password_column = candidate
            break
    if not password_column:
        return

    cur.execute(f"SELECT 1 FROM {schema}.{table} WHERE email = %s LIMIT 1;", (email,))
    exists = bool(cur.fetchone())

    if exists:
        cur.execute(
            f"UPDATE {schema}.{table} SET {password_column} = %s WHERE email = %s;",
            (pw_hash, email),
        )
        return

    columns = ["email", password_column]
    values = [email, pw_hash]
    if _table_has_column(cur, schema, table, "id"):
        columns.insert(0, "id")
        values.insert(0, str(user_id))

    cols_sql = ", ".join(columns)
    params_sql = ", ".join(["%s"] * len(columns))
    cur.execute(
        f"INSERT INTO {schema}.{table} ({cols_sql}) VALUES ({params_sql});",
        tuple(values),
    )


@router.get("/me")
def debug_me(user: CurrentUser = Depends(get_current_user)):
    return {"user_id": str(user.user_id)}


@router.get("/invariants/wallet/{wallet_id}", response_model=WalletInvariantResponse)
def debug_wallet_invariant(
    wallet_id: UUID,
    admin: CurrentUser = Depends(require_admin),
):
    _require_dev()
    result = assert_wallet_balance_matches_ledger(wallet_id)
    return WalletInvariantResponse(ok=bool(result["ok"]), wallet=result)


@router.get("/invariants/wallets", response_model=WalletInvariantListResponse)
def debug_wallet_invariants(admin: CurrentUser = Depends(require_admin)):
    _require_dev()
    items = list_wallet_balance_invariants()
    mismatches = sum(1 for item in items if not item["ok"])
    return WalletInvariantListResponse(
        ok=mismatches == 0,
        count=len(items),
        mismatches=mismatches,
        items=items,
    )


@router.post("/bootstrap-admin", response_model=BootstrapAdminResponse)
def debug_bootstrap_admin(
    payload: BootstrapAdminRequest,
    secret: str = Header(..., alias="X-Bootstrap-Secret"),
):
    if not _bootstrap_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    expected = _bootstrap_secret()
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Bad bootstrap secret")

    email = payload.email or os.getenv("ADMIN_EMAIL")
    if not email:
        raise HTTPException(status_code=400, detail="Missing admin email")
    password = _normalize_password(payload.password or os.getenv("ADMIN_PASSWORD"))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users.users WHERE email = %s LIMIT 1;", (email,))
            row = cur.fetchone()

            if row and not password:
                user_id = row[0]
            else:
                if not password:
                    raise HTTPException(status_code=400, detail="Missing admin password")
                user_id, _, _ = _ensure_user_with_password(
                    cur=cur,
                    email=email,
                    password=password,
                    full_name="Bootstrap Admin",
                    country="GH",
                )
            cur.execute(
                """
                INSERT INTO users.user_roles (user_id, role)
                VALUES (%s::uuid, 'ADMIN')
                ON CONFLICT (user_id) DO UPDATE SET role = 'ADMIN';
                """,
                (str(user_id),),
            )
            if password:
                cur.execute(
                    "SELECT password_hash FROM users.users WHERE id = %s LIMIT 1;",
                    (user_id,),
                )
                pw_row = cur.fetchone()
                password_hash_db = pw_row[0] if pw_row else None
                try:
                    ok = bool(password_hash_db) and verify_password(password, password_hash_db)
                except Exception:
                    ok = False
                if not ok:
                    prefix = (password_hash_db or "")[:20]
                    detail = {
                        "detail": "BOOTSTRAP_PASSWORD_VERIFY_FAILED",
                        "email": email,
                        "user_id": str(user_id),
                        "hash_prefix": prefix,
                        "hash_len": len(password_hash_db or ""),
                    }
                    raise HTTPException(status_code=500, detail=detail)
        conn.commit()

    return BootstrapAdminResponse(ok=True, user_id=user_id, role="ADMIN")


@router.post("/bootstrap-verify", response_model=BootstrapVerifyResponse)
def debug_bootstrap_verify(
    payload: BootstrapVerifyRequest,
    secret: str = Header(..., alias="X-Bootstrap-Secret"),
):
    if not _bootstrap_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    expected = _bootstrap_secret()
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Bad bootstrap secret")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash FROM users.users WHERE email = %s LIMIT 1;",
                (payload.email,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_id, password_hash_db = row

    db_ok = verify_password(payload.password, password_hash_db)
    self_ok = verify_password(payload.password, hash_password(payload.password))
    prefix = (password_hash_db or "")[:20]
    return BootstrapVerifyResponse(
        ok=db_ok,
        db_ok=db_ok,
        self_ok=self_ok,
        user_id=user_id,
        prefix=prefix,
    )


@router.get("/version", response_model=DebugVersionResponse)
def debug_version():
    if not _bootstrap_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    git_sha = (
        (os.getenv("FLY_IMAGE_REF") or "").strip()
        or (os.getenv("GIT_SHA") or "").strip()
        or (os.getenv("FLY_APP_NAME") or "").strip()
    )
    return DebugVersionResponse(
        git_sha=git_sha,
        env=(os.getenv("ENV") or "").strip(),
        environment=(os.getenv("ENVIRONMENT") or "").strip(),
        mm_mode=(os.getenv("MM_MODE") or "").strip(),
    )


@router.post("/auth-probe", response_model=AuthProbeResponse)
def debug_auth_probe(
    payload: AuthProbeRequest,
    secret: str = Header(..., alias="X-Bootstrap-Secret"),
):
    if not _bootstrap_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    expected = _bootstrap_secret()
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Bad bootstrap secret")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash FROM users.users WHERE email = %s LIMIT 1;",
                (payload.email,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_id, email, password_hash_db = row

    db_ok = False
    if password_hash_db:
        db_ok = verify_password(payload.password, password_hash_db)

    pw = payload.password
    self_ok = verify_password(pw, hash_password(pw))
    pw_len = len(pw)
    pw_strip_changed = pw != pw.strip()
    pw_sha12 = hashlib.sha256(pw.encode("utf-8")).hexdigest()[:12]
    pw_has_crlf = "\r" in pw or "\n" in pw

    hash_prefix = (password_hash_db or "")[:20]
    hash_len = len(password_hash_db or "")
    return AuthProbeResponse(
        ok=db_ok,
        db_ok=db_ok,
        self_ok=self_ok,
        user_id=user_id,
        email=email,
        hash_prefix=hash_prefix,
        hash_len=hash_len,
        hash_is_null=not bool(password_hash_db),
        pw_len=pw_len,
        pw_strip_changed=pw_strip_changed,
        pw_sha12=pw_sha12,
        pw_has_crlf=pw_has_crlf,
    )


@router.post("/bootstrap-staging-users", response_model=BootstrapStagingUsersResponse)
def debug_bootstrap_staging_users(
    secret: str = Header(..., alias="X-Bootstrap-Admin-Secret"),
):
    if not _bootstrap_staging_allowed():
        raise HTTPException(status_code=404, detail="Not found")

    expected = _bootstrap_secret()
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Bad bootstrap secret")

    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = _normalize_password(os.getenv("ADMIN_PASSWORD"))
    user_email = os.getenv("USER_EMAIL")
    user_password = _normalize_password(os.getenv("USER_PASSWORD"))
    if not admin_email or not admin_password or not user_email or not user_password:
        raise HTTPException(status_code=400, detail="Missing staging credentials")

    with get_conn() as conn:
        with conn.cursor() as cur:
            admin_id, admin_created, admin_updated = _ensure_user_with_password(
                cur=cur,
                email=admin_email,
                password=admin_password,
                full_name="Staging Admin",
                country="GH",
            )
            cur.execute(
                """
                INSERT INTO users.user_roles (user_id, role)
                VALUES (%s::uuid, 'ADMIN')
                ON CONFLICT (user_id) DO UPDATE SET role = 'ADMIN';
                """,
                (str(admin_id),),
            )

            user_id, user_created, user_updated = _ensure_user_with_password(
                cur=cur,
                email=user_email,
                password=user_password,
                full_name="Staging User",
                country="GH",
            )
        conn.commit()

    return BootstrapStagingUsersResponse(
        ok=True,
        admin=BootstrapStagingUserStatus(
            email=admin_email,
            user_id=admin_id,
            created=admin_created,
            updated=admin_updated,
            role="ADMIN",
        ),
        user=BootstrapStagingUserStatus(
            email=user_email,
            user_id=user_id,
            created=user_created,
            updated=user_updated,
            role="USER",
        ),
    )
