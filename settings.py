

# settings.py
from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent  # settings.py folder
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),  # ✅ absolute path so worker & api behave the same
        extra="ignore",
    )

    # -----------------------
    # Environment
    # -----------------------
    ENV: Literal["dev", "staging", "prod"] = "dev"

    # -----------------------
    # DB
    # -----------------------
    DATABASE_URL: str = Field(...)

    # -----------------------
    # System owner
    # -----------------------
    SYSTEM_OWNER_ID: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))

    # -----------------------
    # JWT
    # -----------------------
    JWT_SECRET: str = Field(default="dev-secret-change-me", min_length=16)
    JWT_ALG: str = Field(default="HS256")
    JWT_ACCESS_MINUTES: int = Field(default=60, ge=1)
    JWT_REFRESH_DAYS: int = Field(default=30, ge=1)

    # -----------------------
    # CORS
    # -----------------------
    CORS_ALLOW_ORIGINS: str = ""

    # -----------------------
    # Velocity limits (fraud/abuse controls)
    # -----------------------
    MAX_CASHOUT_PER_DAY_CENTS: int = 0
    MAX_CASHOUT_COUNT_PER_DAY: int = 0
    MAX_DISTINCT_RECEIVERS_PER_DAY: int = 0
    MAX_CASHIN_PER_DAY_CENTS: int = 0

    # -----------------------
    # Mobile Money (Mode Switch)
    # -----------------------
    MM_MODE: Literal["sandbox", "real"] = "sandbox"
    MM_STRICT_STARTUP_VALIDATION: bool = False
    MM_ENABLED_PROVIDERS: str = "TMONEY,FLOOZ,MTN_MOMO,THUNES"

    # HTTP timeouts
    MM_HTTP_TIMEOUT_S: float = 20.0
    MOMO_HTTP_TIMEOUT_S: float = 20.0

    # -----------------------
    # TMONEY (sandbox/real)
    # -----------------------
    TMONEY_AUTH_MODE: str = "bearer"  # "bearer" or "x-api-key"

    TMONEY_SANDBOX_API_KEY: str = ""
    TMONEY_SANDBOX_CASHOUT_URL: str = ""
    TMONEY_SANDBOX_STATUS_URL_TEMPLATE: str = ""

    TMONEY_REAL_API_KEY: str = ""
    TMONEY_REAL_CASHOUT_URL: str = ""
    TMONEY_REAL_STATUS_URL_TEMPLATE: str = ""

    # Backward-compat
    TMONEY_API_KEY: str = ""
    TMONEY_CASHOUT_URL: str = ""
    TMONEY_STATUS_URL_TEMPLATE: str = ""
    TMONEY_WEBHOOK_SECRET: str = ""

    # -----------------------
    # FLOOZ (sandbox/real)
    # -----------------------
    FLOOZ_AUTH_MODE: str = "bearer"  # "bearer" or "x-api-key"

    FLOOZ_SANDBOX_API_KEY: str = ""
    FLOOZ_SANDBOX_CASHOUT_URL: str = ""
    FLOOZ_SANDBOX_STATUS_URL_TEMPLATE: str = ""

    FLOOZ_REAL_API_KEY: str = ""
    FLOOZ_REAL_CASHOUT_URL: str = ""
    FLOOZ_REAL_STATUS_URL_TEMPLATE: str = ""

    # Backward-compat
    FLOOZ_API_KEY: str = ""
    FLOOZ_CASHOUT_URL: str = ""
    FLOOZ_STATUS_URL_TEMPLATE: str = ""
    FLOOZ_WEBHOOK_SECRET: str = ""

    # -----------------------
    # MTN MOMO (Disbursement) — sandbox/real
    # -----------------------
    MOMO_ENV: str = "sandbox"
    MOMO_TARGET_ENV: str = "sandbox"

    MOMO_SANDBOX_BASE_URL: str = ""
    MOMO_REAL_BASE_URL: str = ""

    MOMO_API_USER_ID: str = ""
    MOMO_DISBURSE_SUB_KEY: str = ""
    MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT: str = ""
    MOMO_SANDBOX_API_USER: str = ""
    MOMO_SANDBOX_API_KEY: str = ""

    MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT: str = ""
    MOMO_REAL_API_USER: str = ""
    MOMO_REAL_API_KEY: str = ""

    MOMO_CALLBACK_URL: str = ""

    # Backward-compat
    MOMO_BASE_URL: str = ""
    MOMO_SUBSCRIPTION_KEY_DISBURSEMENT: str = ""
    MOMO_API_USER: str = ""
    MOMO_API_KEY: str = ""
    MOMO_WEBHOOK_SECRET: str = ""

    # -----------------------
    # THUNES (sandbox/real)
    # -----------------------
    THUNES_SANDBOX_BASE_URL: str = ""
    THUNES_REAL_BASE_URL: str = ""

    THUNES_SANDBOX_API_KEY: str = ""
    THUNES_REAL_API_KEY: str = ""

    THUNES_SANDBOX_TOKEN_URL: str = ""
    THUNES_REAL_TOKEN_URL: str = ""
    THUNES_SANDBOX_CLIENT_ID: str = ""
    THUNES_SANDBOX_CLIENT_SECRET: str = ""
    THUNES_REAL_CLIENT_ID: str = ""
    THUNES_REAL_CLIENT_SECRET: str = ""

    THUNES_WEBHOOK_SECRET: str = ""
    THUNES_ALLOW_UNSIGNED_WEBHOOKS: bool = True

    # -----------------------
    # THUNES (Money Transfer API v2)
    # -----------------------
    THUNES_SANDBOX_API_ENDPOINT: str = ""
    THUNES_SANDBOX_API_KEY: str = ""
    THUNES_SANDBOX_API_SECRET: str = ""

    THUNES_REAL_API_ENDPOINT: str = ""
    THUNES_REAL_API_KEY: str = ""
    THUNES_REAL_API_SECRET: str = ""

    THUNES_USE_SIMULATION: bool = True

    THUNES_PAYER_ID_TG: str = ""
    THUNES_PAYER_ID_BJ: str = ""

    THUNES_TX_TYPE: str = "C2C"
    THUNES_QUOTE_MODE: str = "DESTINATION_AMOUNT"

    THUNES_SOURCE_CURRENCY: str = "USD"
    THUNES_SOURCE_COUNTRY_ISO3: str = "USA"

    THUNES_SENDER_FIRSTNAME: str = "John"
    THUNES_SENDER_LASTNAME: str = "Doe"
    THUNES_SENDER_DOB: str = "1970-01-01"
    THUNES_SENDER_GENDER: str = "MALE"
    THUNES_SENDER_NATIONALITY_ISO3: str = "USA"
    THUNES_SENDER_COUNTRY_OF_BIRTH_ISO3: str = "USA"
    THUNES_SENDER_ADDRESS: str = "42 Main Street"
    THUNES_SENDER_CITY: str = "New York"
    THUNES_SENDER_POSTAL: str = "10001"
    THUNES_SENDER_COUNTRY_ISO3: str = "USA"

    # -----------------------
    # Google sign-in (optional)
    # -----------------------
    GOOGLE_WEB_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""
    GOOGLE_IOS_CLIENT_ID: str = ""


