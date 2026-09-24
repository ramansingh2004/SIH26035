"""Phase 16 Stage 1 real PostgreSQL report-schema acceptance."""

from pathlib import Path

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_phase16_report_tables_and_head(world):
    async with world.factory() as session:
        tables = set(
            (
                await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            ).scalars()
        )
        assert {
            "report_number_counters",
            "reports",
            "report_generations",
            "report_files",
            "report_previews",
        } <= tables
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0010_phase16"


@pytest.mark.asyncio
async def test_phase16_report_guards_and_current_issue_index(world):
    async with world.factory() as session:
        triggers = set(
            (
                await session.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))
            ).scalars()
        )
        indexes = set(
            (
                await session.execute(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
                )
            ).scalars()
        )

    assert {
        "phase16_reports_guard",
        "phase16_report_generations_guard",
        "phase16_report_files_guard",
        "phase16_report_previews_guard",
    } <= triggers
    assert "uq_report_current_issued" in indexes


def test_phase16_stage1_migration_downgrade_is_complete():
    source = Path("alembic/versions/0009_phase16.py").read_text()
    assert ("ALTER TABLE reports DROP CONSTRAINT IF EXISTS fk_report_selected_generation") in source
    for table in (
        "report_previews",
        "report_files",
        "report_generations",
        "reports",
        "report_number_counters",
    ):
        assert f'op.drop_table("{table}")' in source
    for function in (
        "phase16_preview_guard",
        "phase16_report_file_guard",
        "phase16_generation_guard",
        "phase16_report_guard",
    ):
        assert f"DROP FUNCTION IF EXISTS {function}()" in source
