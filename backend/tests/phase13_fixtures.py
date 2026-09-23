"""SYNTHETIC Phase 13 checklist integration fixture only."""

from uuid import UUID

from app.compliance.ruleset import RuleSet
from app.services.rulesets import RulesetService
from app.storage.objects import StoredObject
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION
from tests.phase11_fixtures import configured_phase11
from tests.phase12_fixtures import prepare_phase12_world
from tests.test_storage import PDF

GROUPS = (
    "GENERAL",
    "DIRECT_SALES",
    "ELECTRONIC",
    "SOFTWARE_CONTROLLED",
)


def policy(*, feature=None):
    conditions = []
    if feature is not None:
        conditions.append({"feature": feature, "equals": True})
    return {
        "schema_version": "v1",
        "mode": "ALL",
        "conditions": conditions,
        "when_match": "REQUIRED",
        "when_not_match": "NOT_APPLICABLE",
        "match_reason": "SYNTHETIC TEST FIXTURE ONLY - applicable",
        "no_match_reason": "SYNTHETIC TEST FIXTURE ONLY - excluded",
    }


def phase13_fixture_rules() -> RuleSet:
    from tests.phase12_fixtures import phase12_fixture_rules

    payload = phase12_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE13_INTEGRATION"
    payload["metadata"]["edition"] = "TEST-PHASE13-v1"
    payload["checklist"] = [
        {
            "key": "GENERAL_SYNTHETIC_VERIFIED",
            "group": "GENERAL",
            "text": "SYNTHETIC TEST FIXTURE ONLY - general requirement",
            "source": SOURCE,
            "verification": VERIFICATION,
            "applicability": policy(),
            "evidence_required": False,
        },
        {
            "key": "DIRECT_SALES_SYNTHETIC_VERIFIED",
            "group": "DIRECT_SALES",
            "text": "SYNTHETIC TEST FIXTURE ONLY - direct sales requirement",
            "source": SOURCE,
            "verification": VERIFICATION,
            "applicability": policy(feature="is_direct_sales"),
            "evidence_required": False,
        },
        {
            "key": "ELECTRONIC_SYNTHETIC_VERIFIED",
            "group": "ELECTRONIC",
            "text": "SYNTHETIC TEST FIXTURE ONLY - electronic evidence requirement",
            "source": SOURCE,
            "verification": VERIFICATION,
            "applicability": policy(feature="is_electronic"),
            "evidence_required": True,
        },
        {
            "key": "SOFTWARE_SYNTHETIC_VERIFIED",
            "group": "SOFTWARE_CONTROLLED",
            "text": "SYNTHETIC TEST FIXTURE ONLY - software requirement",
            "source": SOURCE,
            "verification": VERIFICATION,
            "applicability": policy(feature="is_software_controlled"),
            "evidence_required": False,
        },
    ]
    return RuleSet.model_validate(payload)


async def install_phase13_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase13_fixture_rules()
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


async def prepare_phase13_world(world, monkeypatch):
    world = await prepare_phase12_world(world, monkeypatch)
    await install_phase13_synthetic(world, monkeypatch)
    return world


async def start_phase13_examination(client, world):
    response, session_path = await configured_phase11(client, world)

    snapshot = response.json()["instrument_snapshot"]
    snapshot["is_direct_sales"] = False
    snapshot["is_software_controlled"] = True

    response = await client.post(
        session_path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={"instrument_snapshot": snapshot},
    )
    assert response.status_code == 200, response.text

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


async def fill_required_rows(client, session_path, *, fail_key=None):
    rows = (await client.get(session_path + "/checklist")).json()
    result = {}
    for row in rows:
        if row["applicability_status"] != "REQUIRED":
            result[row["requirement_key"]] = row
            continue
        outcome = "FAIL" if row["requirement_key"] == fail_key else "PASS"
        response = await client.patch(
            session_path + "/checklist/" + row["checklist_rule_id"],
            headers={"If-Match": f'"{row["lock_version"]}"'},
            json={
                "response_result": outcome,
                "remarks": "SYNTHETIC TEST FIXTURE ONLY",
            },
        )
        assert response.status_code == 200, response.text
        result[row["requirement_key"]] = response.json()
    return result


async def attach_checklist_evidence(client, world, session_path, row):
    import hashlib

    from app.models import AttachmentUpload

    sha = hashlib.sha256(PDF).hexdigest()
    presign = await client.post(
        "/api/v1/attachments/presign",
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={
            "laboratory_id": str(world.labs[0].id),
            "entity_type": "checklist_responses",
            "entity_id": row["id"],
            "purpose": "section17_supporting",
            "file_name": "checklist-evidence.pdf",
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
            "stage13-v1",
        )

    complete = await client.post(
        "/api/v1/attachments/complete",
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={"upload_id": presign.json()["upload_id"]},
    )
    assert complete.status_code == 201, complete.text

    refreshed = (await client.get(session_path + "/checklist")).json()
    return next(value for value in refreshed if value["id"] == row["id"])
