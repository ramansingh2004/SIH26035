"""Phase 0 startup/health/configuration tests; no regulatory fixtures."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.main import create_app


def test_health_is_public_and_starts_without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None, environment="test")
    assert settings.database_url is None
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_preserved_and_no_phase_four_endpoints() -> None:
    settings = Settings(_env_file=None, environment="test", database_url=None)
    paths = set(create_app(settings).openapi()["paths"])
    assert "/health" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/instruments" in paths
    assert "/api/v1/rulesets" in paths
    assert not any("test-session" in path or "evaluate" in path for path in paths)
    assert "instruments" in Base.metadata.tables
    assert "test_sessions" not in Base.metadata.tables


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Bootstrap test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    settings = Settings(_env_file=None, database_url=None)
    assert settings.app_name == "Bootstrap test"
    assert settings.environment == "test"


@pytest.mark.parametrize("url", ["sqlite:///test.db", "postgresql://localhost/test", "invalid"])
def test_database_configuration_requires_asyncpg(url: str) -> None:
    with pytest.raises(ValidationError, match="PostgreSQL asyncpg|postgresql\\+asyncpg"):
        Settings(_env_file=None, database_url=url)


def test_async_database_factories_do_not_require_a_live_database() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://example:example@127.0.0.1:1/example",
    )
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    assert engine.dialect.driver == "asyncpg"
    assert factory.kw["expire_on_commit"] is False
    asyncio.run(engine.dispose())


def test_database_factory_requires_explicit_configuration() -> None:
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        create_database_engine(Settings(_env_file=None, database_url=None))
