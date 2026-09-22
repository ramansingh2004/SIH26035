from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import (
    AuditEvent,
    RefreshSession,
    User,
    UserRoleAssignment,
)
from app.repositories.identity import IdentityRepository
from app.services.audit import AuditService, RequestContext
from app.services.provisioning import ProvisioningService

FROZEN_RBAC = Path("../docs/07-rbac-workflow.md").read_text()

pytestmark = pytest.mark.asyncio


async def test_schema_extensions_indexes_and_citext(world):
    async with world.factory() as session:
        tables = set(
            (
                await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            ).scalars()
        )
        assert tables == {
            "alembic_version",
            "users",
            "roles",
            "permissions",
            "role_permissions",
            "laboratories",
            "user_role_assignments",
            "auth_refresh_sessions",
            "audit_events",
            "idempotency_keys",
            "manufacturers",
            "instruments",
            "instrument_ranges",
            "instrument_components",
            "rule_sets",
            "rule_definitions",
            "test_definitions",
            "checklist_rules",
            "test_equipment",
            "attachment_uploads",
            "attachments",
            "attachment_links",
            "test_sessions",
            "test_session_sections",
            "session_test_requirements",
            "test_runs",
            "test_observations",
            "environment_readings",
            "test_run_equipment",
            "test_run_results",
            "evaluation_result_events",
            "test_run_selection_events",
        }
        extensions = set(
            (await session.execute(text("SELECT extname FROM pg_extension"))).scalars()
        )
        assert {"citext", "pgcrypto"} <= extensions
        indexes = set(
            (
                await session.execute(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
                )
            ).scalars()
        )
        assert {
            "uq_assignment_global_active",
            "uq_assignment_lab_active",
            "uq_refresh_successor",
        } <= indexes
        found = await session.scalar(
            select(User).where(User.email == world.users["admin"].email.upper())
        )
        assert found.id == world.users["admin"].id
        assert (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar() == "0004_phase5"


@pytest.mark.parametrize(
    "kind", ["global_null", "lab_required", "duplicate_global", "duplicate_lab", "non_admin_global"]
)
async def test_assignment_database_constraints(world, kind):
    values = dict(
        user_id=world.users["viewer"].id,
        role_id=world.roles["REVIEWER"],
        scope_type="LABORATORY",
        laboratory_id=world.labs[0].id,
        assigned_by=world.users["admin"].id,
    )
    if kind == "global_null":
        values.update(scope_type="GLOBAL", role_id=world.roles["ADMIN"])
    elif kind == "lab_required":
        values["laboratory_id"] = None
    elif kind == "duplicate_global":
        values.update(
            user_id=world.users["admin"].id,
            role_id=world.roles["ADMIN"],
            scope_type="GLOBAL",
            laboratory_id=None,
        )
    elif kind == "duplicate_lab":
        values["role_id"] = world.roles["VIEWER"]
    else:
        values.update(scope_type="GLOBAL", laboratory_id=None)
    with pytest.raises(IntegrityError):
        async with world.factory() as session, session.begin():
            session.add(UserRoleAssignment(**values))
            await session.flush()


async def test_revocation_preserves_history_and_allows_new_uuid(world):
    async with world.factory() as session, session.begin():
        old = await session.scalar(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == world.users["viewer"].id)
        )
        old.revoked_at = datetime.now(UTC)
        old.revoked_by = world.users["admin"].id
        old.revocation_reason = "Test revocation"
        old.lock_version += 1
        await session.flush()
        new = UserRoleAssignment(
            user_id=old.user_id,
            role_id=old.role_id,
            scope_type=old.scope_type,
            laboratory_id=old.laboratory_id,
            assigned_by=world.users["admin"].id,
        )
        session.add(new)
        await session.flush()
        assert new.id != old.id


async def test_refresh_successor_uniqueness(world):
    now = datetime.now(UTC)

    def row(parent=None):
        return RefreshSession(
            id=uuid4(),
            user_id=world.users["admin"].id,
            family_id=family,
            token_digest=uuid4().hex * 2,
            created_at=now,
            expires_at=now + timedelta(days=1),
            family_expires_at=now + timedelta(days=2),
            parent_session_id=parent,
        )

    family = uuid4()
    async with world.factory() as session, session.begin():
        parent = row()
        session.add(parent)
        await session.flush()
        session.add(row(parent.id))
    with pytest.raises(IntegrityError):
        async with world.factory() as session, session.begin():
            session.add(row(parent.id))
            await session.flush()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action='tampered'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
async def test_audit_is_immutable_in_database(world, statement):
    with pytest.raises(DBAPIError):
        async with world.factory() as session, session.begin():
            await session.execute(text(statement))


async def test_failed_mutation_rolls_back_its_audit(world):
    marker = uuid4()
    with pytest.raises(RuntimeError):
        async with world.factory() as session, session.begin():
            user = await session.get(User, world.users["viewer"].id)
            user.full_name = "Must roll back"
            AuditService(IdentityRepository(session), RequestContext()).record(
                "user.updated", user.id, "users", marker, after={"full_name": "Must roll back"}
            )
            await session.flush()
            raise RuntimeError("Rollback")
    async with world.factory() as session:
        assert (await session.get(User, world.users["viewer"].id)).full_name == "viewer"
        assert (
            await session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == marker)
            )
            == 0
        )


async def test_seed_matches_frozen_permission_sets_and_is_idempotent(world):
    source = FROZEN_RBAC
    sets = {}
    for line in source.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) == 4 and cells[1] in {
            "READ",
            "MASTER",
            "ENTRY",
            "ENGINEER",
            "REVIEW",
            "APPROVE",
            "LAB_ADMIN",
            "GLOBAL_ADMIN",
        }:
            sets[cells[1]] = set(cells[2].split(", "))
    expected = {
        "ADMIN": sets["READ"] | sets["MASTER"] | sets["LAB_ADMIN"] | sets["GLOBAL_ADMIN"],
        "LAB_TECHNICIAN": sets["READ"] | sets["MASTER"] | sets["ENTRY"],
        "LAB_ENGINEER": sets["READ"] | sets["MASTER"] | sets["ENTRY"] | sets["ENGINEER"],
        "REVIEWER": sets["READ"] | sets["REVIEW"],
        "APPROVING_OFFICER": sets["READ"] | sets["APPROVE"],
        "VIEWER": sets["READ"],
    }
    async with world.factory() as session:
        assert await ProvisioningService(session).seed() == 0
        actual = {}
        for role, code in await IdentityRepository(session).roles():
            actual.setdefault(role.code, set()).add(code)
        assert actual == expected
        assert "*" not in set().union(*actual.values())
