from __future__ import annotations

from enum import Enum
from typing import Protocol

from app.providers.base import ProviderResult
from services.providers.momo import MomoProvider


class ProviderName(str, Enum):
    MOMO = "MOMO"
    TMONEY = "TMONEY"
    THUNES = "THUNES"
    FLOOZ = "FLOOZ"


class PayoutProvider(Protocol):
    def initiate_payout(self, payout: dict) -> ProviderResult: ...
    def get_payout_status(self, payout: dict) -> ProviderResult: ...


PROVIDERS: dict[str, type[PayoutProvider]] = {
    ProviderName.MOMO.value: MomoProvider,
}
