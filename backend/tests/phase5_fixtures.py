"""SYNTHETIC integration fixtures. Imported only by tests, never the application.

The private dependency override retains synthetic_fixture=True in every result.
It exists only inside isolated *_test databases; normal endpoints reject it.
"""

import json
from uuid import UUID, uuid4

from fastapi import Request

from app.api.dependencies import context, testing_service
from app.compliance.engine import synthetic_artifact
from app.compliance.ruleset import RuleSet, load_ruleset
from app.models import UserRoleAssignment
from app.services.rulesets import RulesetService, seed_phase3
from app.services.testing import TestingService
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION
from domain_tests.fixtures.weighing import fixture_engine, fixture_rules
from tests.conftest import login
from tests.test_master_data import masters


class SyntheticTestingService(TestingService):
    __test__ = False

    def __init__(self, session, request_context):
        super().__init__(session, request_context)
        self.engine = fixture_engine()

    def artifact_is_production(self, rules):
        # No production data may use this isolated test harness.
        assert synthetic_artifact(rules)
        return True

    def require_production_output(self, synthetic):
        assert synthetic is True


def full_fixture_rules():
    payload = fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE5"
    others = dict(
        schema_version="v1",
        scope="INSTRUMENT",
        scenarios=[dict(procedure_variant="UNIMPLEMENTED", scenario="fixture")],
        cases=[
            dict(when={"kind": "always"}, decision="REQUIRED", reason="Synthetic pending section")
        ],
    )
    payload["rules"].append(
        dict(
            key="OTHER_APPLICABILITY",
            kind="applicability_policy_v1",
            description="SYNTHETIC TEST FIXTURE ONLY",
            source=SOURCE,
            verification=VERIFICATION,
            parameters=[dict(name="POLICY_JSON", value=json.dumps(others))],
        )
    )
    payload["rules"].append(
        dict(
            key="RETEST_SELECTION",
            kind="run_selection_v1",
            description="SYNTHETIC TEST FIXTURE ONLY",
            source=SOURCE,
            verification=VERIFICATION,
            parameters=[
                dict(
                    name="POLICY_JSON",
                    value=json.dumps(
                        dict(
                            schema_version="v1",
                            allowed_evaluation_statuses=["COMPLETE"],
                            allowed_compliance_outcomes=["COMPLIANT", "NONCOMPLIANT"],
                            require_current_result=True,
                            allow_replacing_known_failure=True,
                        )
                    ),
                )
            ],
        )
    )
    payload["tests"][0]["implemented"] = True
    for test in load_ruleset().tests:
        if test.code == "WEIGHING_PERFORMANCE":
            continue
        entry = test.model_dump(mode="json")
        entry.update(source=SOURCE, verification=VERIFICATION, dependencies=["OTHER_APPLICABILITY"])
        payload["tests"].append(entry)
    return RuleSet.model_validate(payload)


async def prepare_world(world):
    async with world.factory() as session, session.begin():
        for name, lab in (("local", 0), ("other", 1)):
            session.add(
                UserRoleAssignment(
                    user_id=world.users[name].id,
                    role_id=world.roles["LAB_ENGINEER"],
                    scope_type="LABORATORY",
                    laboratory_id=world.labs[lab].id,
                    assigned_by=world.users["admin"].id,
                )
            )
    async with world.factory() as session:
        world.ruleset_id = await seed_phase3(session)
    return world


async def install_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = full_fixture_rules()
    # Trusted loader replacement is scoped to this test process; never an API flag.
    with monkeypatch.context() as patch:
        patch.setattr(service_module, "load_ruleset", lambda: fixture)
        async with world.factory() as session, session.begin():
            row = await RulesetService(session, RequestContext()).insert_artifact()
            row.ruleset_status = "ACTIVE"
            row.validation_summary = {"authoritative": True, "SYNTHETIC_TEST_FIXTURE_ONLY": True}
            world.synthetic_ruleset_id = str(row.id)

    async def service(request: Request):
        async with world.factory() as session:
            yield SyntheticTestingService(session, context(request))

    world.app.dependency_overrides[testing_service] = service
    # There is deliberately no production setting or route for this override.


