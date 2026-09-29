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
async def stage4(world):
    world = await prepare_world(world)

    async with world.factory() as database, database.begin():
        # The real *_test database is intentionally persistent across tests.
        # Reclaim the one dedicated demo code from any earlier Stage 4 fixture
        # without weakening the production unique constraint.
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


async def test_stage4_one_click_demo_completes_section16(client, stage4):
    path = await start_v3_examination(client, stage4)

    before = await client.get(path + "/construction")
    assert before.status_code == 200, before.text
    assert before.json()["evaluation_status"] == "NOT_STARTED"

    response = await client.post(
        path + "/construction/demo-complete",
        headers={"If-Match": before.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["evaluation_status"] == "COMPLETE"
    assert body["compliance_outcome"] == "COMPLIANT"
    assert body["summary_json"]["catalog_total"] == 8
    assert body["summary_json"]["required_total"] == 8
    assert body["summary_json"]["examined"] == 8
    assert body["summary_json"]["passed"] == 8
    assert body["summary_json"]["failed"] == 0
    assert body["summary_json"]["missing_item_keys"] == []
    assert body["summary_json"]["blockers"] == []

    items = (await client.get(path + "/construction/items")).json()
    assert len(items) == 8
    assert all(item["examination_state"] == "EXAMINED" for item in items)
    assert all(item["conformance_result"] == "PASS" for item in items)
    assert all("SYNTHETIC" in (item["remarks"] or "") for item in items)

    section = await client.get(path + "/sections/16")
    assert section.status_code == 200
    assert section.json()["evaluation_status"] == "COMPLETE"
    assert section.json()["compliance_outcome"] == "COMPLIANT"

    item_ids = {UUID(item["id"]) for item in items}
    async with stage4.factory() as database:
        links = list(
            (
                await database.scalars(
                    select(AttachmentLink).where(
                        AttachmentLink.entity_type == "construction_items",
                        AttachmentLink.entity_id.in_(item_ids),
                        AttachmentLink.unlinked_at.is_(None),
                    )
                )
            ).all()
        )
        attachments = [
            await database.get(Attachment, link.attachment_id)
            for link in links
        ]

    assert len(links) == 8
    assert len(attachments) == 8
    assert all(item.storage_provider == "synthetic-demo" for item in attachments)
    assert all(item.metadata_json["synthetic_demo"] is True for item in attachments)
    assert all(item.metadata_json["metadata_only"] is True for item in attachments)


async def test_stage4_demo_completion_is_not_repeatable_after_completion(
    client,
    stage4,
):
    path = await start_v3_examination(client, stage4)
    before = await client.get(path + "/construction")

    first = await client.post(
        path + "/construction/demo-complete",
        headers={"If-Match": before.headers["etag"]},
    )
    assert first.status_code == 200, first.text

    repeated = await client.post(
        path + "/construction/demo-complete",
        headers={"If-Match": first.headers["etag"]},
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "CONSTRUCTION_ALREADY_COMPLETE"
