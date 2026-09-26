"""Render boundary adapters. Application configuration remains provider-agnostic."""

import os

from sqlalchemy.engine import make_url

from app.core.config import get_settings


def normalize_render_database_url(value: str) -> str:
    """Convert Render's standard PostgreSQL URL to the app's asyncpg URL."""
    url = make_url(value)
    if url.drivername == "postgresql+asyncpg":
        return url.render_as_string(hide_password=False)
    if url.drivername not in {"postgres", "postgresql"}:
        raise RuntimeError("Render database URL must be PostgreSQL")
    return url.set(drivername="postgresql+asyncpg").render_as_string(
        hide_password=False
    )


def configure_render_database_url() -> bool:
    """Install Render's managed DB URL as DATABASE_URL without logging secrets.

    Returns True when RENDER_DATABASE_URL was present and DATABASE_URL was set.
    Outside Render this is a no-op so local .env configuration keeps working.
    """
    value = os.environ.get("RENDER_DATABASE_URL")
    if not value:
        return False
    os.environ["DATABASE_URL"] = normalize_render_database_url(value)
    get_settings.cache_clear()
    return True
