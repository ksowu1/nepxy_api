
# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from uuid import UUID

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # DB
    DATABASE_URL: str = Field(...)

    # System owner
    SYSTEM_OWNER_ID: UUID = Field(default=UUID("00000000-0000-0000-0000-000000000001"))

    # JWT
    JWT_SECRET: str = Field(default="dev-secret-change-me", min_length=16)
    JWT_ALG: str = Field(default="HS256")
    JWT_ACCESS_MINUTES: int = Field(default=60)

settings = Settings()
