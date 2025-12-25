

# routes/payments.py
# routes/payments.py
from fastapi import APIRouter, Header, HTTPException, Depends
import os

from deps.auth import get_current_user, CurrentUser
from services.ownership import require_wallet_owned_by_user, require_merchant_wallet
from db import get_conn
from settings import settings
from schemas import P2PRequest, MerchantPayRequest, CashInRequest, CashOutRequest, TxnResponse
from db_session import set_db_actor

router = APIRouter(prefix="/v1", tags=["payments"])


def require_idempotency(idempotency_key: str | None) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    if len(idempotency_key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key too long")
    return idempotency_key.strip()


def map_db_error(e: Exception) -> HTTPException:
    msg = str(e)
    pg = getattr(e, "pgerror", "") or ""
    full = (pg + " " + msg).strip()

    # ownership / existence
    if "WALLET_NOT_OWNED" in full:
        return HTTPException(status_code=403, detail="WALLET_NOT_OWNED")
    if "WALLET_NOT_FOUND" in full:
        return HTTPException(status_code=404, detail="WALLET_NOT_FOUND")
    if "MERCHANT_WALLET_NOT_FOUND" in full:
        return HTTPException(status_code=404, detail="MERCHANT_WALLET_NOT_FOUND")
    if "NOT_A_MERCHANT_WALLET" in full:
        return HTTPException(status_code=400, detail="NOT_A_MERCHANT_WALLET")

    # business rules
    if "Insufficient funds" in full:
        return HTTPException(status_code=409, detail="INSUFFICIENT_FUNDS")
    if "Daily send limit exceeded" in full:
        return HTTPException(status_code=409, detail="DAILY_LIMIT_EXCEEDED")
    if "Monthly send limit exceeded" in full:
        return HTTPException(status_code=409, detail="MONTHLY_LIMIT_EXCEEDED")
    if "Daily cashout limit exceeded" in full:
        return HTTPException(status_code=409, detail="DAILY_CASHOUT_LIMIT_EXCEEDED")
    if "No limits configured" in full:
        return HTTPException(status_code=500, detail="LIMITS_NOT_CONFIGURED")

    # ✅ DEV MODE: show the real DB error so you can fix fast
    if getattr(settings, "env", "dev") == "dev":
        return HTTPException(status_code=500, detail=f"DB_ERROR: {full}")

    return HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.post("/cash-in/momo", response_model=TxnResponse)
def cash_in_momo(
    body: CashInRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    # Fast fail (still good), DB enforces too
    require_wallet_owned_by_user(body.user_account_id, user.user_id)

    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # ✅ IMPORTANT: set session actor for DB-level policies
                set_db_actor(cur, user.user_id)

                cur.execute(
                    """
                    SELECT ledger.post_cash_in_momo(
                      %s::uuid, %s::uuid,
                      %s::bigint, %s::ledger.country_code,
                      %s::text, %s::text, %s::uuid
                    );
                    """,
                    (
                        str(body.user_account_id),
                        str(user.user_id),
                        int(body.amount_cents),
                        body.country,
                        idem,
                        body.provider_ref,
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]
        return TxnResponse(transaction_id=txn_id)

    except Exception as e:
        raise map_db_error(e)


@router.post("/cash-out/momo", response_model=TxnResponse)
def cash_out_momo(
    body: CashOutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    require_wallet_owned_by_user(body.user_account_id, user.user_id)
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                cur.execute(
                    """
                    SELECT ledger.post_cash_out_momo(
                      %s::uuid, %s::uuid,
                      %s::bigint, %s::ledger.country_code,
                      %s::text, %s::text, %s::uuid
                    );
                    """,
                    (
                        str(body.user_account_id),
                        str(user.user_id),
                        int(body.amount_cents),
                        body.country,
                        idem,
                        body.provider_ref,
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]
        return TxnResponse(transaction_id=txn_id)

    except Exception as e:
        raise map_db_error(e)
