from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr

from db import get_conn
from deps.auth import get_current_user, CurrentUser
from deps.admin import require_admin
from schemas import WalletInvariantListResponse, WalletInvariantResponse
from services.ledger_invariants import (
    assert_wallet_balance_matches_ledger,
    list_wallet_balance_invariants,
)


router = APIRouter(prefix="/debug", tags=["debug"])


class BootstrapAdminRequest(BaseModel):
    email: EmailStr | None = None


class BootstrapAdminResponse(BaseModel):
    ok: bool
    user_id: UUID
    role: str = "ADMIN"


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

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users.users WHERE email = %s LIMIT 1;", (email,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_id = row[0]
            cur.execute(
                """
                INSERT INTO users.user_roles (user_id, role)
                VALUES (%s::uuid, 'ADMIN')
                ON CONFLICT (user_id) DO UPDATE SET role = 'ADMIN';
                """,
                (str(user_id),),
            )
        conn.commit()

    return BootstrapAdminResponse(ok=True, user_id=user_id, role="ADMIN")
