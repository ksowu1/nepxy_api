

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


@dataclass(frozen=True)
class Payout:
    id: UUID
    transaction_id: UUID
    provider: str
    phone_e164: str
    provider_ref: Optional[str]
    status: str
    last_error: Optional[str]
    attempt_count: int
    last_attempt_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    provider_response: Optional[dict[str, Any]]
