


# routes/webhooks.py
from __future__ import annotations

import os
import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from psycopg2.extras import Json

from db import get_conn

from app.payouts.repository import (
    update_status_by_any_ref,
    get_payout_by_any_ref,
)

# IMPORTANT:
# This existing function in your repo logs a "detailed" webhook audit record
# (likely in a different table than app.webhook_events).
from app.webhooks.repository import insert_webhook_event as insert_webhook_audit_event


router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


_ENV_SECRET_BY_PROVIDER = {
    "TMONEY": "TMONEY_WEBHOOK_SECRET",
    "FLOOZ": "FLOOZ_WEBHOOK_SECRET",
    "MOMO": "MOMO_WEBHOOK_SECRET",
    "THUNES": "THUNES_WEBHOOK_SECRET",
}


def _map_provider_status(status_raw: str):
    status = (status_raw or "").strip().upper()

    if status in ("SUCCESS", "SUCCESSFUL", "CONFIRMED", "COMPLETED"):
        return ("CONFIRMED", False, None, None)  # new_status, retryable, last_error, next_retry_at
    if status in ("FAILED", "REJECTED", "CANCELLED", "CANCELED"):
        return ("FAILED", False, status, None)

    # in-flight/unknown -> keep it retryable so worker can poll
    return ("SENT", True, None, None)


def _unwrap_payload(payload: Any) -> Any:
    """
    Some providers wrap payloads like {"data": {...}}.
    """
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _extract_refs(payload: dict) -> tuple[str | None, str | None, str]:
    """
    Normalize common provider payload shapes.
    We accept either provider_ref OR external_ref.
    """
    provider_ref = (
        payload.get("provider_ref")
        or payload.get("providerReference")
        or payload.get("reference")
        or ""
    )
    provider_ref = str(provider_ref).strip() or None

    external_ref = (
        payload.get("external_ref")
        or payload.get("externalReference")
        or payload.get("client_ref")
        or payload.get("clientReference")
        or payload.get("merchant_ref")
        or payload.get("merchantReference")
        or ""
    )
    external_ref = str(external_ref).strip() or None

    status = (payload.get("status") or payload.get("state") or "").strip()
    return provider_ref, external_ref, status


def _get_secret(provider: str) -> str | None:
    key = _ENV_SECRET_BY_PROVIDER.get(provider.upper())
    if not key:
        return None
    return os.getenv(key)


def _verify_signature(*, raw: bytes, signature_header: str | None, secret: str | None) -> tuple[bool, str | None]:
    if not secret or not secret.strip():
        return False, "WEBHOOK_SECRET_NOT_CONFIGURED"

    if not signature_header or not signature_header.strip():
        return False, "MISSING_SIGNATURE"

    sig = signature_header.strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1].strip()

    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "INVALID_SIGNATURE"

    return True, None


