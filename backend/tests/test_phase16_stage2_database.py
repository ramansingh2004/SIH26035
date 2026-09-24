"""Phase 16 Stage 2 real PostgreSQL generated-document guards."""

from pathlib import Path

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_phase16_stage2_head_and_document_guards(world):
    async with world.factory() as session:
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0010_phase16"

        triggers = set(
            (
                await session.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))
            ).scalars()
        )

    assert {
        "phase16_generated_attachment_guard",
        "phase16_preview_ready_files_guard",
        "phase16_report_file_integrity_guard",
    } <= triggers


def test_phase16_stage2_migration_is_reversible():
    source = Path("alembic/versions/0010_phase16.py").read_text()
    assert 'revision = "0010_phase16"' in source
    assert 'down_revision = "0009_phase16"' in source
    for function in (
        "phase16_report_file_integrity_guard",
        "phase16_preview_ready_files_guard",
        "phase16_generated_attachment_guard",
    ):
        assert f"DROP FUNCTION IF EXISTS {function}()" in source
