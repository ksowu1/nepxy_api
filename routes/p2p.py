

# routes/p2p.py
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from uuid import UUID

from deps.auth import get_current_user, CurrentUser
from db import get_conn
from db_session import set_db_actor
from schemas import P2PTransferRequest
from services.db_errors import raise_http_from_db_error
from services.idempotency import get_idempotency, store_idempotency, request_hash, idempotency_conflict
from services.metrics import increment_idempotency_replay

router = APIRouter(prefix="/v1", tags=["p2p"])

SYSTEM_USER_ID = UUID("14b365c5-413b-43da-9d5f-86be7fd95fe3")  # system@nexapay.local


@router.post("/p2p/transfer")
def p2p_transfer(
    body: P2PTransferRequest,
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    # Idempotency is mandatory
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

    route_key = "p2p_transfer"
    req_hash = request_hash(body.model_dump())

    try:
        with get_conn() as conn:
            cached = get_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idempotency_key.strip(),
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
                idempotency_key=idempotency_key.strip(),
                route_key=route_key,
            ):
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

            with conn.cursor() as cur:
                set_db_actor(cur, user.user_id)

                # derive country from sender wallet
                cur.execute(
                    "SELECT country FROM ledger.ledger_accounts WHERE id=%s::uuid;",
                    (str(body.from_wallet_id),),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Wallet not found")
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

            resp = {"transaction_id": tx_id}
            store_idempotency(
                conn,
                user_id=str(user.user_id),
                idempotency_key=idempotency_key.strip(),
                route_key=route_key,
                request_hash_value=req_hash,
                response_json=resp,
                status_code=200,
            )

        return {"transaction_id": tx_id}

    except HTTPException:
        # already clean
        raise
    except Exception as e:
        # ✅ Convert DB_ERROR codes into 403/404/409/etc
        raise_http_from_db_error(e)

        # If mapping didn't raise, fail closed (no "P2P failed" masking)
        raise HTTPException(status_code=500, detail="Internal server error")
