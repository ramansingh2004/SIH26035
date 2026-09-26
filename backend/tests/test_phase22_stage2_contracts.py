"""Phase 22 Stage 2 deployment-boundary contracts; no live cloud access."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from scripts.render_environment import normalize_render_database_url

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("supplied", "expected_prefix"),
    [
        (
            "postgresql://user:pass@db.internal:5432/sih26035",
            "postgresql+asyncpg://",
        ),
        (
            "postgres://user:pass@db.internal:5432/sih26035",
            "postgresql+asyncpg://",
        ),
        (
            "postgresql+asyncpg://user:pass@db.internal:5432/sih26035",
            "postgresql+asyncpg://",
        ),
    ],
)
def test_render_database_boundary_normalizes_postgres_urls(
    supplied: str, expected_prefix: str
) -> None:
    normalized = normalize_render_database_url(supplied)
    assert normalized.startswith(expected_prefix)
    assert "db.internal" in normalized
    assert normalized.endswith("/sih26035")


def test_render_database_boundary_rejects_non_postgres() -> None:
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        normalize_render_database_url("sqlite:///tmp.db")


def test_application_still_rejects_raw_sync_postgresql_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql://user:pass@localhost/db",
        )


def test_stage2_keeps_migrations_out_of_fastapi_startup() -> None:
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "alembic" not in main.lower()

    migration = (
        ROOT / "backend/scripts/run_production_migrations.py"
    ).read_text(encoding="utf-8")
    assert 'command.upgrade(config, "head")' in migration


def test_live_dependency_check_verifies_db_head_and_storage_privacy() -> None:
    check = (
        ROOT / "backend/scripts/check_production_dependencies.py"
    ).read_text(encoding="utf-8")
    assert "alembic_version" in check
    assert "get_current_head" in check
    assert "storage.ready()" in check


def test_s3_runtime_policy_is_scoped_to_the_application_bucket() -> None:
    policy = (
        ROOT / "deploy/aws/s3-runtime-policy.json.example"
    ).read_text(encoding="utf-8")
    assert '"s3:GetBucketVersioning"' in policy
    assert '"s3:GetBucketPublicAccessBlock"' in policy
    assert '"s3:ListBucketVersions"' in policy
    assert '"s3:PutObject"' in policy
    assert '"s3:GetObjectVersion"' in policy
    assert '"s3:DeleteObjectVersion"' in policy
    assert '"Resource": "arn:aws:s3:::REPLACE_BUCKET_NAME"' in policy
    assert '"Resource": "arn:aws:s3:::REPLACE_BUCKET_NAME/*"' in policy
    assert '"Resource": "*"' not in policy
