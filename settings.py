

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
    JWT_ACCESS_MINUTES: int = Field(default=60)
    JWT_REFRESH_DAYS: int = 30

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

    # -----------------------
    # MTN MOMO (Disbursement) — sandbox/real
    # -----------------------
    MOMO_TARGET_ENV: str = "sandbox"

    MOMO_SANDBOX_BASE_URL: str = ""
    MOMO_REAL_BASE_URL: str = ""

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
