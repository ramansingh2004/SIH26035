from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.compliance.demo import DEMO_LAB_CODE
from app.compliance.full_demo_execution import FULL_DEMO_EXECUTION_ARTIFACT
from app.models import Attachment, AttachmentLink, Laboratory
from app.services.audit import RequestContext
from app.services.rulesets import RulesetService
from tests.phase5_fixtures import configured, prepare_world

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def stage5(world):
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


async def start_v3_examination(client, world):
    response, path = await configured(client, world, synthetic=True)

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

    response = await client.post(
        path + "/start-examination",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    return path


async def complete_section16(client, path):
    construction = await client.get(path + "/construction")
    assert construction.status_code == 200, construction.text
    result = await client.post(
        path + "/construction/demo-complete",
        headers={"If-Match": construction.headers["etag"]},
    )
    assert result.status_code == 200, result.text
    assert result.json()["evaluation_status"] == "COMPLETE"
    assert result.json()["compliance_outcome"] == "COMPLIANT"


async def test_stage5_requires_completed_section16(client, stage5):
    path = await start_v3_examination(client, stage5)

    before = await client.get(path + "/checklist/summary")
    assert before.status_code == 200, before.text

    blocked = await client.post(
        path + "/checklist/demo-complete",
        headers={"If-Match": before.headers["etag"]},
    )
    assert blocked.status_code == 409
    assert (
        blocked.json()["error"]["code"]
        == "SYNTHETIC_DEMO_STAGE5_SECTION16_REQUIRED"
    )


async def test_stage5_one_click_demo_completes_section17(client, stage5):
    path = await start_v3_examination(client, stage5)
    await complete_section16(client, path)

    before = await client.get(path + "/checklist/summary")
    assert before.status_code == 200, before.text
    assert before.json()["catalog_total"] == 27
    assert before.json()["evaluation_status"] == "NOT_STARTED"

    response = await client.post(
        path + "/checklist/demo-complete",
        headers={"If-Match": before.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["catalog_total"] == 27
    assert body["applicable"] == 27
    assert body["passed"] == 27
    assert body["failed"] == 0
    assert body["not_examined"] == 0
    assert body["not_applicable"] == 0
    assert body["review_required"] == 0
    assert body["evaluation_status"] == "COMPLETE"
    assert body["compliance_outcome"] == "COMPLIANT"
    assert body["missing_rule_keys"] == []
    assert body["blockers"] == []

    rows = (await client.get(path + "/checklist")).json()
    assert len(rows) == 27
    assert all(row["applicability_status"] == "REQUIRED" for row in rows)
    assert all(row["response_result"] == "PASS" for row in rows)
    assert all("SYNTHETIC" in (row["remarks"] or "") for row in rows)

    section16 = await client.get(path + "/sections/16")
    section17 = await client.get(path + "/sections/17")
    assert section16.json()["evaluation_status"] == "COMPLETE"
    assert section16.json()["compliance_outcome"] == "COMPLIANT"
    assert section17.json()["evaluation_status"] == "COMPLETE"
    assert section17.json()["compliance_outcome"] == "COMPLIANT"

    response_ids = {UUID(row["id"]) for row in rows}
    async with stage5.factory() as database:
        links = list(
            (
                await database.scalars(
                    select(AttachmentLink).where(
                        AttachmentLink.entity_type == "checklist_responses",
                        AttachmentLink.entity_id.in_(response_ids),
                        AttachmentLink.unlinked_at.is_(None),
                    )
                )
            ).all()
        )
        attachments = [
            await database.get(Attachment, link.attachment_id)
            for link in links
        ]

    assert len(links) == 27
    assert len(attachments) == 27
    assert all(item.storage_provider == "synthetic-demo" for item in attachments)
    assert all(item.metadata_json["synthetic_demo"] is True for item in attachments)
    assert all(item.metadata_json["metadata_only"] is True for item in attachments)


async def test_stage5_demo_completion_is_not_repeatable(client, stage5):
    path = await start_v3_examination(client, stage5)
    await complete_section16(client, path)

    before = await client.get(path + "/checklist/summary")
    first = await client.post(
        path + "/checklist/demo-complete",
        headers={"If-Match": before.headers["etag"]},
    )
    assert first.status_code == 200, first.text

    repeated = await client.post(
        path + "/checklist/demo-complete",
        headers={"If-Match": first.headers["etag"]},
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "CHECKLIST_ALREADY_COMPLETE"
