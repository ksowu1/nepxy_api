
# routes/fx.py
from fastapi import APIRouter, Depends, Header
from typing import Optional

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from db_exec import db_fetchone
from pydantic import BaseModel, Field

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
        with conn.cursor() as cur:
            set_db_actor(cur, user.user_id)

        row = db_fetchone(
            conn,
            "SELECT ledger.post_fx_convert_secure(%s::uuid, %s::text);",
            (req.quote_id, idempotency_key),
        )

    return FxConvertResponse(transaction_id=str(row[0]))
