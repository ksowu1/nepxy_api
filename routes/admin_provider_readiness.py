from __future__ import annotations

from fastapi import APIRouter, Depends

from deps.admin import require_admin
from app.providers.mobile_money.config import provider_enabled
from settings import settings


router = APIRouter(prefix="/v1/admin", tags=["admin", "providers"])


def _missing_if_empty(missing: list[str], name: str, value: str | None) -> None:
    if not (value or "").strip():
        missing.append(name)


def _missing_if_all_empty(missing: list[str], name: str, *values: str | None) -> None:
    for v in values:
        if (v or "").strip():
            return
    missing.append(name)


def _tmoney_missing(mode: str) -> list[str]:
    missing: list[str] = []
    _missing_if_empty(missing, "TMONEY_WEBHOOK_SECRET", settings.TMONEY_WEBHOOK_SECRET)
    if mode == "real":
        _missing_if_all_empty(missing, "TMONEY_REAL_API_KEY", settings.TMONEY_REAL_API_KEY, settings.TMONEY_API_KEY)
        _missing_if_all_empty(
            missing, "TMONEY_REAL_CASHOUT_URL", settings.TMONEY_REAL_CASHOUT_URL, settings.TMONEY_CASHOUT_URL
        )
    else:
        _missing_if_all_empty(missing, "TMONEY_SANDBOX_API_KEY", settings.TMONEY_SANDBOX_API_KEY, settings.TMONEY_API_KEY)
        _missing_if_all_empty(
            missing, "TMONEY_SANDBOX_CASHOUT_URL", settings.TMONEY_SANDBOX_CASHOUT_URL, settings.TMONEY_CASHOUT_URL
        )
    return missing


def _flooz_missing(mode: str) -> list[str]:
    missing: list[str] = []
    _missing_if_empty(missing, "FLOOZ_WEBHOOK_SECRET", settings.FLOOZ_WEBHOOK_SECRET)
    if mode == "real":
        _missing_if_all_empty(missing, "FLOOZ_REAL_API_KEY", settings.FLOOZ_REAL_API_KEY, settings.FLOOZ_API_KEY)
        _missing_if_all_empty(
            missing, "FLOOZ_REAL_CASHOUT_URL", settings.FLOOZ_REAL_CASHOUT_URL, settings.FLOOZ_CASHOUT_URL
        )
    else:
        _missing_if_all_empty(missing, "FLOOZ_SANDBOX_API_KEY", settings.FLOOZ_SANDBOX_API_KEY, settings.FLOOZ_API_KEY)
        _missing_if_all_empty(
            missing, "FLOOZ_SANDBOX_CASHOUT_URL", settings.FLOOZ_SANDBOX_CASHOUT_URL, settings.FLOOZ_CASHOUT_URL
        )
    return missing


def _momo_missing(mode: str) -> list[str]:
    missing: list[str] = []
    _missing_if_empty(missing, "MOMO_WEBHOOK_SECRET", settings.MOMO_WEBHOOK_SECRET)
    if mode == "real":
        _missing_if_all_empty(missing, "MOMO_REAL_BASE_URL", settings.MOMO_REAL_BASE_URL, settings.MOMO_BASE_URL)
        _missing_if_all_empty(
            missing,
            "MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT",
            settings.MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT,
            settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT,
        )
        _missing_if_all_empty(missing, "MOMO_REAL_API_USER", settings.MOMO_REAL_API_USER, settings.MOMO_API_USER)
        _missing_if_all_empty(missing, "MOMO_REAL_API_KEY", settings.MOMO_REAL_API_KEY, settings.MOMO_API_KEY)
    else:
        _missing_if_all_empty(missing, "MOMO_SANDBOX_BASE_URL", settings.MOMO_SANDBOX_BASE_URL, settings.MOMO_BASE_URL)
        _missing_if_all_empty(
            missing,
            "MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT",
            settings.MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT,
            settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT,
        )
        _missing_if_all_empty(missing, "MOMO_SANDBOX_API_USER", settings.MOMO_SANDBOX_API_USER, settings.MOMO_API_USER)
        _missing_if_all_empty(missing, "MOMO_SANDBOX_API_KEY", settings.MOMO_SANDBOX_API_KEY, settings.MOMO_API_KEY)
    return missing


def _thunes_missing(mode: str) -> list[str]:
    missing: list[str] = []
    _missing_if_empty(missing, "THUNES_WEBHOOK_SECRET", settings.THUNES_WEBHOOK_SECRET)
    _missing_if_empty(missing, "THUNES_PAYER_ID_GH", settings.THUNES_PAYER_ID_GH)
    if mode == "real":
        _missing_if_empty(missing, "THUNES_REAL_API_ENDPOINT", settings.THUNES_REAL_API_ENDPOINT)
        _missing_if_empty(missing, "THUNES_REAL_API_KEY", settings.THUNES_REAL_API_KEY)
        _missing_if_empty(missing, "THUNES_REAL_API_SECRET", settings.THUNES_REAL_API_SECRET)
    else:
        _missing_if_empty(missing, "THUNES_SANDBOX_API_ENDPOINT", settings.THUNES_SANDBOX_API_ENDPOINT)
        _missing_if_empty(missing, "THUNES_SANDBOX_API_KEY", settings.THUNES_SANDBOX_API_KEY)
        _missing_if_empty(missing, "THUNES_SANDBOX_API_SECRET", settings.THUNES_SANDBOX_API_SECRET)
    return missing


@router.get("/provider-readiness")
def provider_readiness(_admin=Depends(require_admin)):
    mode = (settings.MM_MODE or "sandbox").strip().lower()

    def _row(provider: str, missing_fn):
        enabled = bool(provider_enabled(provider))
        missing = missing_fn(mode) if enabled else []
        return {
            "enabled": enabled,
            "missing": missing,
            "webhooks_enabled": enabled,
            "worker_enabled": enabled,
        }

    return {
        "mode": mode,
        "providers": {
            "TMONEY": _row("TMONEY", _tmoney_missing),
            "FLOOZ": _row("FLOOZ", _flooz_missing),
            "MOMO": _row("MOMO", _momo_missing),
            "THUNES": _row("THUNES", _thunes_missing),
        },
    }
