from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class FundingProvider(str, Enum):
    ACH = "ACH"
    CARD = "CARD"
    WIRE = "WIRE"


class FundingIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet_id: UUID
    amount_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    external_ref: str | None = Field(default=None, min_length=3, max_length=100)
    memo: str | None = Field(default=None, max_length=200)


class FundingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    provider: FundingProvider
    wallet_id: UUID
    amount_cents: int
    currency: str
    external_ref: str | None = None
    memo: str | None = None
    user_id: UUID | None = None
    idempotency_key: str | None = None
    status: str = "RECEIVED"
    created_at: datetime
