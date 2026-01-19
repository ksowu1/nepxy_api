

# app/providers/mobile_money/mtn_momo.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Any

from app.providers.base import ProviderResult, MobileMoneyProvider
from app.providers.mobile_money.config import mm_mode, momo_config
from settings import settings


@dataclass(frozen=True)
class MomoCountryConfig:
    country: str
    mode: str
    base_url: str
    target_env: str
    subscription_key: str
    api_user: str
    api_key: str
    callback_url: str
    webhook_secret: str
    token_url: str
    transfer_url: str
    status_url_template: str
    missing: list[str]


def _normalize(value: str | None) -> str:
    return (value or "").strip().upper()


def _country_env(country: str, key: str) -> str:
    name = f"MOMO_{country}_{key}"
    return (os.getenv(name) or "").strip()


def _fallback_momo_config(mode: str) -> dict[str, str]:
    cfg = momo_config()
    if mode == "real":
        return {
            "base_url": (settings.MOMO_REAL_BASE_URL or settings.MOMO_BASE_URL or "").strip(),
            "subscription_key": (settings.MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT or settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT or "").strip(),
            "api_user": (settings.MOMO_REAL_API_USER or settings.MOMO_API_USER or "").strip(),
            "api_key": (settings.MOMO_REAL_API_KEY or settings.MOMO_API_KEY or "").strip(),
            "target_env": (settings.MOMO_TARGET_ENV or "production").strip(),
        }
    return {
        "base_url": (settings.MOMO_SANDBOX_BASE_URL or settings.MOMO_BASE_URL or "").strip(),
        "subscription_key": (settings.MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT or settings.MOMO_SUBSCRIPTION_KEY_DISBURSEMENT or "").strip(),
        "api_user": (settings.MOMO_SANDBOX_API_USER or settings.MOMO_API_USER or "").strip(),
        "api_key": (settings.MOMO_SANDBOX_API_KEY or settings.MOMO_API_KEY or "").strip(),
        "target_env": (settings.MOMO_TARGET_ENV or "sandbox").strip(),
    }


def _momo_country_config(country: str) -> MomoCountryConfig:
    mode = mm_mode()
    normalized = _normalize(country)
    suffix = "REAL" if mode == "real" else "SANDBOX"
    fallback = _fallback_momo_config(mode)

    base_url = _country_env(normalized, f"{suffix}_BASE_URL") or fallback["base_url"]
    subscription_key = _country_env(normalized, f"{suffix}_SUBSCRIPTION_KEY_DISBURSEMENT") or fallback["subscription_key"]
    api_user = _country_env(normalized, f"{suffix}_API_USER") or fallback["api_user"]
    api_key = _country_env(normalized, f"{suffix}_API_KEY") or fallback["api_key"]
    target_env = _country_env(normalized, "TARGET_ENV") or fallback["target_env"]
    callback_url = _country_env(normalized, "CALLBACK_URL") or (settings.MOMO_CALLBACK_URL or "").strip()
    webhook_secret = _country_env(normalized, "WEBHOOK_SECRET") or (settings.MOMO_WEBHOOK_SECRET or "").strip()

    base_url = base_url.rstrip("/")
    token_url = f"{base_url}/disbursement/token/" if base_url else ""
    transfer_url = f"{base_url}/disbursement/v1_0/transfer" if base_url else ""
    status_url_template = (
        f"{base_url}/disbursement/v1_0/transfer/{{provider_ref}}" if base_url else ""
    )

    missing: list[str] = []
    if not base_url:
        missing.append(f"MOMO_{normalized}_{suffix}_BASE_URL")
    if not subscription_key:
        missing.append(f"MOMO_{normalized}_{suffix}_SUBSCRIPTION_KEY_DISBURSEMENT")
    if not api_user:
        missing.append(f"MOMO_{normalized}_{suffix}_API_USER")
    if not api_key:
        missing.append(f"MOMO_{normalized}_{suffix}_API_KEY")
    if not webhook_secret:
        missing.append(f"MOMO_{normalized}_WEBHOOK_SECRET")

    return MomoCountryConfig(
        country=normalized,
        mode=mode,
        base_url=base_url,
        target_env=target_env,
        subscription_key=subscription_key,
        api_user=api_user,
        api_key=api_key,
        callback_url=callback_url,
        webhook_secret=webhook_secret,
        token_url=token_url,
        transfer_url=transfer_url,
        status_url_template=status_url_template,
        missing=missing,
    )


