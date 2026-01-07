

# app/providers/mobile_money/validate.py
from __future__ import annotations

import os
from typing import Iterable

from app.providers.mobile_money.config import enabled_providers, is_strict_startup_validation, mm_mode

# Canonical provider keys used internally
ALLOWED_PROVIDERS = {"TMONEY", "FLOOZ", "MTN_MOMO"}


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _require(missing: list[str], *names: str) -> None:
    for n in names:
        if not _env(n):
            missing.append(n)


def _sorted_csv(items: Iterable[str]) -> str:
    return ", ".join(sorted(set(items)))


def validate_mobile_money_startup() -> None:
    """
    Fail-fast validation.

    Rules:
      - sandbox: validate ONLY if MM_STRICT_STARTUP_VALIDATION=1
      - real: always validate
      - validate only enabled providers from MM_ENABLED_PROVIDERS
      - raise RuntimeError listing missing env vars
    """
    mode = (mm_mode() or "sandbox").strip().lower()
    strict = bool(is_strict_startup_validation())

    if mode not in ("sandbox", "real"):
        raise RuntimeError(
            f"Mobile money startup validation failed. "
            f"Invalid MM_MODE={mode!r}. Allowed: sandbox, real"
        )

    # In sandbox, only validate when strict is enabled
    if mode == "sandbox" and not strict:
        return

    enabled = enabled_providers()
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

    for p in sorted(enabled):
        if p == "TMONEY":
            prefix = "TMONEY_REAL_" if mode == "real" else "TMONEY_SANDBOX_"
            _require(missing, prefix + "API_KEY", prefix + "CASHOUT_URL")

        elif p == "FLOOZ":
            prefix = "FLOOZ_REAL_" if mode == "real" else "FLOOZ_SANDBOX_"
            _require(missing, prefix + "API_KEY", prefix + "CASHOUT_URL")

        elif p == "MTN_MOMO":
            prefix = "MOMO_REAL_" if mode == "real" else "MOMO_SANDBOX_"
            _require(
                missing,
                prefix + "BASE_URL",
                prefix + "SUBSCRIPTION_KEY_DISBURSEMENT",
                prefix + "API_USER",
                prefix + "API_KEY",
            )

    if missing:
        raise RuntimeError(
            "Mobile money startup validation failed. Missing required env vars: "
            + _sorted_csv(missing)
        )
