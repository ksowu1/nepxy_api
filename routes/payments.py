

# routes/payments.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from psycopg2.extras import Json as Psycopg2Json

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from settings import settings, FX_STATIC_RATES
from schemas import (
    TxnResponse,
    CashOutResponse,
    MerchantPayRequest,
    CashInRequest,
    CashOutRequest,
)
from services.corridors import validate_cash_out_corridor, CURRENCY_RULES
from services.db_errors import raise_http_from_db_error
from services.idempotency import get_idempotency, store_idempotency, request_hash, idempotency_conflict
from services.metrics import increment_idempotency_replay
from services.velocity import check_cash_in_velocity, check_cash_out_velocity

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
    provider_ref = body.provider_ref or str(uuid.uuid4())
    route_key = "cash_in_mobile_money"
    req_hash = request_hash(body.model_dump())

    try:
        with get_conn() as conn:
            cached = get_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            )
            if cached:
                if cached.get("request_hash") and cached["request_hash"] != req_hash:
                    raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
                increment_idempotency_replay(route_key)
                return JSONResponse(status_code=cached["status_code"], content=cached["response_json"])
            if idempotency_conflict(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            ):
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

            check_cash_in_velocity(
                conn,
                user_id=str(user.user_id),
                amount_cents=int(body.amount_cents),
            )

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
                        provider_ref,
                        body.provider.value,     # MOMO/TMONEY/FLOOZ
                        body.phone_e164,         # optional
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]

            resp = {"transaction_id": txn_id}
            store_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
                request_hash_value=req_hash,
                response_json=resp,
                status_code=200,
            )

        return TxnResponse(transaction_id=txn_id)

    except HTTPException:
        raise
    except Exception as e:
        raise_http_from_db_error(e)
        raise HTTPException(status_code=500, detail="Database error")