def _insert_admin_webhook_event(
    conn,
    *,
    provider: str,
    headers: dict,
    payload: dict | None,
    provider_ref: str | None,
    external_ref: str | None,
    status_raw: str,
    signature_valid: bool,
) -> str:
    """
    Inserts into app.webhook_events — the table your /v1/admin/webhooks/events endpoint reads.
    Returns the inserted event id as string.
    """
    event_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.webhook_events
                (id, provider, external_ref, provider_ref, status_raw, payload, headers, received_at, signature_valid)
            VALUES
                (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            """,
            (
                event_id,
                provider,
                external_ref,
                provider_ref,
                status_raw,
                Json(payload) if payload is not None else Json({}),
                Json(headers or {}),
                received_at,
                bool(signature_valid),
            ),
        )

    return event_id


def _log_both_tables(
    conn,
    *,
    provider: str,
    req: Request,
    headers: dict,
    payload_for_storage: dict | None,
    payload_obj: dict | None,
    body_raw_str: str,
    sig_header: str | None,
    signature_valid: bool,
    signature_error: str | None,
    provider_ref: str | None,
    external_ref: str | None,
    status_raw: str,
    payout_transaction_id: str | None = None,
    payout_status_before: str | None = None,
    payout_status_after: str | None = None,
    update_applied: bool = False,
    ignored: bool = False,
    ignore_reason: str | None = None,
):
    # 1) Minimal admin table insert (this is what fixes your failing tests)
    _insert_admin_webhook_event(
        conn,
        provider=provider,
        headers=headers,
        payload=payload_for_storage,
        provider_ref=provider_ref,
        external_ref=external_ref,
        status_raw=status_raw,
        signature_valid=signature_valid,
    )

    # 2) Your existing detailed audit insert (kept as-is)
    insert_webhook_audit_event(
        conn,
        provider=provider,
        path=str(req.url.path),
        headers=headers,
        body=payload_obj,
        body_raw=body_raw_str,
        signature=sig_header,
        signature_valid=signature_valid,
        signature_error=signature_error,
        provider_ref=provider_ref,
        external_ref=external_ref,
        status_raw=status_raw,
        payout_transaction_id=payout_transaction_id,
        payout_status_before=payout_status_before,
        payout_status_after=payout_status_after,
        update_applied=update_applied,
        ignored=ignored,
        ignore_reason=ignore_reason,
    )


async def _handle_mobile_money_webhook(req: Request, *, provider: str):
    raw = await req.body()
    sig_header = req.headers.get("X-Signature")

    secret = _get_secret(provider)
    sig_ok, sig_err = _verify_signature(raw=raw, signature_header=sig_header, secret=secret)

    # Try parse JSON (even on invalid sig) so we can log refs when possible
    payload_original: dict[str, Any] | None = None
    payload_obj: dict[str, Any] | None = None  # unwrapped dict used for extracting refs
    body_raw_str = raw.decode("utf-8", errors="replace")

    try:
        parsed = await req.json()
        if isinstance(parsed, dict):
            payload_original = parsed
            unwrapped = _unwrap_payload(parsed)
            if isinstance(unwrapped, dict):
                payload_obj = unwrapped
    except Exception:
        payload_original = None
        payload_obj = None

    provider_ref = None
    external_ref = None
    status_raw = ""

    if payload_obj is not None:
        provider_ref, external_ref, status_raw = _extract_refs(payload_obj)

    headers_dict = dict(req.headers)

    # If secret missing, log and 500 (deployment misconfig)
    if sig_err == "WEBHOOK_SECRET_NOT_CONFIGURED":
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=payload_obj,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=False,
                signature_error=sig_err,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason=sig_err,
            )
            conn.commit()
        raise HTTPException(status_code=500, detail={"error": sig_err, "provider": provider})

    # Missing/invalid signature -> log and 401
    if not sig_ok:
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=payload_obj,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=False,
                signature_error=sig_err,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason=sig_err,
            )
            conn.commit()
        raise HTTPException(status_code=401, detail={"error": sig_err})

    # From here: signature valid, now enforce valid JSON object
    if payload_obj is None:
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=None,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=True,
                signature_error=None,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason="INVALID_JSON",
            )
            conn.commit()
        raise HTTPException(status_code=400, detail={"error": "INVALID_JSON", "body": body_raw_str})

    if not isinstance(payload_obj, dict):
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=None,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=True,
                signature_error=None,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason="INVALID_JSON_OBJECT",
            )
            conn.commit()
        raise HTTPException(status_code=400, detail={"error": "INVALID_JSON_OBJECT"})

    provider_ref, external_ref, status_raw = _extract_refs(payload_obj)

    if not status_raw:
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=payload_obj,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=True,
                signature_error=None,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason="MISSING_STATUS",
            )
            conn.commit()
        raise HTTPException(status_code=400, detail={"error": "MISSING_STATUS"})

    if not provider_ref and not external_ref:
        with get_conn() as conn:
            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=payload_obj,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=True,
                signature_error=None,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                ignored=True,
                ignore_reason="MISSING_PROVIDER_REF_OR_EXTERNAL_REF",
            )
            conn.commit()
        raise HTTPException(status_code=400, detail={"error": "MISSING_PROVIDER_REF_OR_EXTERNAL_REF"})

    new_status, retryable, last_error, next_retry_at = _map_provider_status(status_raw)

    with get_conn() as conn:
        existing = get_payout_by_any_ref(conn, provider_ref=provider_ref, external_ref=external_ref)
        status_before = existing.get("status") if existing else None
        tx_id = existing.get("transaction_id") if existing else None

        update_applied = False
        ignored = False
        ignore_reason = None
        status_after = None

        if not existing:
            # IMPORTANT: return 200 to avoid provider retry storms
            ignored = True
            ignore_reason = "PAYOUT_NOT_FOUND"

            _log_both_tables(
                conn,
                provider=provider,
                req=req,
                headers=headers_dict,
                payload_for_storage=payload_original,
                payload_obj=payload_obj,
                body_raw_str=body_raw_str,
                sig_header=sig_header,
                signature_valid=True,
                signature_error=None,
                provider_ref=provider_ref,
                external_ref=external_ref,
                status_raw=status_raw,
                payout_transaction_id=None,
                payout_status_before=None,
                payout_status_after=None,
                update_applied=False,
                ignored=True,
                ignore_reason=ignore_reason,
            )
            conn.commit()

            return {
                "ok": True,
                "provider": provider,
                "provider_ref": provider_ref,
                "external_ref": external_ref,
                "status": status_raw,
                "ignored": True,
                "reason": ignore_reason,
            }

        # Try update (no terminal override)
        ok = update_status_by_any_ref(
            conn,
            provider_ref=provider_ref,
            external_ref=external_ref,
            new_status=new_status,
            provider_response={**payload_obj, "_provider": provider},
            retryable=retryable,
            last_error=last_error,
            next_retry_at=next_retry_at,
            allow_terminal_override=False,
        )

        if not ok:
            ignored = True
            status_after = status_before
            if status_before in ("CONFIRMED", "FAILED"):
                ignore_reason = f"ALREADY_{status_before}"
            else:
                ignore_reason = "NOT_UPDATED"
        else:
            update_applied = True
            refreshed = get_payout_by_any_ref(conn, provider_ref=provider_ref, external_ref=external_ref)
            status_after = refreshed.get("status") if refreshed else None

        _log_both_tables(
            conn,
            provider=provider,
            req=req,
            headers=headers_dict,
            payload_for_storage=payload_original,
            payload_obj=payload_obj,
            body_raw_str=body_raw_str,
            sig_header=sig_header,
            signature_valid=True,
            signature_error=None,
            provider_ref=provider_ref,
            external_ref=external_ref,
            status_raw=status_raw,
            payout_transaction_id=str(tx_id) if tx_id else None,
            payout_status_before=status_before,
            payout_status_after=status_after,
            update_applied=update_applied,
            ignored=ignored,
            ignore_reason=ignore_reason,
        )

        conn.commit()

    resp = {
        "ok": True,
        "provider": provider,
        "provider_ref": provider_ref,
        "external_ref": external_ref,
        "status": status_raw,
    }
    if ignored:
        resp["ignored"] = True
        resp["reason"] = ignore_reason
    return resp


@router.post("/tmoney")
async def tmoney_webhook(req: Request):
    return await _handle_mobile_money_webhook(req, provider="TMONEY")


@router.post("/flooz")
async def flooz_webhook(req: Request):
    return await _handle_mobile_money_webhook(req, provider="FLOOZ")


@router.post("/momo")
async def momo_webhook(req: Request):
    return await _handle_mobile_money_webhook(req, provider="MOMO")

@router.post("/thunes")
async def thunes_webhook(req: Request):
    return await _handle_mobile_money_webhook(req, provider="THUNES")
