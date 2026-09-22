"""SYNTHETIC Phase 6 PostgreSQL integration fixtures only.

The artifact assembled here is never seedable through production configuration.  It
exists only behind a pytest dependency override and keeps every determined result
marked ``synthetic_fixture=True``.
"""

from dataclasses import replace
from uuid import uuid4

from fastapi import Request

from app.api.dependencies import context, testing_service
from app.compliance.engine import R76Engine, synthetic_artifact
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import RuleSet
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.services.rulesets import RulesetService
from app.services.testing import TestingService
from domain_tests.fixtures.core_reusable import (
    ECCENTRICITY,
    REPEATABILITY,
    TARE,
    eccentricity_context,
    eccentricity_observations,
    eccentricity_rules,
    repeatability_context,
    repeatability_observations,
    repeatability_rules,
    tare_context,
    tare_observations,
    tare_rules,
)
from domain_tests.fixtures.synthetic import instrument
from tests.phase5_fixtures import (
    create_session,
    full_fixture_rules,
    prepare_world,
    seed_evidence,
)


def _rename_rule(rule: dict, mapping: dict[str, str]) -> dict:
    result = dict(rule)
    result["key"] = mapping.get(result["key"], result["key"])
    result["dependencies"] = [mapping.get(value, value) for value in result["dependencies"]]
    return result


def phase6_fixture_rules() -> RuleSet:
    """One labelled synthetic artifact exercising Sections 1, 3, 5 and 9."""

    payload = full_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE6_INTEGRATION"
    # Use a Phase-6-only synthetic edition so this ACTIVE pytest artifact cannot
    # collide with the Phase 5 synthetic ACTIVE artifact under uq_ruleset_active.
    # Production ruleset uniqueness remains unchanged.
    payload["metadata"]["edition"] = "TEST-PHASE6-v1"
    payload["metadata"]["supported_test_codes"] = list(IMPLEMENTED_TEST_CODES)
    tests = {item["code"]: item for item in payload["tests"]}

    for rules_factory, code, applicability_key in (
        (eccentricity_rules, ECCENTRICITY, "SECTION3_APPLICABILITY"),
        (repeatability_rules, REPEATABILITY, "SECTION5_APPLICABILITY"),
        (tare_rules, TARE, "SECTION9_APPLICABILITY"),
    ):
        specialized = rules_factory().model_dump(mode="json")
        rename = {"APP": applicability_key}
        for rule in specialized["rules"]:
            if rule["key"] == "BASE":
                continue
            payload["rules"].append(_rename_rule(rule, rename))
        definition = dict(specialized["tests"][0])
        definition["dependencies"] = [
            rename.get(value, value) for value in definition["dependencies"]
        ]
        target = tests[code]
        target.update(
            source=definition["source"],
            verification=definition["verification"],
            dependencies=definition["dependencies"],
            implemented=True,
        )

    return RuleSet.model_validate(payload)


def phase6_fixture_engine() -> R76Engine:
    registrations = tuple(
        replace(item, synthetic_fixture=True) for item in implemented_registry().registrations
    )
    return R76Engine(EvaluatorRegistry(registrations))


class SyntheticPhase6TestingService(TestingService):
    __test__ = False

    def __init__(self, session, request_context):
        super().__init__(session, request_context)
        self.engine = phase6_fixture_engine()

    def artifact_is_production(self, rules):
        assert synthetic_artifact(rules)
        return True

    def require_production_output(self, synthetic):
        assert synthetic is True


async def install_phase6_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase6_fixture_rules()
    with monkeypatch.context() as patch:
        patch.setattr(service_module, "load_ruleset", lambda: fixture)
        async with world.factory() as session, session.begin():
            row = await RulesetService(session, RequestContext()).insert_artifact()
            row.ruleset_status = "ACTIVE"
            row.validation_summary = {
                "authoritative": True,
                "SYNTHETIC_TEST_FIXTURE_ONLY": True,
            }
            world.synthetic_ruleset_id = str(row.id)

    async def service(request: Request):
        async with world.factory() as session:
            yield SyntheticPhase6TestingService(session, context(request))

    world.app.dependency_overrides[testing_service] = service


async def configured_phase6(client, world):
    response, _, _ = await create_session(client, world, synthetic=True)
    path = "/api/v1/test-sessions/" + response.json()["id"]
    snapshot = instrument(
        indication_type="DIGITAL",
        load_receptor_type="RECTANGULAR",
        support_point_count=4,
        tare_type="SUBTRACTIVE",
        maximum_tare_g="5000",
    )
    response = await client.post(
        path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={"instrument_snapshot": snapshot.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text
    return response, path


async def started_phase6_runs(client, world):
    response, session_path = await configured_phase6(client, world)
    preview = await client.post(session_path + "/applicability")
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmable"] is True
    response = await client.post(
        session_path + "/confirm-applicability",
        headers={"If-Match": response.headers["etag"]},
        json={"elections": {}},
    )
    assert response.status_code == 200, response.text
    requirements = (await client.get(session_path + "/requirements")).json()
    selected = {
        item["slot_snapshot"]["test_code"]: item
        for item in requirements
        if item["slot_snapshot"]["test_code"] in IMPLEMENTED_TEST_CODES
    }
    assert set(selected) == set(IMPLEMENTED_TEST_CODES)
    response = await client.post(
        session_path + "/start-testing",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text
    paths = {}
    for code, requirement in selected.items():
        run_path = "/api/v1/test-runs/" + requirement["selected_run_id"]
        current = await client.get(run_path)
        started = await client.post(
            run_path + "/start",
            headers={"If-Match": current.headers["etag"]},
        )
        assert started.status_code == 200, started.text
        paths[code] = run_path
    return session_path, paths, selected


CONTEXTS = {
    ECCENTRICITY: eccentricity_context,
    REPEATABILITY: repeatability_context,
    TARE: tare_context,
}
OBSERVATIONS = {
    ECCENTRICITY: eccentricity_observations,
    REPEATABILITY: repeatability_observations,
    TARE: tare_observations,
}


async def populate_phase6_run(client, world, code, run_path):
    context_factory = CONTEXTS[code]
    observation_factory = OBSERVATIONS[code]
    current = await client.get(run_path)
    procedure = context_factory(environment=(), equipment=(), evidence_hashes=())
    response = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": procedure.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text

    for row in observation_factory().rows:
        current = await client.get(run_path)
        response = await client.post(
            run_path + "/observations",
            headers={"If-Match": current.headers["etag"]},
            json={
                "sequence_no": row.sequence_no,
                "observation_type": code,
                "payload_schema_version": row.observation_schema_version,
                "payload": row.model_dump(mode="json"),
            },
        )
        assert response.status_code == 201, response.text

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/environment",
        headers={"If-Match": current.headers["etag"]},
        json={"measured_at": "2000-01-01T00:00:00Z", "temperature_c": "20"},
    )
    assert response.status_code == 201, response.text

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC",
            "reference_number": f"SYNTHETIC_{code}_{uuid4().hex}",
        },
    )
    assert equipment.status_code == 201, equipment.text
    current = await client.get(run_path)
    response = await client.post(
        run_path + "/equipment/" + equipment.json()["id"],
        headers={"If-Match": current.headers["etag"]},
        json={},
    )
    assert response.status_code == 201, response.text
    await seed_evidence(world, run_path.rsplit("/", 1)[1])


async def prepare_phase6_world(world, monkeypatch):
    world = await prepare_world(world)
    await install_phase6_synthetic(world, monkeypatch)
    return world
