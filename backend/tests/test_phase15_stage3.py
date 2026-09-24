"""Phase 15 Stage 3 final approval, immutability and revision governance."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.compliance.canonical import content_hash
from app.models import UserRoleAssignment
from app.models.review import ApprovalAction, SessionApprovalSnapshot
from app.models.testing import (
    TestObservation as ObservationRecord,
)
from app.models.testing import (
    TestRun as RunRecord,
)
from tests.conftest import login
from tests.phase5_fixtures import install_synthetic, prepare_world
from tests.test_phase15_stage2 import (
    approve as technical_approve,
)
from tests.test_phase15_stage2 import (
    grant_reviewer,
    submit,
    synthetic_review_ready,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase15_stage3(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    return world


async def grant_role(world, name, role):
    async with world.factory() as database, database.begin():
        database.add(
            UserRoleAssignment(
                user_id=world.users[name].id,
                role_id=world.roles[role],
                scope_type="LABORATORY",
                laboratory_id=world.labs[0].id,
                assigned_by=world.users["admin"].id,
            )
        )


async def technically_approved(client, world):
    await grant_reviewer(world, "viewer")
    session_path, run_path, requirement = await synthetic_review_ready(
        client,
        world,
    )
    await submit(client, session_path)
    await login(client, world, "viewer")
    technical = await technical_approve(client, session_path)
    return session_path, run_path, requirement, technical


async def final_approve(client, world, session_path, *, key=None):
    await login(client, world, "officer")
    current = await client.get(session_path)
    headers = {
        "If-Match": current.headers["etag"],
        "Idempotency-Key": key or uuid4().hex,
    }
    response = await client.post(
        session_path + "/approve",
        headers=headers,
    )
    return response, headers


async def test_phase15_complete_noncompliant_can_be_finally_approved(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, technical = await technically_approved(
        client,
        world,
    )

    approved, _ = await final_approve(
        client,
        world,
        session_path,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["workflow_status"] == "APPROVED"
    assert body["evaluation_status"] == "COMPLETE"
    assert body["compliance_outcome"] == "NONCOMPLIANT"
    assert body["approved_at"] is not None
    assert body["completed_at"] is not None

    session_id = UUID(body["id"])
    async with world.factory() as database:
        snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == session_id
            )
        )
        assert snapshot is not None
        assert snapshot.regulatory_revision == body["regulatory_revision"]
        assert snapshot.snapshot_hash == content_hash(snapshot.snapshot_json)
        assert snapshot.snapshot_json["session"]["workflow_status"] == "APPROVED"
        assert snapshot.snapshot_json["session"]["compliance_outcome"] == "NONCOMPLIANT"
        assert snapshot.snapshot_json["evidence"]
        assert snapshot.snapshot_json["results"]
        assert len(snapshot.snapshot_json["sections"]) == 17
        assert snapshot.snapshot_json["actors"]
        assert all(
            "password_hash" not in actor["user"] for actor in snapshot.snapshot_json["actors"]
        )

        final_action = await database.get(
            ApprovalAction,
            snapshot.approval_action_id,
        )
        assert final_action.stage == "FINAL_APPROVAL"
        assert final_action.decision == "APPROVED"
        assert final_action.scope_json["technical_approval_action_id"] == technical.json()["id"]


async def test_phase15_final_approval_idempotent_replay_precedes_stale_etag(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)

    key = uuid4().hex
    first, headers = await final_approve(
        client,
        world,
        session_path,
        key=key,
    )
    assert first.status_code == 200, first.text

    replay = await client.post(
        session_path + "/approve",
        headers=headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()

    session_id = UUID(first.json()["id"])
    async with world.factory() as database:
        assert (
            await database.scalar(
                select(func.count())
                .select_from(SessionApprovalSnapshot)
                .where(SessionApprovalSnapshot.test_session_id == session_id)
            )
            == 1
        )
        assert (
            await database.scalar(
                select(func.count())
                .select_from(ApprovalAction)
                .where(
                    ApprovalAction.test_session_id == session_id,
                    ApprovalAction.stage == "FINAL_APPROVAL",
                    ApprovalAction.decision == "APPROVED",
                )
            )
            == 1
        )


async def test_phase15_final_approver_must_be_independent(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)
    await grant_role(world, "local", "APPROVING_OFFICER")

    await login(client, world, "local")
    current = await client.get(session_path)
    response = await client.post(
        session_path + "/approve",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "APPROVAL_INDEPENDENCE_REQUIRED"


async def test_phase15_global_admin_has_no_final_approval_wildcard(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)

    current = await client.get(session_path)
    await login(client, world, "admin")
    response = await client.post(
        session_path + "/approve",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_phase15_final_rejection_is_terminal_without_snapshot(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    await grant_reviewer(world, "viewer")
    session_path, _, _ = await synthetic_review_ready(client, world)
    await submit(client, session_path)

    await login(client, world, "officer")
    current = await client.get(session_path)
    rejected = await client.post(
        session_path + "/reject",
        headers={"If-Match": current.headers["etag"]},
        json={"reason": "Officer rejected the submitted regulatory record."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["workflow_status"] == "REJECTED"

    session_id = UUID(rejected.json()["id"])
    async with world.factory() as database:
        assert (
            await database.scalar(
                select(SessionApprovalSnapshot).where(
                    SessionApprovalSnapshot.test_session_id == session_id
                )
            )
            is None
        )
        action = await database.scalar(
            select(ApprovalAction)
            .where(
                ApprovalAction.test_session_id == session_id,
                ApprovalAction.stage == "FINAL_APPROVAL",
            )
            .order_by(ApprovalAction.created_at.desc())
        )
        assert action.decision == "REJECTED"
        assert action.reason


async def test_phase15_approved_snapshot_and_sources_are_database_immutable(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)
    approved, _ = await final_approve(client, world, session_path)
    assert approved.status_code == 200, approved.text
    session_id = UUID(approved.json()["id"])

    async with world.factory() as database:
        snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == session_id
            )
        )
        observation = await database.scalar(
            select(ObservationRecord)
            .join(
                RunRecord,
                RunRecord.id == ObservationRecord.test_run_id,
            )
            .where(RunRecord.test_session_id == session_id)
        )

    with pytest.raises(DBAPIError):
        async with world.factory() as database, database.begin():
            await database.execute(
                text("UPDATE session_approval_snapshots SET snapshot_hash = :hash WHERE id = :id"),
                {
                    "hash": "f" * 64,
                    "id": snapshot.id,
                },
            )

    with pytest.raises(DBAPIError):
        async with world.factory() as database, database.begin():
            await database.execute(
                text("UPDATE test_observations SET payload_json = payload_json WHERE id = :id"),
                {"id": observation.id},
            )

    with pytest.raises(DBAPIError):
        async with world.factory() as database, database.begin():
            await database.execute(
                text("UPDATE test_sessions SET notes = 'forbidden approved edit' WHERE id = :id"),
                {"id": session_id},
            )


async def test_phase15_post_approval_correction_creates_child_revision(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)
    approved, _ = await final_approve(client, world, session_path)
    assert approved.status_code == 200, approved.text
    parent = approved.json()

    current = await client.get(session_path)
    child = await client.post(
        session_path + "/revisions",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={"reason": "Post-approval controlled correction."},
    )
    assert child.status_code == 201, child.text
    body = child.json()
    assert body["workflow_status"] == "INSTRUMENT_CONFIGURATION"
    assert body["evaluation_status"] == "NOT_STARTED"
    assert body["compliance_outcome"] == "UNDETERMINED"
    assert body["parent_session_id"] == parent["id"]
    assert body["root_session_id"] == parent["root_session_id"]
    assert body["session_revision_no"] == parent["session_revision_no"] + 1
    assert body["revision_reason"] == "Post-approval controlled correction."

    async with world.factory() as database:
        original_snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == UUID(parent["id"])
            )
        )
        child_snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == UUID(body["id"])
            )
        )
        child_actions = await database.scalar(
            select(func.count())
            .select_from(ApprovalAction)
            .where(ApprovalAction.test_session_id == UUID(body["id"]))
        )
        assert original_snapshot is not None
        assert child_snapshot is None
        assert child_actions == 0

    original = await client.get(session_path)
    assert original.json()["workflow_status"] == "APPROVED"


async def test_phase15_final_approval_requires_current_technical_approval(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    await grant_reviewer(world, "viewer")
    session_path, _, _ = await synthetic_review_ready(client, world)
    await submit(client, session_path)

    response, _ = await final_approve(client, world, session_path)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "SESSION_NOT_READY_FOR_APPROVAL"


async def test_phase15_reviewer_and_approver_may_be_same_independent_actor(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    await grant_reviewer(world, "viewer")
    await grant_role(world, "viewer", "APPROVING_OFFICER")
    session_path, _, _ = await synthetic_review_ready(client, world)
    await submit(client, session_path)

    await login(client, world, "viewer")
    technical = await technical_approve(client, session_path)
    assert technical.status_code == 200, technical.text

    current = await client.get(session_path)
    approved = await client.post(
        session_path + "/approve",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["workflow_status"] == "APPROVED"


async def test_phase15_final_approval_requires_idempotency_key(
    client,
    phase15_stage3,
):
    world = phase15_stage3
    session_path, _, _, _ = await technically_approved(client, world)

    await login(client, world, "officer")
    current = await client.get(session_path)
    response = await client.post(
        session_path + "/approve",
        headers={"If-Match": current.headers["etag"]},
    )
    assert response.status_code == 428
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
