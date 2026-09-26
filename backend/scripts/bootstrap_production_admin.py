"""One-time production administrator bootstrap using the external Render DB URL.

This script is intentionally database-side because a fresh production database has no
authenticated actor yet. It uses the existing ProvisioningService so role seeding,
password hashing, locking and audit behavior remain authoritative.
"""

import asyncio
import getpass
import os

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import create_database_engine, create_session_factory
from app.services.provisioning import ProvisioningService
from scripts.render_environment import normalize_render_database_url


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name}")
    return value


async def bootstrap() -> None:
    external_url = required("RENDER_DATABASE_URL")
    email = required("PRODUCTION_ADMIN_EMAIL")
    name = os.environ.get("PRODUCTION_ADMIN_NAME", "Production administrator").strip()
    if not name:
        raise RuntimeError("PRODUCTION_ADMIN_NAME must not be empty")

    password = getpass.getpass("Production administrator password: ")
    confirmation = getpass.getpass("Confirm production administrator password: ")

    if password != confirmation:
        raise RuntimeError("Passwords do not match")
    if not 12 <= len(password) <= 128:
        raise RuntimeError("Password must contain 12-128 characters")

    # Bootstrap needs only a database connection. The deployed application still uses
    # ENVIRONMENT=production and the full production Settings validation.
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=normalize_render_database_url(external_url),
    )
    engine = create_database_engine(settings)

    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            try:
                user_id = await ProvisioningService(session).bootstrap(
                    email,
                    name,
                    password,
                )
            except AppError as error:
                if error.code == "ADMIN_EXISTS":
                    print("Production administrator bootstrap: ALREADY PRESENT")
                    print("No database changes were made.")
                    return
                raise
    finally:
        await engine.dispose()

    print("Production administrator bootstrap: PASS")
    print(f"- administrator user id: {user_id}")
    print("- permission catalog seeded")
    print("- global ADMIN assignment created")
    print("- bootstrap audit event created")
    print("- password and database credentials were not printed")


def main() -> None:
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()
