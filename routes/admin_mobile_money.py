

# routes/admin_mobile_money.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from db import get_conn
from deps.admin import require_admin
from deps.auth import CurrentUser
from services.audit_log import write_audit_log
from app.workers import payout_worker

router = APIRouter(prefix="/v1/admin/mobile-money", tags=["admin", "mobile-money"])

class PayoutRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False
    reason: str | None = None


class PayoutProcessOnceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_size: int = Field(default=1, ge=1, le=500)
    stale_seconds: int = Field(default=0, ge=0, le=3600)


def _serialize_retry_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "transaction_id": str(row["transaction_id"]),
        "status": row["status"],
        "retryable": bool(row.get("retryable")),
        "attempt_count": int(row.get("attempt_count") or 0),
        "next_retry_at": row["next_retry_at"].isoformat() if row.get("next_retry_at") else None,
    }


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

def _provider_aliases(provider: str | None) -> list[str]:
    if not provider:
        return []
    p = provider.strip().upper()
    if p in {"MOMO", "MTN_MOMO"}:
        return ["MOMO", "MTN_MOMO"]
    return [p]


@router.post("/payouts/{transaction_id}/confirmed")
def admin_mark_payout_confirmed(transaction_id: str, admin: CurrentUser = Depends(require_admin)):
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

        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="PAYOUT_CONFIRMED",
            target_id=str(updated[0]),
            metadata={"status": updated[1]},
        )
        conn.commit()

    return {"ok": True, "transaction_id": updated[0], "status": updated[1]}