async def create_session(client, world, *, synthetic=False):
    _, instrument = await masters(client, world)
    instrument_id = instrument.json()["id"]
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/ranges",
        headers={"If-Match": instrument.headers["etag"]},
        json=dict(
            range_no=1,
            max_capacity_g="10000",
            min_capacity_g="0",
            scale_interval_d_g="0.1",
            verification_interval_e_g="10",
        ),
    )
    assert response.status_code == 201, response.text
    await login(client, world, "local")
    payload = dict(
        instrument_id=instrument_id,
        rule_set_id=world.synthetic_ruleset_id if synthetic else world.ruleset_id,
        evaluation_context="SYNTHETIC" if synthetic else "INITIAL_VERIFICATION",
    )
    key = uuid4().hex
    response = await client.post(
        "/api/v1/test-sessions", json=payload, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201, response.text
    return response, payload, key


async def configured(client, world, *, synthetic=False):
    from domain_tests.fixtures.synthetic import instrument

    response, payload, key = await create_session(client, world, synthetic=synthetic)
    path = "/api/v1/test-sessions/" + response.json()["id"]
    response = await client.post(
        path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={"instrument_snapshot": instrument(indication_type="DIGITAL").model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text
    return response, path


async def started_run(client, world):
    response, path = await configured(client, world, synthetic=True)
    response = await client.post(
        path + "/confirm-applicability",
        headers={"If-Match": response.headers["etag"]},
        json={"elections": {}},
    )
    assert response.status_code == 200, response.text
    requirements = (await client.get(path + "/requirements")).json()
    requirement = next(
        r for r in requirements if r["slot_snapshot"]["test_code"] == "WEIGHING_PERFORMANCE"
    )
    response = await client.post(
        path + "/start-testing", headers={"If-Match": response.headers["etag"]}
    )
    assert response.status_code == 200, response.text
    run_path = "/api/v1/test-runs/" + requirement["selected_run_id"]
    response = await client.post(run_path + "/start", headers={"If-Match": '"1"'})
    assert response.status_code == 200, response.text
    return path, run_path, requirement


async def populate(client, world, run_path):
    from domain_tests.fixtures.weighing import fixture_context, fixture_observations

    current = await client.get(run_path)
    ctx = fixture_context(environment=(), equipment=(), evidence_hashes=())
    result = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": ctx.model_dump(mode="json")},
    )
    assert result.status_code == 200, result.text
    for row in fixture_observations().rows:
        current = await client.get(run_path)
        result = await client.post(
            run_path + "/observations",
            headers={"If-Match": current.headers["etag"]},
            json=dict(
                sequence_no=row.sequence_no,
                observation_type="WEIGHING_PERFORMANCE",
                payload_schema_version="v1",
                payload=row.model_dump(mode="json"),
            ),
        )
        assert result.status_code == 201, result.text
    current = await client.get(run_path)
    result = await client.post(
        run_path + "/environment",
        headers={"If-Match": current.headers["etag"]},
        json=dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20"),
    )
    assert result.status_code == 201, result.text
    equipment = await client.post(
        "/api/v1/test-equipment",
        json=dict(
            laboratory_id=str(world.labs[0].id),
            category="SYNTHETIC",
            reference_number="SYNTHETIC_WEIGHT_" + uuid4().hex,
        ),
    )
    assert equipment.status_code == 201, equipment.text
    current = await client.get(run_path)
    result = await client.post(
        run_path + "/equipment/" + equipment.json()["id"],
        headers={"If-Match": current.headers["etag"]},
        json={},
    )
    assert result.status_code == 201, result.text


async def seed_evidence(world, run_id):
    """Metadata-only fixture; does NOT establish an S3/MinIO acceptance result."""
    from app.models import Attachment, AttachmentLink

    async with world.factory() as session, session.begin():
        item = Attachment(
            id=uuid4(),
            laboratory_id=world.labs[0].id,
            attachment_type="EVIDENCE",
            file_name="synthetic.pdf",
            content_type="application/pdf",
            file_size=1,
            storage_provider="minio",
            storage_key="SYNTHETIC/" + uuid4().hex,
            object_version="fixture",
            sha256="b" * 64,
            uploaded_by=world.users["local"].id,
            metadata_json={},
        )
        session.add(item)
        await session.flush()
        session.add(
            AttachmentLink(
                attachment_id=item.id,
                entity_type="test_runs",
                entity_id=UUID(run_id),
                purpose="synthetic",
                linked_by=world.users["local"].id,
            )
        )
    return item.id
