from io import BytesIO
from uuid import UUID
from zipfile import ZipFile

import pytest
import pytest_asyncio
from sqlalchemy import update

from app.api.dependencies import object_storage
from app.compliance.demo import DEMO_LAB_CODE
from app.compliance.full_demo_execution import FULL_DEMO_EXECUTION_ARTIFACT
from app.models import Attachment, Laboratory
from app.services.audit import RequestContext
from app.services.rulesets import RulesetService
from tests.phase5_fixtures import prepare_world
from tests.test_foundations_api import MemoryStorage
from tests.test_phase26_stage6_api import start_v3_testing

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def stage7(world):
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

    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def test_stage7_rejects_v3_before_stage6_completion(client, stage7):
    path, testing = await start_v3_testing(client, stage7)

    response = await client.post(
        path + "/full-demo-report-previews",
        headers={"If-Match": testing.headers["etag"]},
    )
    assert response.status_code == 409
    assert (
        response.json()["error"]["code"]
        == "SYNTHETIC_DEMO_STAGE7_SOURCE_INCOMPLETE"
    )


async def test_stage7_generates_complete_pdf_docx_from_finished_stage6(
    client,
    stage7,
):
    path, testing = await start_v3_testing(client, stage7)

    completed = await client.post(
        path + "/demo-complete-evaluation",
        headers={"If-Match": testing.headers["etag"]},
    )
    assert completed.status_code == 200, completed.text

    current = await client.get(path)
    assert current.status_code == 200, current.text

    response = await client.post(
        path + "/full-demo-report-previews",
        headers={"If-Match": current.headers["etag"]},
    )
    assert response.status_code == 201, response.text
    preview = response.json()
    assert preview["preview_status"] == "READY"

    context = preview["preview_context_snapshot"]
    assert context["document_kind"] == "FULL_DEMO_REPORT"
    assert context["document_control"]["report_status"] == "DEMONSTRATION_ONLY"
    assert context["demonstration"]["demo_only"] is True
    assert context["demonstration"]["not_for_regulatory_use"] is True
    assert context["demonstration"]["source_counts"] == {
        "sections": 17,
        "runs": 23,
        "observations": 92,
        "environment_readings": 23,
        "equipment_links": 24,
        "results": 23,
        "construction_items": 8,
        "checklist": 27,
        "evidence_links": 85,
        "unique_evidence_attachments": 60,
    }

    record = context["regulatory_record"]
    assert len(record["sections"]) == 17
    assert len(record["runs"]) == 23
    assert len(record["observations"]) == 92
    assert len(record["results"]) == 23
    assert len(record["construction"]["items"]) == 8
    assert len(record["checklist"]) == 27
    assert len(record["evidence"]) == 85
    assert (
        len(
            {
                item["attachment"]["id"]
                for item in record["evidence"]
            }
        )
        == 60
    )

    ids = preview["file_attachment_ids"]
    assert set(ids) == {"pdf", "docx"}

    async with stage7.factory() as database:
        pdf = await database.get(Attachment, UUID(ids["pdf"]))
        docx = await database.get(Attachment, UUID(ids["docx"]))

    assert pdf.metadata_json["full_demo_report"] is True
    assert docx.metadata_json["full_demo_report"] is True
    assert pdf.metadata_json["unofficial"] is True
    assert docx.metadata_json["unofficial"] is True

    pdf_bytes = stage7.storage.objects[pdf.storage_key].body
    docx_bytes = stage7.storage.objects[docx.storage_key].body
    assert pdf_bytes.startswith(b"%PDF-")
    assert docx_bytes.startswith(b"PK")

    with ZipFile(BytesIO(docx_bytes)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "NOT AN OFFICIAL OIML CERTIFICATE" in document_xml
    assert "Executive Summary - All 17 Sections" in document_xml
    assert "Test Runs, Observations and Stored Results" in document_xml
    assert "Construction Examination" in document_xml
    assert "Evidence Register" in document_xml

    for file_format in ("pdf", "docx"):
        download = await client.get(
            f"/api/v1/report-previews/{preview['id']}/download",
            params={"format": file_format},
        )
        assert download.status_code == 200, download.text
        assert download.json()["download_url"].startswith(
            "https://private.invalid/download"
        )
