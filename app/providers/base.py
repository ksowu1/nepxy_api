

# app/providers/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Literal

ProviderStatus = Literal["SENT", "CONFIRMED", "FAILED"]

@dataclass(frozen=True)
class ProviderResult:
    status: ProviderStatus
    provider_ref: Optional[str] = None
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    # None => let worker classify based on http_status / error
    retryable: Optional[bool] = None

    # --- Backward compatibility for older worker/tests ---
    @property
    def ok(self) -> bool:
        return self.status == "CONFIRMED"

    @property
    def provider_tx_id(self) -> Optional[str]:
        return self.provider_ref


class MobileMoneyProvider(Protocol):
    def send_cashout(self, payout: dict[str, Any]) -> ProviderResult: ...
    def get_cashout_status(self, payout: dict[str, Any]) -> ProviderResult: ...
