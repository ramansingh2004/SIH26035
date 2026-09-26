"""Fail-safe production configuration preflight without printing secrets."""

from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from scripts.render_environment import configure_render_database_url


def main() -> None:
    configure_render_database_url()
    get_settings.cache_clear()
    settings = Settings()
    errors: list[str] = []

    if settings.environment != "production":
        errors.append("ENVIRONMENT must be production")

    if settings.database_url is None:
        errors.append("DATABASE_URL or RENDER_DATABASE_URL is required")
    else:
        url = make_url(settings.database_url.get_secret_value())
        if url.drivername != "postgresql+asyncpg":
            errors.append("Effective DATABASE_URL must use postgresql+asyncpg")

    if settings.jwt_secret is None:
        errors.append("JWT_SECRET is required")

    if not settings.cookie_secure:
        errors.append("COOKIE_SECURE must be true")

    if not settings.allowed_origins:
        errors.append("ALLOWED_ORIGINS must contain the deployed frontend origin")
    elif any(not origin.startswith("https://") for origin in settings.allowed_origins):
        errors.append("Every ALLOWED_ORIGINS entry must use HTTPS")

    if settings.storage_provider != "s3":
        errors.append("Production deployment target requires STORAGE_PROVIDER=s3")

    if not settings.storage_bucket:
        errors.append("STORAGE_BUCKET is required")

    if settings.storage_access_key is None:
        errors.append("STORAGE_ACCESS_KEY is required")

    if settings.storage_secret_key is None:
        errors.append("STORAGE_SECRET_KEY is required")

    if errors:
        print("Production configuration: FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Production configuration: PASS")
    print(f"- environment: {settings.environment}")
    print("- database: configured with postgresql+asyncpg")
    print("- JWT secret: configured")
    print(f"- secure cookies: {settings.cookie_secure}")
    print(f"- allowed HTTPS origins: {len(settings.allowed_origins)}")
    print(f"- storage provider: {settings.storage_provider}")
    print("- storage bucket: configured")
    print("- storage credentials: configured")
    print("- secrets were not printed")


if __name__ == "__main__":
    main()
