"""Phase 15 Stage 1 real PostgreSQL schema/trigger acceptance."""

from pathlib import Path

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_phase15_real_tables_and_head(world):
    async with world.factory() as session:
        tables = set(
            (
                await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            ).scalars()
        )
        assert {
            "approval_actions",
            "correction_requests",
            "session_approval_snapshots",
        } <= tables
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0010_phase16"


@pytest.mark.asyncio
async def test_phase15_database_installs_history_and_correction_guards(world):
    async with world.factory() as session:
        triggers = set(
            (
                await session.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))
            ).scalars()
        )

    assert {
        "phase15_validate_approval_actions",
        "phase15_validate_correction_requests",
        "phase15_validate_session_approval_snapshots",
        "phase15_approval_actions_immutable",
        "phase15_session_approval_snapshots_immutable",
        "phase15_correction_request_update_guard",
    } <= triggers


def test_phase15_static_migration_downgrade_is_complete():
    source = Path("alembic/versions/0007_phase15.py").read_text()
    for table in (
        "session_approval_snapshots",
        "correction_requests",
        "approval_actions",
    ):
        assert f'op.drop_table("{table}")' in source
