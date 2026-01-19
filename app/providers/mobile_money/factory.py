


# app/providers/mobile_money/factory.py
from __future__ import annotations

from typing import Any, Dict

_PROVIDER_CACHE: Dict[str, Any] = {}


def get_provider(name: str):
    key = (name or "").strip().upper()
    if not key:
        return None

    key = key.replace("-", "_").replace(" ", "_")

    if key in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[key]

    provider = None

    if key == "TMONEY":
        from app.providers.mobile_money.tmoney import TMoneyProvider
        provider = TMoneyProvider()

    elif key == "FLOOZ":
        from app.providers.mobile_money.flooz import FloozProvider
        provider = FloozProvider()

    elif key == "MOMO":
        from services.providers.momo import MomoProvider
        provider = MomoProvider()

    elif key in ("MTN", "MTN_MOMO"):
        from app.providers.mobile_money.mtn_momo import MtnMomoProvider
        provider = MtnMomoProvider()

    elif key == "THUNES":
        from app.providers.mobile_money.thunes import ThunesProvider
        provider = ThunesProvider()

    else:
        return None

    _PROVIDER_CACHE[key] = provider
    return provider
