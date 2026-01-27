

# app/providers/mobile_money/config.py
from __future__ import annotations

from dataclasses import dataclass

from settings import settings


def mm_mode() -> str:
    # ✅ always reflect .env via pydantic settings
    return (settings.MM_MODE or "sandbox").strip().lower()


def is_strict_startup_validation() -> bool:
    return bool(settings.MM_STRICT_STARTUP_VALIDATION)


def _normalize_provider(value: str) -> str:
    v = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if v == "MOMO":
        return "MTN_MOMO"
    return v


def _raw_enabled_providers() -> set[str]:
    raw = settings.MM_ENABLED_PROVIDERS or ""
    return {_normalize_provider(p) for p in raw.split(",") if p.strip()}


def provider_enabled(provider: str) -> bool:
    normalized = _normalize_provider(provider)
    providers = _raw_enabled_providers()
    if normalized not in providers:
        return False
    if normalized == "TMONEY":
        return bool(settings.TMONEY_ENABLED)
    if normalized == "FLOOZ":
        return bool(settings.FLOOZ_ENABLED)
    if normalized == "MTN_MOMO":
        return bool(settings.MOMO_ENABLED)
    if normalized == "THUNES":
        return bool(settings.THUNES_ENABLED)
    return False


def enabled_providers() -> set[str]:
    return {p for p in _raw_enabled_providers() if provider_enabled(p)}


@dataclass(frozen=True)
class ProviderConfig:
    mode: str  # "sandbox" | "real"
    cashout_url: str
    status_url_template: str
    api_key: str
    auth_mode: str


def tmoney_config() -> ProviderConfig:
    mode = mm_mode()
    if mode == "real":
        return ProviderConfig(
            mode=mode,
            cashout_url=(settings.TMONEY_REAL_CASHOUT_URL or settings.TMONEY_CASHOUT_URL or "").strip(),
            status_url_template=(settings.TMONEY_REAL_STATUS_URL_TEMPLATE or settings.TMONEY_STATUS_URL_TEMPLATE or "").strip(),
            api_key=(settings.TMONEY_REAL_API_KEY or settings.TMONEY_API_KEY or "").strip(),
            auth_mode=(settings.TMONEY_AUTH_MODE or "bearer").strip().lower(),
        )
    return ProviderConfig(
        mode=mode,
        cashout_url=(settings.TMONEY_SANDBOX_CASHOUT_URL or settings.TMONEY_CASHOUT_URL or "").strip(),
        status_url_template=(settings.TMONEY_SANDBOX_STATUS_URL_TEMPLATE or settings.TMONEY_STATUS_URL_TEMPLATE or "").strip(),
        api_key=(settings.TMONEY_SANDBOX_API_KEY or settings.TMONEY_API_KEY or "").strip(),
        auth_mode=(settings.TMONEY_AUTH_MODE or "bearer").strip().lower(),
    )


def flooz_config() -> ProviderConfig:
    mode = mm_mode()
    if mode == "real":
        return ProviderConfig(
            mode=mode,
            cashout_url=(settings.FLOOZ_REAL_CASHOUT_URL or settings.FLOOZ_CASHOUT_URL or "").strip(),
            status_url_template=(settings.FLOOZ_REAL_STATUS_URL_TEMPLATE or settings.FLOOZ_STATUS_URL_TEMPLATE or "").strip(),
            api_key=(settings.FLOOZ_REAL_API_KEY or settings.FLOOZ_API_KEY or "").strip(),
            auth_mode=(settings.FLOOZ_AUTH_MODE or "bearer").strip().lower(),
        )
    return ProviderConfig(
        mode=mode,
        cashout_url=(settings.FLOOZ_SANDBOX_CASHOUT_URL or settings.FLOOZ_CASHOUT_URL or "").strip(),
        status_url_template=(settings.FLOOZ_SANDBOX_STATUS_URL_TEMPLATE or settings.FLOOZ_STATUS_URL_TEMPLATE or "").strip(),
        api_key=(settings.FLOOZ_SANDBOX_API_KEY or settings.FLOOZ_API_KEY or "").strip(),
        auth_mode=(settings.FLOOZ_AUTH_MODE or "bearer").strip().lower(),
    )


@dataclass(frozen=True)
class MomoConfig:
    mode: str
    base_url: str
    target_env: str
    subscription_key: str
    api_user: str
    api_key: str
    callback_url: str


def momo_config() -> MomoConfig:
    mode = mm_mode()
    if mode == "real":
        base = (settings.MOMO_REAL_BASE_URL or settings.MOMO_BASE_URL or "").strip()
        sub = (settings.MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT or settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT or "").strip()
        usr = (settings.MOMO_REAL_API_USER or settings.MOMO_API_USER or "").strip()
        key = (settings.MOMO_REAL_API_KEY or settings.MOMO_API_KEY or "").strip()
        target = "production"
    else:
        base = (settings.MOMO_SANDBOX_BASE_URL or settings.MOMO_BASE_URL or "").strip()
        sub = (settings.MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT or settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT or "").strip()
        usr = (settings.MOMO_SANDBOX_API_USER or settings.MOMO_API_USER or "").strip()
        key = (settings.MOMO_SANDBOX_API_KEY or settings.MOMO_API_KEY or "").strip()
        target = "sandbox"

    return MomoConfig(
        mode=mode,
        base_url=base.rstrip("/"),
        target_env=(settings.MOMO_TARGET_ENV or target).strip(),
        subscription_key=sub,
        api_user=usr,
        api_key=key,
        callback_url=(settings.MOMO_CALLBACK_URL or "").strip(),
    )
