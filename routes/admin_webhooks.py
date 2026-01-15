

# routes/admin_webhooks.py
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from db import get_conn
from services.roles import require_admin
from deps.auth import CurrentUser
from services.audit_log import write_audit_log
from app.payouts.repository import update_status_by_any_ref, get_payout_by_any_ref
from app.providers.mobile_money.thunes import ThunesProvider

router = APIRouter(prefix="/v1/admin/webhooks", tags=["admin_webhooks"])


def _map_provider_status(status_raw: str, provider: str | None = None):
    if (provider or "").strip().upper() == "THUNES":
        mapped_status, retryable, last_error = ThunesProvider.map_thunes_status(status_raw)
        return (mapped_status, retryable, last_error, None)

    status = (status_raw or "").strip().upper()

    if status in ("SUCCESS", "SUCCESSFUL", "CONFIRMED", "COMPLETED"):
        return ("CONFIRMED", False, None, None)
    if status in ("FAILED", "REJECTED", "CANCELLED", "CANCELED"):
        return ("FAILED", False, status, None)

    return ("SENT", True, None, None)


def _extract_refs(payload: dict) -> tuple[str | None, str | None, str]:
    provider_ref = (
        payload.get("provider_ref")
        or payload.get("providerReference")
        or payload.get("reference")
        or payload.get("transaction_id")
        or payload.get("id")
        or ""
    )
    provider_ref = str(provider_ref).strip() or None

    external_ref = (
        payload.get("external_ref")
        or payload.get("externalReference")
        or payload.get("external_id")
        or payload.get("client_ref")
        or payload.get("clientReference")
        or payload.get("merchant_ref")
        or payload.get("merchantReference")
        or ""
    )
    external_ref = str(external_ref).strip() or None

    status = (payload.get("status") or payload.get("state") or "").strip()
    return provider_ref, external_ref, status


def _unwrap_payload(obj: Any) -> Any:
    # Some providers wrap like {"data": {...}} or {"event": {...}}
    if isinstance(obj, dict):
        if isinstance(obj.get("data"), dict):
            return obj["data"]
        if isinstance(obj.get("event"), dict):
            return obj["event"]
    return obj


@router.get("/events")
def list_events(
    limit: int = Query(50, ge=1, le=200),
    provider: str | None = Query(None),
    external_ref: str | None = Query(None),
    provider_ref: str | None = Query(None),
    _admin=Depends(require_admin),
):
    """
    Returns:
      { "events": [...], "count": N, "limit": limit }
    """

    where = []
    params: list[Any] = []

    if provider:
        where.append("provider = %s")
        params.append(provider.strip().upper())

    if external_ref:
        where.append("external_ref = %s")
        params.append(external_ref.strip())

    if provider_ref:
        where.append("provider_ref = %s")
        params.append(provider_ref.strip())

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            id::text,
            provider,
            external_ref,
            provider_ref,
            status_raw,
            signature_valid,
            received_at,
            payload
        FROM app.webhook_events
        {where_sql}
        ORDER BY received_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    events = []
    for r in rows:
        events.append(
            {
                "id": r[0],
                "provider": r[1],
                "external_ref": r[2],
                "provider_ref": r[3],
                "status_raw": r[4],
                "signature_valid": r[5],
                "received_at": r[6].isoformat() if r[6] else None,
                "payload": r[7],
            }
        )

    return {"events": events, "count": len(events), "limit": limit}


@router.post("/events/{event_id}/replay")
def replay_event(
    event_id: str = Path(...),
    allow_terminal_override: bool = Query(False),
    admin: CurrentUser = Depends(require_admin),
):
    """
    Re-process a previously stored webhook event payload and apply it to payout state again.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider, payload, status_raw, external_ref, provider_ref
                FROM app.webhook_events
                WHERE id = %s::uuid
                """,
                (event_id,),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail={"error": "EVENT_NOT_FOUND", "event_id": event_id})

        provider, payload, status_raw, external_ref, provider_ref = row

        payload = _unwrap_payload(payload)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail={"error": "INVALID_EVENT_PAYLOAD", "event_id": event_id})

        pr2, er2, st2 = _extract_refs(payload)
        provider_ref = pr2 or provider_ref
        external_ref = er2 or external_ref
        status_raw = st2 or (status_raw or "")

        if not status_raw:
            raise HTTPException(status_code=400, detail={"error": "MISSING_STATUS", "event_id": event_id})
        if not provider_ref and not external_ref:
            raise HTTPException(status_code=400, detail={"error": "MISSING_REFS", "event_id": event_id})

        new_status, retryable, last_error, next_retry_at = _map_provider_status(status_raw, provider=provider)

        ok = update_status_by_any_ref(
            conn,
            provider_ref=provider_ref,
            external_ref=external_ref,
            new_status=new_status,
            provider_response={**payload, "_provider": provider, "_replayed_from_event_id": event_id},
            retryable=retryable,
            last_error=last_error,
            next_retry_at=next_retry_at,
            allow_terminal_override=bool(allow_terminal_override),
        )

        payout = get_payout_by_any_ref(conn, provider_ref=provider_ref, external_ref=external_ref)

        ignored = False
        reason = None
        if not ok:
            ignored = True
            if payout and payout.get("status") in ("CONFIRMED", "FAILED"):
                reason = f"ALREADY_{payout['status']}"
            elif payout:
                reason = "NOT_UPDATED"
            else:
                reason = "PAYOUT_NOT_FOUND"

        write_audit_log(
            conn,
            actor_user_id=str(admin.user_id),
            action="WEBHOOK_REPLAY",
            target_id=str(event_id),
            metadata={
                "provider": provider,
                "provider_ref": provider_ref,
                "external_ref": external_ref,
                "applied": bool(ok),
                "ignored": bool(ignored),
                "reason": reason,
            },
        )

        conn.commit()

    return {
        "ok": True,
        "event_id": event_id,
        "provider": provider,
        "provider_ref": provider_ref,
        "external_ref": external_ref,
        "status_raw": status_raw,
        "applied": bool(ok),
        "ignored": ignored,
        "reason": reason,
        "payout_status": (payout.get("status") if payout else None),
    }