@router.post("/payouts/{transaction_id}/retry")
def admin_retry_payout(
    transaction_id: UUID,
    body: PayoutRetryRequest | None = None,
    admin: CurrentUser = Depends(require_admin),
):
    req = body or PayoutRetryRequest()
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  p.transaction_id,
                  p.status,
                  p.retryable,
                  p.attempt_count,
                  p.next_retry_at,
                  p.last_error
                FROM app.mobile_money_payouts p
                WHERE p.transaction_id = %s::uuid
                """,
                (str(transaction_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Payout not found")

            status = str(row.get("status") or "")
            if status == "CONFIRMED":
                raise HTTPException(status_code=409, detail="ALREADY_CONFIRMED")

            if status == "PENDING":
                return _serialize_retry_summary(row)

            if status == "FAILED":
                if row.get("retryable") is False and not req.force:
                    raise HTTPException(status_code=409, detail="NOT_RETRYABLE")

                cur.execute(
                    """
                    UPDATE app.mobile_money_payouts
                    SET status = 'PENDING',
                        next_retry_at = now(),
                        last_error = NULL,
                        retryable = TRUE,
                        updated_at = now()
                    WHERE transaction_id = %s::uuid
                    RETURNING transaction_id, status, retryable, attempt_count, next_retry_at
                    """,
                    (str(transaction_id),),
                )
                row = cur.fetchone()
            else:
                raise HTTPException(status_code=409, detail="NOT_RETRYABLE")

        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="PAYOUT_RETRY",
            target_id=str(transaction_id),
            metadata={"force": bool(req.force), "reason": req.reason},
        )
        conn.commit()

    return _serialize_retry_summary(row)


@router.post("/payouts/process-once")
def admin_process_payouts_once(
    body: PayoutProcessOnceRequest | None = None,
    _admin=Depends(require_admin),
):
    req = body or PayoutProcessOnceRequest()
    processed = payout_worker.process_once(
        batch_size=req.batch_size,
        stale_seconds=req.stale_seconds,
    )
    return {"processed": processed}


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
    payout_sql = """
        SELECT
          p.provider,
          tx.external_ref AS external_ref,
          p.provider_ref AS provider_ref
        FROM app.mobile_money_payouts p
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        WHERE p.transaction_id = %s::uuid
    """
    events_sql = """
        SELECT
          id::text AS id,
          provider,
          external_ref,
          provider_ref,
          status_raw,
          signature_valid,
          received_at,
          COALESCE(payload_json, payload) AS payload_json
        FROM app.webhook_events
        WHERE provider = ANY(%s::text[])
          AND (external_ref = %s OR provider_ref = %s)
        ORDER BY received_at DESC
        LIMIT %s
    """
    events_sql_no_provider = """
        SELECT
          id::text AS id,
          provider,
          external_ref,
          provider_ref,
          status_raw,
          signature_valid,
          received_at,
          COALESCE(payload_json, payload) AS payload_json
        FROM app.webhook_events
        WHERE (external_ref = %s OR provider_ref = %s)
        ORDER BY received_at DESC
        LIMIT %s
    """

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(payout_sql, (str(transaction_id),))
            payout = cur.fetchone()
            if not payout:
                raise HTTPException(status_code=404, detail="Payout not found")

            payout_external_ref = payout.get("external_ref") or f"ext-{transaction_id}"
            providers = _provider_aliases(payout.get("provider"))
            if not providers:
                providers = ["UNKNOWN"]
            cur.execute(
                events_sql,
                (
                    providers,
                    payout_external_ref,
                    payout.get("provider_ref"),
                    limit,
                ),
            )
            rows = cur.fetchall() or []
            if not rows:
                cur.execute(
                    events_sql_no_provider,
                    (
                        payout_external_ref,
                        payout.get("provider_ref"),
                        limit,
                    ),
                )
                rows = cur.fetchall() or []

    events = []
    for row in rows:
        event_external_ref = row["external_ref"] or payout_external_ref
        events.append(
            {
                "id": row["id"],
                "provider": row["provider"],
                "external_ref": event_external_ref,
                "provider_ref": row["provider_ref"],
                "status_raw": row["status_raw"],
                "signature_valid": row["signature_valid"],
                "received_at": row["received_at"].isoformat() if row["received_at"] else None,
                "payload": row["payload_json"],
            }
        )

    return {"events": events, "count": len(events), "limit": limit}


@router.get("/trace")
def admin_trace_events(
    transaction_id: str | None = Query(None),
    external_ref: str | None = Query(None),
    provider_ref: str | None = Query(None),
    provider: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin=Depends(require_admin),
):
    tx_id = (transaction_id or "").strip()
    ext_ref = (external_ref or "").strip()
    prov_ref = (provider_ref or "").strip()
    prov = (provider or "").strip().upper()

    if not any([tx_id, ext_ref, prov_ref]):
        return {"payouts": [], "webhook_events": [], "count": 0, "limit": limit}

    where = []
    params: list[Any] = []
    if tx_id:
        where.append("p.transaction_id::text = %s")
        params.append(tx_id)
    if prov_ref:
        where.append("p.provider_ref = %s")
        params.append(prov_ref)
    if ext_ref:
        where.append("tx.external_ref = %s")
        params.append(ext_ref)
    if prov:
        where.append("upper(p.provider) = upper(%s)")
        params.append(prov)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    payouts_sql = f"""
        SELECT
          p.id::text AS payout_id,
          p.transaction_id::text AS transaction_id,
          p.status,
          p.provider,
          p.phone_e164,
          p.provider_ref,
          p.created_at,
          tx.external_ref,
          tx.amount_cents,
          tx.currency
        FROM app.mobile_money_payouts p
        LEFT JOIN ledger.ledger_transactions tx ON tx.id = p.transaction_id
        {where_sql}
        ORDER BY p.created_at DESC
        LIMIT %s
    """
    params_with_limit = params + [limit]

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(payouts_sql, params_with_limit)
            payouts = cur.fetchall() or []

            external_refs = {ext_ref} if ext_ref else set()
            provider_refs = {prov_ref} if prov_ref else set()
            providers = {prov} if prov else set()
            for row in payouts:
                if row.get("external_ref"):
                    external_refs.add(row["external_ref"])
                if row.get("provider_ref"):
                    provider_refs.add(row["provider_ref"])
                if row.get("provider"):
                    providers.add(str(row["provider"]).upper())

            webhook_events = []
            if external_refs or provider_refs:
                cur.execute(
                    """
                    SELECT
                      id::text AS id,
                      provider,
                      external_ref,
                      provider_ref,
                      status_raw,
                      signature_valid,
                      received_at,
                      COALESCE(payload_json, payload) AS payload_json
                    FROM app.webhook_events
                    WHERE (external_ref = ANY(%s::text[]) OR provider_ref = ANY(%s::text[]))
                      AND (%s = '' OR upper(provider) = %s)
                    ORDER BY received_at DESC
                    LIMIT %s
                    """,
                    (
                        list(external_refs) or [""],
                        list(provider_refs) or [""],
                        prov or "",
                        prov or "",
                        limit,
                    ),
                )
                webhook_events = cur.fetchall() or []

    return {
        "payouts": payouts,
        "webhook_events": webhook_events,
        "count": len(payouts) + len(webhook_events),
        "limit": limit,
    }
