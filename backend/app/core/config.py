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
    storage_provider: Literal["minio", "s3"] = "minio"
    storage_endpoint: str | None = None
    storage_bucket: str | None = None
    storage_region: str = "us-east-1"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_url_seconds: int = Field(default=300, ge=30, le=900)
    report_preview_hours: int = Field(default=24, ge=1, le=168)

    @model_validator(mode="after")
    def storage_security(self):
        if self.storage_endpoint:
            from urllib.parse import urlsplit

            url = urlsplit(self.storage_endpoint)
            if (
                url.username
                or url.password
                or url.query
                or url.fragment
                or url.path not in ("", "/")
            ):
                raise ValueError("Storage endpoint must be an origin without credentials")
            if url.scheme != "https" and not (
                self.environment != "production"
                and url.scheme == "http"
                and url.hostname in ("localhost", "127.0.0.1", "::1")
            ):
                raise ValueError("Storage requires HTTPS except development loopback")
        return self

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
