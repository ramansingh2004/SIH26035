"""Local trusted provisioning, not a public registration endpoint."""

import argparse
import asyncio
import getpass

from pydantic import EmailStr, TypeAdapter

from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.provisioning import ProvisioningService


async def run(args):
    engine = create_database_engine(get_settings())
    try:
        async with create_session_factory(engine)() as session:
            service = ProvisioningService(session)
            if args.command == "seed":
                print(f"Inserted catalog rows: {await service.seed()}")
            else:
                email = str(
                    TypeAdapter(EmailStr).validate_python(
                        (await asyncio.to_thread(input, "Admin email: ")).strip()
                    )
                )
                name = (await asyncio.to_thread(input, "Full name: ")).strip()
                if not 1 <= len(name) <= 200:
                    raise ValueError("Full name must contain 1–200 characters")
                password = await asyncio.to_thread(
                    getpass.getpass, "Password (12–128 characters): "
                )
                if password != await asyncio.to_thread(getpass.getpass, "Confirm password: "):
                    raise ValueError("Passwords did not match")
                identifier = await service.bootstrap(email, name, password)
                print(f"Created global administrator: {identifier}")
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed", "bootstrap-admin"])
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
