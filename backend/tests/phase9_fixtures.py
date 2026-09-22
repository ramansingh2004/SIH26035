"""SYNTHETIC Phase 9 PostgreSQL/API integration fixtures only.

This artifact is isolated to pytest and an isolated *_test PostgreSQL database.
It extends the accepted Phase 8 synthetic artifact with Sections 13 and 14.
No production regulatory rule or official authority is created.
"""

from dataclasses import replace
from uuid import uuid4

from fastapi import Request

from app.api.dependencies import context, testing_service
from app.compliance.engine import R76Engine, synthetic_artifact
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase9 import DAMP_HEAT, SPAN_STABILITY
from app.compliance.ruleset import RuleSet
from app.compliance.suite import (
    IMPLEMENTED_TEST_CODES,
    implemented_registry,
)
from app.services.rulesets import RulesetService
from app.services.testing import TestingService
from domain_tests.fixtures.phase9_climatic import (
    damp_heat_context,
    damp_heat_observations,
    damp_heat_rules,
    span_context,
    span_observations,
    span_rules,
)
from domain_tests.fixtures.synthetic import instrument
from tests.phase5_fixtures import (
    create_session,
    prepare_world,
    seed_evidence,
)
from tests.phase8_fixtures import phase8_fixture_rules

PHASE9_CODES = (
    DAMP_HEAT,
    SPAN_STABILITY,
)


def _rename_rule(rule: dict, mapping: dict[str, str]) -> dict:
    result = dict(rule)
    result["key"] = mapping.get(
        result["key"],
        result["key"],
    )
    result["dependencies"] = [mapping.get(value, value) for value in result["dependencies"]]
    return result


def phase9_fixture_rules() -> RuleSet:
    """One labelled synthetic artifact through Phase 9."""

    payload = phase8_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE9_INTEGRATION"
    payload["metadata"]["edition"] = "TEST-PHASE9-v1"
    payload["metadata"]["supported_test_codes"] = list(IMPLEMENTED_TEST_CODES)
    tests = {item["code"]: item for item in payload["tests"]}
    existing_rule_keys = {rule["key"] for rule in payload["rules"]}

    factories = (
        (damp_heat_rules, DAMP_HEAT),
        (span_rules, SPAN_STABILITY),
    )

    for factory, code in factories:
        specialized = factory().model_dump(mode="json")
        rename = {}
        definition = dict(specialized["tests"][0])

        for rule in specialized["rules"]:
            if rule["key"] == "BASE":
                continue
            renamed = _rename_rule(rule, rename)
            if renamed["key"] not in existing_rule_keys:
                payload["rules"].append(renamed)
                existing_rule_keys.add(renamed["key"])

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


def phase9_fixture_engine() -> R76Engine:
    registrations = tuple(
        replace(item, synthetic_fixture=True) for item in implemented_registry().registrations
    )
    return R76Engine(EvaluatorRegistry(registrations))


class SyntheticPhase9TestingService(TestingService):
    __test__ = False

    def __init__(self, session, request_context):
        super().__init__(session, request_context)
        self.engine = phase9_fixture_engine()

    def artifact_is_production(self, rules):
        assert synthetic_artifact(rules)
        return True

    def require_production_output(self, synthetic):
        assert synthetic is True


async def install_phase9_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase9_fixture_rules()
    with monkeypatch.context() as patch:
        patch.setattr(
            service_module,
            "load_ruleset",
            lambda: fixture,
        )
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

    async def service(request: Request):
        async with world.factory() as session:
            yield SyntheticPhase9TestingService(
                session,
                context(request),
            )

    world.app.dependency_overrides[testing_service] = service


async def configured_phase9(client, world):
    response, _, _ = await create_session(
        client,
        world,
        synthetic=True,
    )
    path = "/api/v1/test-sessions/" + response.json()["id"]
    snapshot = instrument(
        indication_type="DIGITAL",
        is_self_indicating=False,
        load_receptor_type="RECTANGULAR",
        support_point_count=4,
        tare_type="SUBTRACTIVE",
        maximum_tare_g="5000",
        zero_tracking_available=True,
        level_indicator_available=False,
        automatic_tilt_sensor=False,
        is_portable=False,
        is_mobile=False,
        power_supply_type="AC",
        nominal_voltage="230",
        min_voltage="200",
        max_voltage="250",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
    )
    response = await client.post(
        path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={"instrument_snapshot": snapshot.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text
    return response, path


async def started_phase9_runs(client, world):
    response, session_path = await configured_phase9(
        client,
        world,
    )
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
    DAMP_HEAT: damp_heat_context,
    SPAN_STABILITY: span_context,
}
OBSERVATIONS = {
    DAMP_HEAT: damp_heat_observations,
    SPAN_STABILITY: span_observations,
}


async def populate_phase9_run(
    client,
    world,
    code,
    run_path,
    *,
    procedure=None,
    observations=None,
):
    current = await client.get(run_path)
    if procedure is None:
        procedure = CONTEXTS[code]()
    procedure = type(procedure).model_validate(
        procedure.model_dump(mode="python")
        | {
            "environment": (),
            "equipment": (),
            "evidence_hashes": (),
        }
    )
    response = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": procedure.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text

    batch = observations or OBSERVATIONS[code]()
    for row in batch.rows:
        current = await client.get(run_path)
        response = await client.post(
            run_path + "/observations",
            headers={"If-Match": current.headers["etag"]},
            json={
                "sequence_no": row.sequence_no,
                "observation_type": code,
                "payload_schema_version": (row.observation_schema_version),
                "payload": row.model_dump(mode="json"),
            },
        )
        assert response.status_code == 201, response.text

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/environment",
        headers={"If-Match": current.headers["etag"]},
        json={
            "measured_at": "2000-01-01T00:00:00Z",
            "temperature_c": "20",
            "relative_humidity_percent": "50",
            "barometric_pressure_hpa": "1000",
            "phase": "SYNTHETIC_PHASE9",
        },
    )
    assert response.status_code == 201, response.text

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC",
            "reference_number": (f"SYNTHETIC_PHASE9_{code}_{uuid4().hex}"),
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

    await seed_evidence(
        world,
        run_path.rsplit("/", 1)[1],
    )


async def prepare_phase9_world(world, monkeypatch):
    world = await prepare_world(world)
    await install_phase9_synthetic(world, monkeypatch)
    return world