settings = Settings()

# -----------------------
# FX static rates (dev)
# -----------------------
# NOTE: These are dev placeholders for UI/testing. Replace with provider rates.
FX_STATIC_RATES = {
    ("USD", "ZAR"): 18.75,
    ("USD", "NGN"): 1600.0,
    ("USD", "EGP"): 50.0,
    ("USD", "KES"): 155.0,
    ("USD", "GHS"): 12.34,
    ("USD", "XOF"): 610.0,
    ("USD", "XAF"): 610.0,
    ("USD", "MAD"): 10.2,
}


def _normalize_provider(value: str) -> str:
    v = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if v == "MOMO":
        return "MTN_MOMO"
    return v


def _enabled_providers_from_settings() -> set[str]:
    raw = settings.MM_ENABLED_PROVIDERS or ""
    items = [i.strip() for i in raw.split(",") if i.strip()]
    return {_normalize_provider(p) for p in items}


def _missing_if_empty(missing: list[str], name: str, value: str) -> None:
    if not (value or "").strip():
        missing.append(name)


def validate_env_settings() -> None:
    import logging

    logger = logging.getLogger("nexapay")
    env = (settings.ENV or "dev").strip().lower()
    providers = _enabled_providers_from_settings()

    missing: list[str] = []

    # Always required in prod
    if env == "prod":
        _missing_if_empty(missing, "DATABASE_URL", settings.DATABASE_URL)
        if settings.JWT_SECRET == "dev-secret-change-me":
            missing.append("JWT_SECRET")

        if "TMONEY" in providers:
            _missing_if_empty(missing, "TMONEY_WEBHOOK_SECRET", getattr(settings, "TMONEY_WEBHOOK_SECRET", ""))
        if "FLOOZ" in providers:
            _missing_if_empty(missing, "FLOOZ_WEBHOOK_SECRET", getattr(settings, "FLOOZ_WEBHOOK_SECRET", ""))
        if "MTN_MOMO" in providers:
            _missing_if_empty(missing, "MOMO_WEBHOOK_SECRET", getattr(settings, "MOMO_WEBHOOK_SECRET", ""))
        if "THUNES" in providers:
            _missing_if_empty(missing, "THUNES_WEBHOOK_SECRET", settings.THUNES_WEBHOOK_SECRET)
            if settings.THUNES_ALLOW_UNSIGNED_WEBHOOKS:
                missing.append("THUNES_ALLOW_UNSIGNED_WEBHOOKS")
            if settings.MM_MODE == "real":
                _missing_if_empty(missing, "THUNES_REAL_API_ENDPOINT", settings.THUNES_REAL_API_ENDPOINT)
                _missing_if_empty(missing, "THUNES_REAL_API_KEY", settings.THUNES_REAL_API_KEY)
                _missing_if_empty(missing, "THUNES_REAL_API_SECRET", settings.THUNES_REAL_API_SECRET)

        google_any = any(
            [
                settings.GOOGLE_WEB_CLIENT_ID,
                settings.GOOGLE_ANDROID_CLIENT_ID,
                settings.GOOGLE_IOS_CLIENT_ID,
            ]
        )
        if google_any:
            _missing_if_empty(missing, "GOOGLE_WEB_CLIENT_ID", settings.GOOGLE_WEB_CLIENT_ID)
            _missing_if_empty(missing, "GOOGLE_ANDROID_CLIENT_ID", settings.GOOGLE_ANDROID_CLIENT_ID)
            _missing_if_empty(missing, "GOOGLE_IOS_CLIENT_ID", settings.GOOGLE_IOS_CLIENT_ID)

        if missing:
            raise RuntimeError(
                "ENV validation failed for prod. Missing required env vars: "
                + ", ".join(sorted(set(missing)))
            )
        return

    # Dev/staging: warn only
    if settings.JWT_SECRET == "dev-secret-change-me":
        logger.warning("ENV=%s using default JWT_SECRET (not for production).", env)

    if "TMONEY" in providers and not getattr(settings, "TMONEY_WEBHOOK_SECRET", ""):
        logger.warning("ENV=%s missing TMONEY_WEBHOOK_SECRET", env)
    if "FLOOZ" in providers and not getattr(settings, "FLOOZ_WEBHOOK_SECRET", ""):
        logger.warning("ENV=%s missing FLOOZ_WEBHOOK_SECRET", env)
    if "MTN_MOMO" in providers and not getattr(settings, "MOMO_WEBHOOK_SECRET", ""):
        logger.warning("ENV=%s missing MOMO_WEBHOOK_SECRET", env)
    if "THUNES" in providers and not settings.THUNES_WEBHOOK_SECRET:
        logger.warning("ENV=%s missing THUNES_WEBHOOK_SECRET", env)
