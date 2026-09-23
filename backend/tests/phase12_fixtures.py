"""SYNTHETIC Phase 12 Section 16 integration fixture only."""

import json
from uuid import UUID

from fastapi import Request

from app.api.dependencies import context, object_storage, testing_service
from app.compliance.ruleset import RuleSet
from app.services.rulesets import RulesetService
from app.storage.objects import StoredObject
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION
from tests.phase11_fixtures import (
    SyntheticPhase11TestingService,
    configured_phase11,
    phase11_fixture_rules,
)
from tests.test_foundations_api import MemoryStorage
from tests.test_storage import PDF

CATEGORIES = (
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
)


def phase12_fixture_rules() -> RuleSet:
    payload = phase11_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE12_INTEGRATION"
    payload["metadata"]["edition"] = "TEST-PHASE12-v1"

    for index, category in enumerate(CATEGORIES, start=1):
        item_key = f"{category}.SYNTHETIC_ITEM"
        policy = {
            "schema_version": "v1",
            "category": category,
            "item_key": item_key,
            "sort_order": index * 10,
            "required": True,
            "evidence_required": category == "DOCUMENTS_PHOTOS",
            "allow_not_applicable": False,
            "required_value_keys": ["observed_value"],
        }
        payload["rules"].append(
            {
                "key": f"SECTION16_{category}_SYNTHETIC",
                "section": 16,
                "kind": "construction_item_v1",
                "description": "SYNTHETIC TEST FIXTURE ONLY - " + category,
                "source": SOURCE,
                "verification": VERIFICATION,
                "dependencies": [],
                "blockers": [],
                "parameters": [
                    {
                        "name": "POLICY_JSON",
                        "value": json.dumps(
                            policy,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        )

    return RuleSet.model_validate(payload)


async def install_phase12_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase12_fixture_rules()
    with monkeypatch.context() as patch:
        patch.setattr(service_module, "load_ruleset", lambda: fixture)
        async with world.factory() as session, session.begin():
            row = await RulesetService(
                session,
                RequestContext(),
            ).insert_artifact()
            row.ruleset_status = "ACTIVE"
            row.validation_summary = {
                "authoritative": True,
                "SYNTHETIC_TEST_FIXTURE_ONLY": True,
            }
            world.synthetic_ruleset_id = str(row.id)

    async def testing(request: Request):
        async with world.factory() as session:
            yield SyntheticPhase11TestingService(
                session,
                context(request),
            )

    world.app.dependency_overrides[testing_service] = testing
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage


async def start_phase12_examination(client, world):
    response, session_path = await configured_phase11(client, world)

    preview = await client.post(session_path + "/applicability")
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmable"] is True

    response = await client.post(
        session_path + "/confirm-applicability",
        headers={"If-Match": response.headers["etag"]},
        json={"elections": {}},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        session_path + "/start-testing",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        session_path + "/start-examination",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["workflow_status"] == "EXAMINATION"
    return session_path, response


async def fill_items(client, session_path, *, fail_key=None):
    items = (await client.get(session_path + "/construction/items")).json()
    result = {}
    for item in items:
        outcome = "FAIL" if item["item_key"] == fail_key else "PASS"
        response = await client.patch(
            session_path + "/construction/items/" + item["id"],
            headers={"If-Match": f'"{item["lock_version"]}"'},
            json={
                "value_json": {"observed_value": "SYNTHETIC_CAPTURED"},
                "examination_state": "EXAMINED",
                "conformance_result": outcome,
                "remarks": "SYNTHETIC TEST FIXTURE ONLY",
            },
        )
        assert response.status_code == 200, response.text
        result[item["item_key"]] = response.json()
    return result


async def attach_document_evidence(client, world, session_path, item):
    import hashlib

    from app.models import AttachmentUpload

    sha = hashlib.sha256(PDF).hexdigest()
    presign = await client.post(
        "/api/v1/attachments/presign",
        headers={"If-Match": f'"{item["lock_version"]}"'},
        json={
            "laboratory_id": str(world.labs[0].id),
            "entity_type": "construction_items",
            "entity_id": item["id"],
            "purpose": "section16_supporting",
            "file_name": "construction-evidence.pdf",
            "content_type": "application/pdf",
            "file_size": len(PDF),
            "sha256": sha,
        },
    )
    assert presign.status_code == 201, presign.text

    async with world.factory() as session:
        upload = await session.get(
            AttachmentUpload,
            UUID(presign.json()["upload_id"]),
        )
        world.storage.objects[upload.storage_key] = StoredObject(
            PDF,
            "application/pdf",
            "staged-v1",
        )

    complete = await client.post(
        "/api/v1/attachments/complete",
        headers={"If-Match": f'"{item["lock_version"]}"'},
        json={"upload_id": presign.json()["upload_id"]},
    )
    assert complete.status_code == 201, complete.text

    refreshed = (await client.get(session_path + "/construction/items")).json()
    return next(value for value in refreshed if value["id"] == item["id"])


async def prepare_phase12_world(world, monkeypatch):
    from tests.phase5_fixtures import prepare_world

    world = await prepare_world(world)
    await install_phase12_synthetic(world, monkeypatch)
    return world
