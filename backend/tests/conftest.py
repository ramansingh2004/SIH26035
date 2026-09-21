"""Real PostgreSQL is required. Missing configuration fails; it never skips gates."""

import os
import secrets
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.models import Laboratory, Role, User, UserRoleAssignment
from app.services.provisioning import ProvisioningService


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not make_url(url).database.endswith("_test"):
        pytest.fail("Set TEST_DATABASE_URL to an isolated real PostgreSQL database ending in _test")
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    from app.core.config import get_settings

    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    if old is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old
    get_settings.cache_clear()
    return url


@pytest_asyncio.fixture
async def world(database_url):
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        jwt_secret=secrets.token_urlsafe(48),
        cookie_secure=True,
        allowed_origins=["https://test.local"],
        login_limit=1000,
    )
    password = secrets.token_urlsafe(24)
    encoded = hash_password(password)
    async with factory() as session:
        await ProvisioningService(session).seed()
        async with session.begin():
            roles = {r.code: r.id for r in (await session.scalars(select(Role))).all()}
            admin = User(
                id=uuid4(),
                email=f"{uuid4().hex}@example.com",
                full_name="Global Admin",
                password_hash=encoded,
            )
            session.add(admin)
            await session.flush()
            labs = []
            for n in range(2):
                lab = Laboratory(
                    id=uuid4(),
                    code=uuid4().hex,
                    name=f"Lab {n}",
                    address_line1="Address",
                    address_line2="",
                    city="City",
                    state="State",
                    postal_code="100001",
                    country="India",
                    phone="0000000000",
                    email="lab@example.com",
                    accreditation_no="TEST",
                    created_by=admin.id,
                )
                session.add(lab)
                labs.append(lab)
            await session.flush()
            session.add(
                UserRoleAssignment(
                    user_id=admin.id,
                    role_id=roles["ADMIN"],
                    scope_type="GLOBAL",
                    assigned_by=admin.id,
                )
            )
            users = {"admin": admin}
            for name, role, lab in [
                ("viewer", "VIEWER", labs[0]),
                ("other", "VIEWER", labs[1]),
                ("local", "ADMIN", labs[0]),
                ("officer", "APPROVING_OFFICER", labs[0]),
            ]:
                user = User(
                    id=uuid4(),
                    email=f"{uuid4().hex}@example.com",
                    full_name=name,
                    password_hash=encoded,
                    created_by=admin.id,
                )
                session.add(user)
                await session.flush()
                session.add(
                    UserRoleAssignment(
                        user_id=user.id,
                        role_id=roles[role],
                        scope_type="LABORATORY",
                        laboratory_id=lab.id,
                        assigned_by=admin.id,
                    )
                )
                users[name] = user
    app = create_app(settings)
    await app.state.engine.dispose()
    app.state.engine = engine
    app.state.session_factory = factory
    result = SimpleNamespace(
        engine=engine,
        factory=factory,
        settings=settings,
        app=app,
        password=password,
        users=users,
        labs=labs,
        roles=roles,
    )
    try:
        yield result
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(world):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=world.app, client=("test-" + uuid4().hex, 123)),
        base_url="https://test.local",
        headers={"Origin": "https://test.local"},
    ) as client:
        yield client


async def login(client, world, name="admin"):
    response = await client.post(
        "/api/v1/auth/login", json={"email": world.users[name].email, "password": world.password}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    client.headers["Authorization"] = "Bearer " + token
    client.headers["X-CSRF-Token"] = client.cookies["sih_csrf"]
    return response
