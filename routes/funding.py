from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from deps.auth import get_current_user, CurrentUser
from settings import settings
from app.funding.models import FundingIntentRequest, FundingProvider
from app.funding.service import build_funding_request

router = APIRouter(prefix="/v1/funding", tags=["funding"])
logger = logging.getLogger("nexapay.funding.http")


def _require_enabled(provider: FundingProvider) -> None:
    if provider == FundingProvider.ACH and not bool(settings.FUNDING_ACH_ENABLED):
        raise HTTPException(status_code=503, detail={"error": "FEATURE_DISABLED", "feature": "ACH"})
    if provider == FundingProvider.CARD and not bool(settings.FUNDING_CARD_ENABLED):
        raise HTTPException(status_code=503, detail={"error": "FEATURE_DISABLED", "feature": "CARD"})
    if provider == FundingProvider.WIRE and not bool(settings.FUNDING_WIRE_ENABLED):
        raise HTTPException(status_code=503, detail={"error": "FEATURE_DISABLED", "feature": "WIRE"})


def _not_implemented(provider: FundingProvider, request_id: str) -> None:
    raise HTTPException(
        status_code=501,
        detail={
            "error": "NOT_IMPLEMENTED",
            "feature": provider.value,
            "request_id": request_id,
        },
    )


@router.post("/ach")
def create_funding_ach(
    body: FundingIntentRequest,
    req: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    _require_enabled(FundingProvider.ACH)
    funding = build_funding_request(
        provider=FundingProvider.ACH,
        body=body,
        user_id=user.user_id,
        idempotency_key=idempotency_key,
        request_id=getattr(req.state, "request_id", None),
    )
    _not_implemented(FundingProvider.ACH, funding.request_id)


@router.post("/card")
def create_funding_card(
    body: FundingIntentRequest,
    req: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    _require_enabled(FundingProvider.CARD)
    funding = build_funding_request(
        provider=FundingProvider.CARD,
        body=body,
        user_id=user.user_id,
        idempotency_key=idempotency_key,
        request_id=getattr(req.state, "request_id", None),
    )
    _not_implemented(FundingProvider.CARD, funding.request_id)


@router.post("/wire")
def create_funding_wire(
    body: FundingIntentRequest,
    req: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
):
    _require_enabled(FundingProvider.WIRE)
    funding = build_funding_request(
        provider=FundingProvider.WIRE,
        body=body,
        user_id=user.user_id,
        idempotency_key=idempotency_key,
        request_id=getattr(req.state, "request_id", None),
    )
    _not_implemented(FundingProvider.WIRE, funding.request_id)
