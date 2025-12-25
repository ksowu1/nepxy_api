
# routes/payments.py
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Depends

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from settings import settings
from schemas import (
    TxnResponse,
    MerchantPayRequest,
    CashInRequest,
    CashOutRequest,
    P2PTransferRequest,  # ✅ use your current schema (from_wallet_id/to_wallet_id)
)
from services.db_errors import raise_http_from_db_error  # ✅ centralized mapper

router = APIRouter(prefix="/v1", tags=["payments"])


def require_idempotency(idempotency_key: str | None) -> str:
    # Keep behavior consistent with rest of API:
    # - empty/blank => conflict (same as your other routes)
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
    key = idempotency_key.strip()
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key too long")
    return key


@router.post("/cash-in/momo", response_model=TxnResponse)
def cash_in_momo(
    body: CashInRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                # NOTE: adjust function/schema name if your DB uses rails.* instead of ledger.*
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
                        body.provider_ref,
                        idem,
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]

        return TxnResponse(transaction_id=txn_id)

    except HTTPException:
        raise
    except Exception as e:
        raise_http_from_db_error(e)
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/cash-out/momo", response_model=TxnResponse)
def cash_out_momo(
    body: CashOutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                # NOTE: adjust function/schema name if your DB uses rails.* instead of ledger.*
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
                        body.provider_ref,
                        idem,
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]

        return TxnResponse(transaction_id=txn_id)

    except HTTPException:
        raise
    except Exception as e:
        raise_http_from_db_error(e)
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/merchant/pay", response_model=TxnResponse)
def merchant_pay(
    body: MerchantPayRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                # NOTE: change this call to whatever your DB function is named
                cur.execute(
                    """
                    SELECT ledger.post_merchant_payment(
                      %s::uuid, %s::uuid,
                      %s::uuid, %s::bigint,
                      %s::ledger.country_code,
                      %s::text, %s::text, %s::uuid
                    );
                    """,
                    (
                        str(body.payer_account_id),
                        str(user.user_id),
                        str(body.merchant_account_id),
                        int(body.amount_cents),
                        body.country,
                        idem,
                        body.note or None,
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]

        return TxnResponse(transaction_id=txn_id)

    except HTTPException:
        raise
    except Exception as e:
        raise_http_from_db_error(e)
        raise HTTPException(status_code=500, detail="Database error")
