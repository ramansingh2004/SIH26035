from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select, update

from app.compliance.demo import DEMO_LAB_CODE
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_ARTIFACT,
    full_demo_execution_instrument,
)
from app.models import Attachment, Laboratory, TestEquipment
from app.models.testing import (
    EnvironmentReading,
    TestObservation,
    TestRun,
    TestRunEquipment,
    TestRunResult,
)
from app.services.audit import RequestContext
from app.services.rulesets import RulesetService
from tests.phase5_fixtures import configured, prepare_world

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def stage6(world):
    world = await prepare_world(world)

    async with world.factory() as database, database.begin():
        await database.execute(
            update(Laboratory)
            .where(
                Laboratory.code == DEMO_LAB_CODE,
                Laboratory.id != world.labs[0].id,
            )
            .values(code="RETIRED-DEMO-" + world.labs[0].id.hex[:12])
        )
        lab = await database.get(Laboratory, world.labs[0].id)
        lab.code = DEMO_LAB_CODE

    async with world.factory() as database, database.begin():
        row = await RulesetService(
            database,
            RequestContext(),
        ).insert_artifact(
            artifact=FULL_DEMO_EXECUTION_ARTIFACT,
        )
        world.synthetic_ruleset_id = str(row.id)

    return world


async def start_v3_testing(client, world):
    response, path = await configured(client, world, synthetic=True)

    response = await client.post(
        path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={
            "instrument_snapshot": full_demo_execution_instrument().model_dump(
                mode="json"
            )
        },
    )
    assert response.status_code == 200, response.text

    preview = await client.post(path + "/applicability")
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmable"] is True

    response = await client.post(
        path + "/confirm-applicability",
        headers={"If-Match": response.headers["etag"]},
        json={"elections": {}},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        path + "/start-testing",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    return path, response


async def count(database, model, *criteria):
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return await database.scalar(statement)


async def test_stage6_one_click_closes_all_17_sections(client, stage6):
    path, testing = await start_v3_testing(client, stage6)
    session_id = UUID(testing.json()["id"])

    response = await client.post(
        path + "/demo-complete-evaluation",
        headers={"If-Match": testing.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    session = body["session"]
    sections = body["sections"]
    assert session["workflow_status"] == "EXAMINATION"
    assert session["evaluation_status"] == "COMPLETE"
    assert session["compliance_outcome"] == "COMPLIANT"
    assert len(sections) == 17
    assert {item["section_number"] for item in sections} == set(range(1, 18))
    assert all(item["applicability_status"] == "REQUIRED" for item in sections)
    assert all(item["evaluation_status"] == "COMPLETE" for item in sections)
    assert all(item["compliance_outcome"] == "COMPLIANT" for item in sections)

    async with stage6.factory() as database:
        runs = list(
            (
                await database.scalars(
                    select(TestRun).where(TestRun.test_session_id == session_id)
                )
            ).all()
        )
        run_ids = [item.id for item in runs]

        assert len(runs) == 23
        assert all(item.completed_at is not None for item in runs)
        assert all(item.current_result_id is not None for item in runs)
        assert all(item.evaluation_status == "COMPLETE" for item in runs)
        assert all(item.compliance_outcome == "COMPLIANT" for item in runs)

        assert (
            await count(
                database,
                TestRunResult,
                TestRunResult.test_run_id.in_(run_ids),
            )
            == 23
        )
        assert (
            await count(
                database,
                TestObservation,
                TestObservation.test_run_id.in_(run_ids),
            )
            == 92
        )
        assert (
            await count(
                database,
                EnvironmentReading,
                EnvironmentReading.test_run_id.in_(run_ids),
            )
            == 23
        )
        assert (
            await count(
                database,
                TestRunEquipment,
                TestRunEquipment.test_run_id.in_(run_ids),
            )
            == 24
        )
        assert (
            await count(
                database,
                TestEquipment,
                TestEquipment.laboratory_id == stage6.labs[0].id,
                TestEquipment.metadata_json["phase"].astext == "PHASE26_STAGE6",
            )
            == 24
        )
        stage6_evidence = list(
            (
                await database.scalars(
                    select(Attachment).where(
                        Attachment.laboratory_id == stage6.labs[0].id,
                        Attachment.metadata_json["phase"].astext
                        == "PHASE26_STAGE6",
                    )
                )
            ).all()
        )

    assert len(stage6_evidence) == 25
    assert all(item.storage_provider == "synthetic-demo" for item in stage6_evidence)
    assert all(item.metadata_json["synthetic_demo"] is True for item in stage6_evidence)
    assert all(item.metadata_json["metadata_only"] is True for item in stage6_evidence)

    repeated = await client.post(
        path + "/demo-complete-evaluation",
        headers={"If-Match": f'"{session["lock_version"]}"'},
    )
    assert repeated.status_code == 409
    assert (
        repeated.json()["error"]["code"]
        == "SYNTHETIC_DEMO_STAGE6_ALREADY_COMPLETE"
    )
