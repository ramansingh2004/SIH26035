"""Environment-backed bootstrap settings without connection side effects."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "SIH26035 API"
    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "sih26035"
    jwt_audience: str = "sih26035-api"
    access_token_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    refresh_family_days: int = Field(default=30, ge=1, le=90)
    cookie_secure: bool = True
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    login_limit: int = Field(default=10, ge=1, le=1000)
    login_window_seconds: int = Field(default=300, ge=1, le=3600)

    def signing_key(self) -> str:
        if self.jwt_secret is None:
            raise RuntimeError("Set JWT_SECRET before using authentication")
        return self.jwt_secret.get_secret_value()

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if self.jwt_secret is not None and len(self.jwt_secret.get_secret_value().encode()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        if self.environment == "production":
            if not self.cookie_secure or self.jwt_secret is None or self.database_url is None:
                raise ValueError("Production requires database, signing key and secure cookies")
            if not self.allowed_origins or any(
                not o.startswith("https://") for o in self.allowed_origins
            ):
                raise ValueError("Production requires explicit HTTPS origins")
        return self

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL asyncpg URL") from None
        if url.drivername != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
