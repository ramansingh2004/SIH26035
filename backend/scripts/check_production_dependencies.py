"""Verify live production PostgreSQL and private versioned object storage."""

import asyncio

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import BACKEND_ROOT, Settings, get_settings
from app.db.session import create_database_engine
from app.storage.objects import create_storage
from scripts.render_environment import configure_render_database_url


async def verify() -> None:
    configure_render_database_url()
    get_settings.cache_clear()
    settings = Settings()

    if settings.environment != "production":
        raise RuntimeError("Dependency verification requires ENVIRONMENT=production")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    if expected_head is None:
        raise RuntimeError("Repository has no Alembic head")

    engine = create_database_engine(settings)
    try:
        async with engine.connect() as connection:
            current_head = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if current_head != expected_head:
                raise RuntimeError(
                    "Production database migration does not match repository head"
                )
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()

    storage = create_storage(settings)
    await storage.ready()

    print("Production dependency verification: PASS")
    print(f"- PostgreSQL Alembic head: {expected_head}")
    print("- PostgreSQL connectivity: PASS")
    print("- private versioned object storage: PASS")
    print("- object-storage public access block: PASS")
    print("- credentials were not printed")


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
