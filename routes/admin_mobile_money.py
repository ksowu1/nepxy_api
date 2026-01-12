

# routes/admin_mobile_money.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor

from db import get_conn
from deps.admin import require_admin

router = APIRouter(prefix="/v1/admin/mobile-money", tags=["admin", "mobile-money"])

def _serialize_payout(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "transaction_id": str(row["transaction_id"]),
        "status": row["status"],
        "provider": row["provider"],
        "amount_cents": int(row.get("amount_cents") or 0),
        "currency": row.get("currency"),
        "phone_e164": row.get("phone_e164"),
        "retryable": bool(row.get("retryable")),
        "attempt_count": int(row.get("attempt_count") or 0),
        "last_error": row.get("last_error"),
        "next_retry_at": row["next_retry_at"].isoformat() if row.get("next_retry_at") else None,
        "provider_ref": row.get("provider_ref"),
        "external_ref": row.get("external_ref"),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


@router.post("/payouts/{transaction_id}/confirmed")
def admin_mark_payout_confirmed(transaction_id: str, _admin=Depends(require_admin)):
    """
    Admin endpoint to force-confirm a payout.
    Used by tests: test_admin_can_mark_payout_confirmed
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Ensure payout exists
            cur.execute(
                "SELECT transaction_id, status FROM app.mobile_money_payouts WHERE transaction_id=%s",
                (transaction_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payout not found")

            # Update
            cur.execute(
                """
                UPDATE app.mobile_money_payouts
                SET status='CONFIRMED', updated_at=NOW()
                WHERE transaction_id=%s
                RETURNING transaction_id, status
                """,
                (transaction_id,),
            )
            updated = cur.fetchone()

        conn.commit()

    return {"ok": True, "transaction_id": updated[0], "status": updated[1]}


@router.post("/payouts/{transaction_id}/retry")
def admin_retry_payout(transaction_id: UUID, _admin=Depends(require_admin)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  p.transaction_id,
                  p.provider,
                  p.amount_cents,
                  p.currency,
                  p.phone_e164,
                  p.provider_ref,
                  p.status,
                  p.last_error,
                  p.retryable,
                  p.attempt_count,
                  p.next_retry_at,
                  p.updated_at,
                  tx.external_ref
                FROM app.mobile_money_payouts p
                LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                WHERE p.transaction_id = %s::uuid
                """,
                (str(transaction_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payout not found")

            if row.get("retryable") is False:
                raise HTTPException(status_code=409, detail="payout_not_retryable")

            status = str(row.get("status") or "")
            if status == "CONFIRMED":
                raise HTTPException(status_code=409, detail="payout_already_confirmed")

            if status in ("FAILED", "RETRY"):
                cur.execute(
                    """
                    UPDATE app.mobile_money_payouts
                    SET status = 'PENDING',
                        next_retry_at = now(),
                        last_error = NULL,
                        updated_at = now()
                    WHERE transaction_id = %s::uuid
                    """,
                    (str(transaction_id),),
                )

                cur.execute(
                    """
                    SELECT
                      p.transaction_id,
                      p.provider,
                      p.amount_cents,
                      p.currency,
                      p.phone_e164,
                      p.provider_ref,
                      p.status,
                      p.last_error,
                      p.retryable,
                      p.attempt_count,
                      p.next_retry_at,
                      p.updated_at,
                      tx.external_ref
                    FROM app.mobile_money_payouts p
                    LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
                    WHERE p.transaction_id = %s::uuid
                    """,
                    (str(transaction_id),),
                )
                row = cur.fetchone()

            elif status not in ("PENDING",):
                raise HTTPException(status_code=409, detail="payout_status_not_retryable")

        conn.commit()

    return _serialize_payout(row)


@router.get("/payouts")
def admin_list_payouts(
    status: str | None = Query(None),
    provider: str | None = Query(None),
    retryable: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin=Depends(require_admin),
):
    where = []
    params: list[Any] = []

    if status:
        where.append("upper(p.status) = upper(%s)")
        params.append(status.strip())

    if provider:
        where.append("upper(p.provider) = upper(%s)")
        params.append(provider.strip())

    if retryable is not None:
        where.append("p.retryable = %s")
        params.append(retryable)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
          p.transaction_id,
          p.provider,
          p.amount_cents,
          p.currency,
          p.phone_e164,
          p.provider_ref,
          p.status,
          p.last_error,
          p.retryable,
          p.attempt_count,
          p.next_retry_at,
          p.updated_at,
          tx.external_ref
        FROM app.mobile_money_payouts p
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        {where_sql}
        ORDER BY p.updated_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []

    payouts = [_serialize_payout(r) for r in rows]
    return {"payouts": payouts, "count": len(payouts), "limit": limit, "offset": offset}


@router.get("/payouts/{transaction_id}/webhook-events")
def admin_list_payout_webhook_events(
    transaction_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    _admin=Depends(require_admin),
):
    sql = """
        SELECT
          provider,
          external_ref,
          provider_ref,
          status_raw,
          signature_valid,
          event_hash,
          received_at
        FROM app.webhook_events
        WHERE payout_transaction_id = %s::uuid
        ORDER BY received_at DESC
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(transaction_id), limit))
            rows = cur.fetchall() or []

    events = []
    for r in rows:
        events.append(
            {
                "provider": r[0],
                "signature_valid": r[4],
                "provider_ref": r[2],
                "external_ref": r[1],
                "status_raw": r[3],
                "event_hash": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }
        )

    return {"events": events, "count": len(events), "limit": limit}
