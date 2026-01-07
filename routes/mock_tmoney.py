


# routes/mock_tmoney.py
from __future__ import annotations

from fastapi import APIRouter, Request
from datetime import datetime, timezone

router = APIRouter(prefix="/mock/tmoney", tags=["mock-tmoney"])

# provider_ref -> first_seen_utc
_seen: dict[str, datetime] = {}


@router.post("/cashout")
async def tmoney_cashout(req: Request):
    # Be tolerant: provider might send weird body; don't crash.
    payload = None
    try:
        payload = await req.json()
    except Exception:
        raw = (await req.body()).decode("utf-8", errors="ignore")
        payload = {"_raw": raw}

    external_id = None
    if isinstance(payload, dict):
        external_id = payload.get("external_id") or payload.get("provider_ref") or payload.get("id")

    return {
        "status": "ACCEPTED",
        "provider_tx_id": external_id or "mock-tx",
        "provider_ref": external_id or "mock-ref",
        "echo": payload,
    }


@router.api_route("/cashout", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"])
async def tmoney_cashout(req: Request):
    try:
        payload = await req.json()
    except Exception:
        raw = (await req.body()).decode("utf-8", errors="ignore")
        payload = {"_raw": raw}

    return {
        "method": req.method,
        "path": str(req.url.path),
        "headers_auth": req.headers.get("authorization"),
        "payload": payload,
    }

@router.get("/status/{provider_ref}")
async def tmoney_status(provider_ref: str):
    return {"status": "SUCCESS", "provider_ref": provider_ref}
