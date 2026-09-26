"""Production entrypoint for the SIH26035 Render web service."""

import os

import uvicorn

from app.core.config import Settings, get_settings
from scripts.render_environment import configure_render_database_url


def render_port() -> int:
    raw = os.environ.get("PORT", "10000")
    try:
        port = int(raw)
    except ValueError as error:
        raise RuntimeError("PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")
    return port


def prepare_environment() -> Settings:
    configure_render_database_url()
    get_settings.cache_clear()
    settings = Settings()
    if settings.environment != "production":
        raise RuntimeError("Render entrypoint requires ENVIRONMENT=production")
    return settings


def main() -> None:
    prepare_environment()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=render_port(),
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
