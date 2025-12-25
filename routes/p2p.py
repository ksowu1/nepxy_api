

# routes/p2p.py
from fastapi import APIRouter, Depends, HTTPException, Header
from uuid import UUID
from services.db_errors import raise_http_from_db_error
from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from schemas import P2PTransferRequest

router = APIRouter(prefix="/v1", tags=["p2p"])

SYSTEM_USER_ID = UUID("14b365c5-413b-43da-9d5f-86be7fd95fe3")  # system@nexapay.local

@router.post("/p2p/transfer")
def p2p_transfer(
    body: P2PTransferRequest,
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                # derive country from sender wallet
                cur.execute(
                    "SELECT country FROM ledger.ledger_accounts WHERE id=%s::uuid;",
                    (str(body.from_wallet_id),),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="WALLET_NOT_FOUND")
                country = row[0]

                cur.execute(
                    """
                    SELECT ledger.post_p2p_transfer(
                        %s::uuid,                 -- sender wallet
                        %s::uuid,                 -- sender user
                        %s::uuid,                 -- receiver wallet
                        %s::bigint,               -- amount
                        %s::ledger.country_code,  -- country
                        %s::text,                 -- idempotency
                        %s::text,                 -- description
                        %s::uuid                  -- system owner
                    );
                    """,
                    (
                        str(body.from_wallet_id),
                        str(user.user_id),
                        str(body.to_wallet_id),
                        int(body.amount_cents),
                        str(country),
                        idempotency_key.strip(),
                        body.memo,
                        str(SYSTEM_USER_ID),
                    ),
                )
                tx_id = cur.fetchone()[0]

        return {"transaction_id": tx_id}

    except Exception as e:
        raise_http_from_db_error(e)
        raise
