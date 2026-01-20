


# app/providers/mobile_money/validate.py
from __future__ import annotations

import logging
import os
from typing import Iterable

from app.providers.mobile_money.config import (
    enabled_providers,
    is_strict_startup_validation,
    mm_mode,
)

logger = logging.getLogger("nexapay")

ALLOWED_PROVIDERS = {"TMONEY", "FLOOZ", "MTN_MOMO", "MOMO", "THUNES"}


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _require(missing: list[str], *names: str) -> None:
    for n in names:
        if not _env(n):
            missing.append(n)


def _sorted_csv(items: Iterable[str]) -> str:
    return ", ".join(sorted(set(items)))


def _normalize_provider(p: str) -> str:
    p = (p or "").strip().upper()
    p = p.replace("-", "_").replace(" ", "_")
    return p


def validate_mobile_money_startup() -> None:
    mode = (mm_mode() or "sandbox").strip().lower()
    strict = bool(is_strict_startup_validation())

    raw_enabled = enabled_providers() or []
    normalized = [_normalize_provider(p) for p in raw_enabled if (p or "").strip()]
    enabled = sorted(set(normalized))

    logger.info(
        "mobile_money startup check: mode=%s strict=%s enabled_providers=%s",
        mode,
        strict,
        ",".join(enabled) if enabled else "<none>",
    )

    if mode not in ("sandbox", "real"):
        raise RuntimeError(
            "Mobile money startup validation failed. "
            f"Invalid MM_MODE={mode!r}. Allowed: sandbox, real"
        )

    if mode == "sandbox" and not strict:
        return

    if not enabled:
        raise RuntimeError(
            "Mobile money startup validation failed. MM_ENABLED_PROVIDERS is empty."
        )

    unknown = sorted(set(enabled) - ALLOWED_PROVIDERS)
    if unknown:
        raise RuntimeError(
            "Mobile money startup validation failed. Unknown providers in MM_ENABLED_PROVIDERS: "
            f"{_sorted_csv(unknown)}. Allowed: {_sorted_csv(ALLOWED_PROVIDERS)}"
        )

    missing: list[str] = []

    for p in enabled:
        if p == "TMONEY":
            prefix = "TMONEY_REAL_" if mode == "real" else "TMONEY_SANDBOX_"
            _require(missing, prefix + "API_KEY", prefix + "CASHOUT_URL")

        elif p == "FLOOZ":
            prefix = "FLOOZ_REAL_" if mode == "real" else "FLOOZ_SANDBOX_"
            _require(missing, prefix + "API_KEY", prefix + "CASHOUT_URL")

        elif p in {"MTN_MOMO", "MOMO"}:
            prefix = "MOMO_REAL_" if mode == "real" else "MOMO_SANDBOX_"
            _require(
                missing,
                prefix + "BASE_URL",
                prefix + "SUBSCRIPTION_KEY_DISBURSEMENT",
                prefix + "API_USER",
                prefix + "API_KEY",
            )

        elif p == "THUNES":
            prefix = "THUNES_REAL_" if mode == "real" else "THUNES_SANDBOX_"
            # For Thunes v2 you need endpoint + key + secret
            _require(missing, prefix + "API_ENDPOINT", prefix + "API_KEY", prefix + "API_SECRET")

    if missing:
        raise RuntimeError(
            "Mobile money startup validation failed. "
            f"mode={mode} enabled_providers={_sorted_csv(enabled)} "
            "Missing required env vars: " + _sorted_csv(missing)
        )
