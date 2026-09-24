"""Phase 15 Stage 2 real PostgreSQL/FastAPI technical review flow."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import UserRoleAssignment
from app.models.testing import (
    SessionTestRequirement,
)
from app.models.testing import (
    TestRun as RunRecord,
)
from app.models.testing import (
    TestSession as SessionRecord,
)
from app.models.testing import (
    TestSessionSection as SessionSectionRecord,
)
from tests.conftest import login
from tests.phase5_fixtures import (
    install_synthetic,
    populate,
    prepare_world,
    seed_evidence,
    started_run,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase15_stage2(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    return world


async def grant_reviewer(world, name):
    async with world.factory() as database, database.begin():
        database.add(
            UserRoleAssignment(
                user_id=world.users[name].id,
                role_id=world.roles["REVIEWER"],
                scope_type="LABORATORY",
                laboratory_id=world.labs[0].id,
                assigned_by=world.users["admin"].id,
            )
        )


async def evaluate(client, run_path):
    current = await client.get(run_path)
    response = await client.post(
        run_path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert response.status_code == 200, response.text
    return response


async def synthetic_review_ready(client, world):
    session_path, run_path, selected_requirement = await started_run(
        client,
        world,
    )
    await populate(client, world, run_path)
    await seed_evidence(world, run_path.rsplit("/", 1)[1])
    result = await evaluate(client, run_path)
    assert result.json()["evaluation_status"] == "COMPLETE"
    assert result.json()["compliance_outcome"] == "NONCOMPLIANT"

    current = await client.get(run_path)
    completed = await client.post(
        run_path + "/complete",
        headers={"If-Match": current.headers["etag"]},
    )
    assert completed.status_code == 200, completed.text

    session_id = UUID(session_path.rsplit("/", 1)[1])
    run_id = UUID(run_path.rsplit("/", 1)[1])
    selected_requirement_id = UUID(selected_requirement["id"])

    async with world.factory() as database, database.begin():
        session = await database.get(
            SessionRecord,
            session_id,
            with_for_update=True,
        )
        run = await database.get(RunRecord, run_id)

        requirements = list(
            (
                await database.scalars(
                    select(SessionTestRequirement).where(
                        SessionTestRequirement.test_session_id == session_id
                    )
                )
            ).all()
        )
        for requirement in requirements:
            if requirement.id == selected_requirement_id:
                requirement.applicability_status = "REQUIRED"
                requirement.is_elected = False
                requirement.selected_run_id = run.id
            else:
                requirement.applicability_status = "NOT_APPLICABLE"
                requirement.is_elected = False
                requirement.selected_run_id = None

        sections = list(
            (
                await database.scalars(
                    select(SessionSectionRecord).where(
                        SessionSectionRecord.test_session_id == session_id
                    )
                )
            ).all()
        )
        for section in sections:
            if section.id == run.session_section_id:
                section.applicability_status = "REQUIRED"
                section.evaluation_status = "COMPLETE"
                section.compliance_outcome = "NONCOMPLIANT"
            else:
                section.applicability_status = "NOT_APPLICABLE"
                section.evaluation_status = "COMPLETE"
                section.compliance_outcome = "NOT_APPLICABLE"

        session.workflow_status = "TESTING"
        session.evaluation_status = "COMPLETE"
        session.compliance_outcome = "NONCOMPLIANT"
        session.lock_version += 1
        session.regulatory_revision += 1

    await login(client, world, "local")
    return session_path, run_path, selected_requirement


async def submit(client, session_path):
    current = await client.get(session_path)
    response = await client.post(
        session_path + "/submit-for-review",
        headers={"If-Match": current.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    return response


async def approve(client, session_path):
    current = await client.get(session_path)
    response = await client.post(
        session_path + "/reviews",
        headers={"If-Match": current.headers["etag"]},
        json={
            "decision": "APPROVED",
            "reviewed_regulatory_revision": current.json()["regulatory_revision"],
        },
    )
    assert response.status_code == 200, response.text
    return response


async def test_phase15_complete_noncompliant_can_be_submitted_and_reviewed(
    client,
    phase15_stage2,
):
    world = phase15_stage2
    await grant_reviewer(world, "viewer")
    session_path, _, _ = await synthetic_review_ready(client, world)

    submitted = await submit(client, session_path)
    assert submitted.json()["workflow_status"] == "UNDER_REVIEW"
    assert submitted.json()["compliance_outcome"] == "NONCOMPLIANT"

    await login(client, world, "viewer")
    approved = await approve(client, session_path)
    assert approved.json()["decision"] == "APPROVED"
    assert approved.json()["actor_id"] == str(world.users["viewer"].id)

    history = (await client.get(session_path + "/reviews")).json()
    assert [row["decision"] for row in history][-2:] == [
        "SUBMITTED",
        "APPROVED",
    ]


async def test_phase15_raw_observation_author_cannot_technically_review(
    client,
    phase15_stage2,
):
    world = phase15_stage2
    await grant_reviewer(world, "local")
    session_path, _, _ = await synthetic_review_ready(client, world)
    await submit(client, session_path)

    current = await client.get(session_path)
    denied = await client.post(
        session_path + "/reviews",
        headers={"If-Match": current.headers["etag"]},
        json={
            "decision": "APPROVED",
            "reviewed_regulatory_revision": current.json()["regulatory_revision"],
        },
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["error"]["code"] == "REVIEW_INDEPENDENCE_REQUIRED"


async def test_phase15_returned_correction_is_bounded_and_invalidates_review(
    client,
    phase15_stage2,
):
    world = phase15_stage2
    await grant_reviewer(world, "viewer")
    session_path, run_path, _ = await synthetic_review_ready(client, world)
    await submit(client, session_path)

    await login(client, world, "viewer")
    approved = await approve(client, session_path)

    current = await client.get(session_path)
    returned = await client.post(
        session_path + "/return-for-correction",
        headers={"If-Match": current.headers["etag"]},
        json={
            "target_workflow_status": "TESTING",
            "requested_scope": {
                "targets": [
                    {
                        "entity_type": "test_runs",
                        "entity_id": run_path.rsplit("/", 1)[1],
                        "field_paths": ["retest"],
                    }
                ]
            },
            "reason": "Create a bounded retest; do not edit the completed source.",
        },
    )
    assert returned.status_code == 200, returned.text
    correction = returned.json()
    assert correction["correction_status"] == "OPEN"

    current = await client.get(session_path)
    assert current.json()["workflow_status"] == "TESTING"

    reopened = await client.post(
        session_path + "/reopen",
        headers={"If-Match": current.headers["etag"]},
    )
    assert reopened.status_code == 200, reopened.text

    await login(client, world, "local")
    run = await client.get(run_path)
    retest = await client.post(
        run_path + "/retests",
        headers={
            "If-Match": run.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={"reason": "Reviewer-authorized Phase 15 retest"},
    )
    assert retest.status_code == 201, retest.text

    history = (await client.get(session_path + "/reviews")).json()
    invalidated = [row for row in history if row["decision"] == "INVALIDATED"]
    assert invalidated
    assert invalidated[-1]["referenced_action_id"] == approved.json()["id"]

    session = await client.get(session_path)
    outside = await client.patch(
        session_path,
        headers={"If-Match": session.headers["etag"]},
        json={"notes": "outside bounded correction"},
    )
    assert outside.status_code == 409, outside.text
    assert outside.json()["error"]["code"] == "CORRECTION_SCOPE_VIOLATION"

    resolved = await client.post(
        session_path + "/corrections/" + correction["id"] + "/resolve",
        headers={"If-Match": f'"{correction["lock_version"]}"'},
        json={"resolution_note": "Bounded retest record created."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["correction_status"] == "RESOLVED"


async def test_phase15_incomplete_session_cannot_submit(
    client,
    phase15_stage2,
):
    world = phase15_stage2
    session_path, _, _ = await started_run(client, world)
    current = await client.get(session_path)
    response = await client.post(
        session_path + "/submit-for-review",
        headers={"If-Match": current.headers["etag"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_NOT_READY_FOR_REVIEW"