class MtnMomoProvider(MobileMoneyProvider):
    def __init__(self, *_: Any, **__: Any):
        pass

    def send_cashout(self, payout: dict) -> ProviderResult:
        country = _normalize(payout.get("country"))
        cfg = _momo_country_config(country)
        missing = cfg.missing
        if missing:
            # TODO(MTN_MOMO): supply country-specific credentials in env vars.
            return ProviderResult(
                status="FAILED",
                error="MOMO_CREDENTIALS_MISSING",
                response={"missing": missing},
                retryable=False,
            )

        phone = (payout.get("phone_e164") or "").strip()
        amount_cents = payout.get("amount_cents")
        currency = (payout.get("currency") or "").strip().upper()

        if not phone:
            return ProviderResult(status="FAILED", error="Missing phone_e164", retryable=False)
        if not currency:
            return ProviderResult(status="FAILED", error="Missing currency", retryable=False)
        if amount_cents is None or int(amount_cents) <= 0:
            return ProviderResult(status="FAILED", error="Missing/invalid amount_cents", retryable=False)

        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id"))

        # TODO(MTN_MOMO): replace stub with real API call once credentials and callbacks are ready.
        response = {
            "stub": True,
            "mode": cfg.mode,
            "country": cfg.country,
            "transfer_url": cfg.transfer_url,
            "status_poll_url": cfg.status_url_template.format(provider_ref=provider_ref),
            "callback_url": cfg.callback_url,
            "webhook_secret_configured": bool(cfg.webhook_secret),
            "currency": currency,
        }
        return ProviderResult(status="SENT", provider_ref=provider_ref, response=response, retryable=True)

    def get_cashout_status(self, payout: dict) -> ProviderResult:
        country = _normalize(payout.get("country"))
        cfg = _momo_country_config(country)
        provider_ref = str(payout.get("provider_ref") or payout.get("id") or payout.get("transaction_id"))

        if cfg.missing:
            # TODO(MTN_MOMO): supply country-specific credentials for status polling.
            return ProviderResult(
                status="SENT",
                provider_ref=provider_ref,
                error="MOMO_CREDENTIALS_MISSING",
                response={"missing": cfg.missing, "status_poll_url": cfg.status_url_template},
                retryable=True,
            )

        response = {
            "stub": True,
            "mode": cfg.mode,
            "country": cfg.country,
            "status_poll_url": cfg.status_url_template.format(provider_ref=provider_ref),
        }
        return ProviderResult(status="SENT", provider_ref=provider_ref, response=response, retryable=True)

    def webhook_event_to_status(self, payload: dict) -> Optional[str]:
        status = _normalize(payload.get("status") or payload.get("financialTransactionStatus"))
        if status in ("SUCCESSFUL", "SUCCESS", "COMPLETED"):
            return "CONFIRMED"
        if status in ("FAILED", "REJECTED", "CANCELLED"):
            return "FAILED"
        return None

    def verify_webhook_signature(self, headers: dict, raw_body: str, country: str) -> bool:
        cfg = _momo_country_config(country)
        if not cfg.webhook_secret:
            # TODO(MTN_MOMO): configure MOMO_<COUNTRY>_WEBHOOK_SECRET for verification.
            return False
        # TODO(MTN_MOMO): implement HMAC verification once MTN signature spec is confirmed.
        return False
