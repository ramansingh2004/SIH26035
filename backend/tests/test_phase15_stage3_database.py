"""Phase 15 Stage 3 PostgreSQL approval-lock acceptance."""

from pathlib import Path

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_phase15_stage3_head_and_terminal_source_guards(world):
    async with world.factory() as session:
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0010_phase16"

        triggers = set(
            (
                await session.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE NOT tgisinternal "
                        "AND tgname LIKE 'phase15_terminal_source_%'"
                    )
                )
            ).scalars()
        )

    assert {
        "phase15_terminal_source_test_sessions",
        "phase15_terminal_source_test_session_sections",
        "phase15_terminal_source_session_test_requirements",
        "phase15_terminal_source_test_runs",
        "phase15_terminal_source_test_observations",
        "phase15_terminal_source_environment_readings",
        "phase15_terminal_source_test_run_equipment",
        "phase15_terminal_source_construction_examinations",
        "phase15_terminal_source_construction_items",
        "phase15_terminal_source_checklist_responses",
        "phase15_terminal_source_attachment_links",
    } <= triggers


def test_phase15_stage3_migration_is_reversible():
    source = Path("alembic/versions/0008_phase15.py").read_text()
    assert 'revision = "0008_phase15"' in source
    assert 'down_revision = "0007_phase15"' in source
    assert "DROP FUNCTION IF EXISTS phase15_terminal_source_guard()" in source