def _cashout_fee_cents(cur, txn_id: str) -> int:
    cur.execute(
        """
        SELECT COALESCE(SUM(e.amount_cents), 0)
        FROM ledger.ledger_entries e
        WHERE e.transaction_id = %s::uuid
          AND e.memo = 'Cashout fee'
        """,
        (txn_id,),
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _cashout_fx_quote(
    cur,
    amount_cents: int,
    country: str,
    provider: str,
    fee_cents: int,
) -> dict:
    payout_currency = CURRENCY_RULES.get(country.upper(), {}).get("payout")
    fx_rate = None
    receive_amount_minor = None

    if payout_currency:
        cur.execute("SAVEPOINT fx_quote;")
        try:
            cur.execute(
                "SELECT * FROM fx.issue_fx_quote_secure(%s::text, %s::text, %s::bigint);",
                ("USD", payout_currency, int(amount_cents)),
            )
            row = cur.fetchone()
            if row:
                fx_rate = str(row[1])
                receive_amount_minor = int(row[3])
            cur.execute("RELEASE SAVEPOINT fx_quote;")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT fx_quote;")
            cur.execute("RELEASE SAVEPOINT fx_quote;")
            rate = FX_STATIC_RATES.get(("USD", payout_currency))
            if rate is not None:
                fx_rate = str(rate)
                receive_amount_minor = int(round(int(amount_cents) * float(rate)))

    if fx_rate is None or receive_amount_minor is None:
        fx_rate = "1"
        receive_amount_minor = int(amount_cents)

    corridor = f"US->{country.upper()}"
    quote_provider = "THUNES" if provider.upper() == "THUNES" else "DIRECT"

    return {
        "send_amount_cents": int(amount_cents),
        "fee_cents": int(fee_cents),
        "fx_rate": str(fx_rate),
        "receive_amount_minor": int(receive_amount_minor),
        "corridor": corridor,
        "provider": quote_provider,
    }


@router.post("/cash-out/mobile-money", response_model=CashOutResponse, response_model_exclude_none=True)
def cash_out_mobile_money(
    body: CashOutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    idem = require_idempotency(idempotency_key)
    provider_ref = body.provider_ref or str(uuid.uuid4())
    route_key = "cash_out_mobile_money"
    req_hash = request_hash(body.model_dump())
    validate_cash_out_corridor(body.country, body.provider.value)

    try:
        with get_conn() as conn:
            cached = get_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            )
            if cached:
                if cached.get("request_hash") and cached["request_hash"] != req_hash:
                    raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
                increment_idempotency_replay(route_key)
                return JSONResponse(status_code=cached["status_code"], content=cached["response_json"])
            if idempotency_conflict(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            ):
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

            check_cash_out_velocity(
                conn,
                user_id=str(user.user_id),
                amount_cents=int(body.amount_cents),
                phone_e164=body.phone_e164,
            )

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
                        provider_ref,
                        body.provider.value,     # MOMO/TMONEY/FLOOZ
                        body.phone_e164,         # optional
                        str(settings.SYSTEM_OWNER_ID),
                    ),
                )
                txn_id = cur.fetchone()[0]

                fee_cents = _cashout_fee_cents(cur, str(txn_id))
                quote = _cashout_fx_quote(
                    cur,
                    amount_cents=int(body.amount_cents),
                    country=body.country,
                    provider=body.provider.value,
                    fee_cents=fee_cents,
                )

                cur.execute(
                    """
                    SELECT external_ref
                    FROM ledger.ledger_transactions
                    WHERE id = %s::uuid
                    """,
                    (str(txn_id),),
                )
                tx_row = cur.fetchone()
                external_ref = tx_row[0] if tx_row and tx_row[0] else f"ext-{txn_id}"

                cur.execute(
                    """
                    INSERT INTO app.mobile_money_payouts (
                      transaction_id, provider, phone_e164, provider_ref,
                      status, amount_cents, currency,
                      last_error, attempt_count, last_attempt_at, next_retry_at, retryable, provider_response,
                      quote,
                      created_at, updated_at
                    )
                    VALUES (
                      %s::uuid, %s, %s, %s,
                      'PENDING', %s, %s,
                      NULL, 0, NULL, NULL, TRUE, NULL,
                      %s::jsonb,
                      now(), now()
                    )
                    ON CONFLICT (transaction_id) DO UPDATE
                    SET quote = COALESCE(app.mobile_money_payouts.quote, EXCLUDED.quote)
                    """,
                    (
                        str(txn_id),
                        body.provider.value,
                        body.phone_e164,
                        provider_ref,
                        int(body.amount_cents),
                        "XOF",
                        Psycopg2Json(quote),
                    ),
                )

            conn.commit()

            resp = {
                "transaction_id": txn_id,
                "external_ref": external_ref,
                "fee_cents": quote.get("fee_cents") if quote else None,
                "fx_rate": quote.get("fx_rate") if quote else None,
                "receive_amount_minor": quote.get("receive_amount_minor") if quote else None,
                "corridor": quote.get("corridor") if quote else None,
            }
            store_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
                request_hash_value=req_hash,
                response_json=resp,
                status_code=200,
            )

        return CashOutResponse(**resp)

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
    route_key = "merchant_pay"
    req_hash = request_hash(body.model_dump())

    try:
        with get_conn() as conn:
            cached = get_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            )
            if cached:
                if cached.get("request_hash") and cached["request_hash"] != req_hash:
                    raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
                increment_idempotency_replay(route_key)
                return JSONResponse(status_code=cached["status_code"], content=cached["response_json"])
            if idempotency_conflict(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
            ):
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

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

            resp = {"transaction_id": txn_id}
            store_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idem,
                route_key=route_key,
                request_hash_value=req_hash,
                response_json=resp,
                status_code=200,
            )

        return TxnResponse(transaction_id=txn_id)

    except HTTPException:
        raise
    except Exception as e:
        raise_http_from_db_error(e)
        raise HTTPException(status_code=500, detail="Database error")
