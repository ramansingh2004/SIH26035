"""Phase 17 Stage 2 bounded-query and 1000-report PostgreSQL smoke tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, insert

from app.models.report import Report
from app.models.testing import TestSession as SessionRecord
from app.repositories.dashboard import DashboardRepository
from app.repositories.report import ReportRepository
from tests.phase5_fixtures import install_synthetic, prepare_world
from tests.test_phase16_stage3 import approved_session

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase17_performance(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    return world


async def test_dashboard_query_count_is_constant(
    phase17_performance,
):
    world = phase17_performance
    statements = 0

    def count_statement(*_args):
        nonlocal statements
        statements += 1

    async with world.factory() as database:
        event.listen(
            world.engine.sync_engine,
            "before_cursor_execute",
            count_statement,
        )
        try:
            repository = DashboardRepository(database)
            result = await repository.summary(
                {world.labs[0].id},
                1,
                20,
            )
        finally:
            event.remove(
                world.engine.sync_engine,
                "before_cursor_execute",
                count_statement,
            )

    assert statements == 6
    assert {
        "workflow_rows",
        "evaluation_rows",
        "outcome_rows",
        "report_rows",
        "activity_rows",
        "activity_total",
    } == set(result)


async def test_paginated_repository_smokes_1000_reports_in_two_queries(
    client,
    phase17_performance,
):
    world = phase17_performance
    _, approved = await approved_session(client, world)
    base_id = UUID(approved.json()["id"])

    async with world.factory() as database:
        transaction = await database.begin()
        try:
            base = await database.get(SessionRecord, base_id)
            now = datetime.now(UTC)

            session_rows = []
            report_rows = []
            for index in range(1000):
                session_id = uuid4()
                report_id = uuid4()
                sequence = index + 1

                session_rows.append(
                    {
                        "id": session_id,
                        "laboratory_id": base.laboratory_id,
                        "instrument_id": base.instrument_id,
                        "rule_set_id": base.rule_set_id,
                        "application_number": (f"PERF-REPO-{sequence:04d}"),
                        "workflow_status": "APPROVED",
                        "evaluation_status": "COMPLETE",
                        "compliance_outcome": "NONCOMPLIANT",
                        "evaluation_context": base.evaluation_context,
                        "instrument_snapshot": base.instrument_snapshot,
                        "ruleset_snapshot": base.ruleset_snapshot,
                        "snapshot_schema_version": 1,
                        "regulatory_revision": 1,
                        "root_session_id": session_id,
                        "parent_session_id": None,
                        "session_revision_no": 1,
                        "revision_reason": None,
                        "started_by": base.started_by,
                        "started_at": now,
                        "submitted_at": now,
                        "approved_at": now,
                        "completed_at": now,
                        "notes": "Phase 17 performance fixture",
                        "lock_version": 1,
                    }
                )
                report_rows.append(
                    {
                        "id": report_id,
                        "test_session_id": session_id,
                        "report_number": (f"R76-2098-{sequence}"),
                        "revision_no": 1,
                        "root_report_id": report_id,
                        "supersedes_report_id": None,
                        "revision_reason": None,
                        "report_status": "UNISSUED",
                        "selected_generation_id": None,
                        "issued_at": None,
                        "issued_by": None,
                        "report_hash": None,
                        "created_by": world.users["officer"].id,
                        "lock_version": 1,
                    }
                )

            await database.execute(
                insert(SessionRecord),
                session_rows,
            )
            await database.execute(
                insert(Report),
                report_rows,
            )
            await database.flush()

            statements = 0

            def count_statement(*_args):
                nonlocal statements
                statements += 1

            event.listen(
                world.engine.sync_engine,
                "before_cursor_execute",
                count_statement,
            )
            try:
                repository = ReportRepository(database)
                rows, total = await repository.search(
                    {world.labs[0].id},
                    1,
                    100,
                    {"search": "PERF-REPO-"},
                )
            finally:
                event.remove(
                    world.engine.sync_engine,
                    "before_cursor_execute",
                    count_statement,
                )

            assert total == 1000
            assert len(rows) == 100
            assert statements == 2
        finally:
            await transaction.rollback()
