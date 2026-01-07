

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
)
from services.db_errors import raise_http_from_db_error

router = APIRouter(prefix="/v1", tags=["payments"])


def require_idempotency(idempotency_key: str | None) -> str:
    """
    Consistent API rule:
      - missing/blank idempotency => 409
      - too long => 400
    """
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
    key = idempotency_key.strip()
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key too long")
    return key


# -------------------------------------------------------------------
# MOBILE MONEY GENERIC (MOMO / TMONEY / FLOOZ)
# -------------------------------------------------------------------

@router.post("/cash-in/mobile-money", response_model=TxnResponse)
def cash_in_mobile_money(
    body: CashInRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                cur.execute(
                    """
                    SELECT ledger.post_cash_in_mobile_money(
                      %s::uuid, %s::uuid,
                      %s::bigint, %s::ledger.country_code,
                      %s::text, %s::text,
                      %s::text, %s::text, %s::uuid
                    );
                    """,
                    (
                        str(body.wallet_id),
                        str(user.user_id),
                        int(body.amount_cents),
                        body.country,
                        idem,
                        body.provider_ref,
                        body.provider.value,     # MOMO/TMONEY/FLOOZ
                        body.phone_e164,         # optional
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


@router.post("/cash-out/mobile-money", response_model=TxnResponse)
def cash_out_mobile_money(
    body: CashOutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                cur.execute(
                    """
                    SELECT ledger.post_cash_out_mobile_money(
                      %s::uuid, %s::uuid,
                      %s::bigint, %s::ledger.country_code,
                      %s::text, %s::text,
                      %s::text, %s::text, %s::uuid
                    );
                    """,
                    (
                        str(body.wallet_id),
                        str(user.user_id),
                        int(body.amount_cents),
                        body.country,
                        idem,
                        body.provider_ref,
                        body.provider.value,     # MOMO/TMONEY/FLOOZ
                        body.phone_e164,         # optional
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


# -------------------------------------------------------------------
# MERCHANT PAY (unchanged)
# -------------------------------------------------------------------
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
