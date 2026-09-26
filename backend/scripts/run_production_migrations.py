"""Apply the repository's Alembic head to the configured production database."""

from alembic.config import Config

from alembic import command
from app.core.config import BACKEND_ROOT, Settings, get_settings
from scripts.render_environment import configure_render_database_url


def main() -> None:
    configure_render_database_url()
    get_settings.cache_clear()
    settings = Settings()

    if settings.environment != "production":
        raise RuntimeError("Production migrations require ENVIRONMENT=production")
    if settings.database_url is None:
        raise RuntimeError("Production migrations require a database URL")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    print("Production database migration: PASS")
    print("Alembic upgraded to repository head.")
    print("Database credentials were not printed.")


if __name__ == "__main__":
    main()
