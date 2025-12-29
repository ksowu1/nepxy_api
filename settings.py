

# settings.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from uuid import UUID
from typing import Literal



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # -----------------------
    # Mobile Money (Mode Switch)
    # -----------------------
    MM_MODE: Literal["sandbox", "real"] = "sandbox"
    MM_STRICT_STARTUP_VALIDATION: bool = False
    MM_ENABLED_PROVIDERS: str = "TMONEY,FLOOZ,MTN_MOMO"

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

    # Backward-compat (older single-key config)
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
    # MTN MOMO (sandbox/real)
    # -----------------------
    # target env used by MoMo headers: "sandbox" or "production"
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

    GOOGLE_WEB_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""
    GOOGLE_IOS_CLIENT_ID: str = ""
    JWT_REFRESH_DAYS: int = 30



settings = Settings()
