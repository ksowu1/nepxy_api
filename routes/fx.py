
# routes/fx.py
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timezone

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from db_exec import db_fetchone
from pydantic import BaseModel, Field
from services.idempotency import get_idempotency, store_idempotency, request_hash, idempotency_conflict
from services.metrics import increment_idempotency_replay
from settings import FX_STATIC_RATES

router = APIRouter(prefix="/v1", tags=["fx"])


class FxQuoteRequest(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    from_amount_cents: int = Field(..., gt=0)


class FxQuoteResponse(BaseModel):
    quote_id: str
    rate_used: str
    from_amount_cents: int
    to_amount_cents: int
    expires_at: str


class FxConvertRequest(BaseModel):
    quote_id: str


class FxConvertResponse(BaseModel):
    transaction_id: str


class FxQuotePublicResponse(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    inverse_rate: float
    amount: float
    converted_amount: float
    updated_at: str
    source: str


@router.post("/fx/quote", response_model=FxQuoteResponse)
def fx_quote(req: FxQuoteRequest, user: CurrentUser = Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        row = db_fetchone(
            conn,
            "SELECT * FROM fx.issue_fx_quote_secure(%s::text, %s::text, %s::bigint);",
            (req.from_currency, req.to_currency, int(req.from_amount_cents)),
        )

    return FxQuoteResponse(
        quote_id=str(row[0]),
        rate_used=str(row[1]),
        from_amount_cents=int(row[2]),
        to_amount_cents=int(row[3]),
        expires_at=row[4].isoformat(),
    )


@router.get("/fx/quote", response_model=FxQuotePublicResponse)
def fx_quote_public(
    from_currency: str = Query("USD", min_length=3, max_length=3, alias="from"),
    to_currency: str = Query(..., min_length=3, max_length=3, alias="to"),
    amount: float = Query(100.0, gt=0),
):
    """
    Lightweight FX quote endpoint for clients.
    Returns static rates in dev; replace with provider-backed rates later.
    """
    pair = (from_currency.upper(), to_currency.upper())
    rate = FX_STATIC_RATES.get(pair)
    if rate is None:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FX_PAIR")

    converted_amount = round(amount * rate, 6)
    updated_at = datetime.now(timezone.utc).isoformat()

    return FxQuotePublicResponse(
        from_currency=pair[0],
        to_currency=pair[1],
        rate=float(rate),
        inverse_rate=round(1.0 / float(rate), 6),
        amount=float(amount),
        converted_amount=converted_amount,
        updated_at=updated_at,
        source="static",
    )


@router.post("/fx/convert", response_model=FxConvertResponse)
def fx_convert(
    req: FxConvertRequest,
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        # Match your existing API behavior
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")

    with get_conn() as conn:
        cached = get_idempotency(
            conn,
            user_id=str(user.user_id),
            idempotency_key=idempotency_key.strip(),
            route_key="fx_convert",
        )
        if cached:
            req_hash = request_hash(req.model_dump())
            if cached.get("request_hash") and cached["request_hash"] != req_hash:
                from fastapi import HTTPException
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")
            increment_idempotency_replay("fx_convert")
            return JSONResponse(status_code=cached["status_code"], content=cached["response_json"])
        if idempotency_conflict(
            conn,
            user_id=str(user.user_id),
            idempotency_key=idempotency_key.strip(),
            route_key="fx_convert",
        ):
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        row = db_fetchone(
            conn,
            "SELECT ledger.post_fx_convert_secure(%s::uuid, %s::text);",
            (req.quote_id, idempotency_key),
        )

        resp = {"transaction_id": str(row[0])}
        store_idempotency(
            conn,
            user_id=str(user.user_id),
            idempotency_key=idempotency_key.strip(),
            route_key="fx_convert",
            request_hash_value=request_hash(req.model_dump()),
            response_json=resp,
            status_code=200,
        )

    return FxConvertResponse(transaction_id=str(row[0]))
