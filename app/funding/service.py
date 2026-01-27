from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import logging

from app.funding.models import FundingIntentRequest, FundingRequest, FundingProvider

logger = logging.getLogger("nexapay.funding")


def build_funding_request(
    *,
    provider: FundingProvider,
    body: FundingIntentRequest,
    user_id: UUID | None,
    idempotency_key: str | None,
    request_id: str | None,
) -> FundingRequest:
    req_id = request_id or str(uuid4())
    req = FundingRequest(
        request_id=req_id,
        provider=provider,
        wallet_id=body.wallet_id,
        amount_cents=int(body.amount_cents),
        currency=(body.currency or "").strip().upper(),
        external_ref=body.external_ref,
        memo=body.memo,
        user_id=user_id,
        idempotency_key=(idempotency_key or "").strip() or None,
        created_at=datetime.now(timezone.utc),
    )

    # Ledger integration point (once funding rails are implemented):
    # - Post a ledger cash-in transaction here (e.g., ledger.post_cash_in_funding_*).
    # - Persist request_id/external_ref for reconciliation and webhook updates.
    logger.info(
        "funding request created provider=%s request_id=%s wallet_id=%s amount_cents=%s currency=%s",
        req.provider,
        req.request_id,
        req.wallet_id,
        req.amount_cents,
        req.currency,
    )
    return req
