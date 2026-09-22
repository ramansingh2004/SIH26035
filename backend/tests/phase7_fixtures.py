"""SYNTHETIC Phase 7 PostgreSQL/API integration fixtures only.

This artifact is isolated to pytest and a *_test PostgreSQL database.  It
combines the already-tested Phase 5/6 mechanics with Phase 7 synthetic rules;
no production configuration or regulatory authority is created.
"""

from dataclasses import replace
from uuid import uuid4

from fastapi import Request

from app.api.dependencies import context, testing_service
from app.compliance.engine import R76Engine, synthetic_artifact
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase7 import (
    CREEP,
    DISCRIMINATION,
    SENSITIVITY,
    STABILITY_EQUILIBRIUM,
    ZERO_RETURN,
)
from app.compliance.ruleset import RuleSet
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.services.rulesets import RulesetService
from app.services.testing import TestingService
from domain_tests.fixtures.phase7_functional_time import (
    creep_context,
    creep_observations,
    creep_rules,
    discrimination_context,
    discrimination_observations,
    discrimination_rules,
    sensitivity_context,
    sensitivity_observations,
    sensitivity_rules,
    stability_context,
    stability_observations,
    stability_rules,
    zero_return_context,
    zero_return_observations,
    zero_return_rules,
)
from domain_tests.fixtures.synthetic import instrument
from tests.phase5_fixtures import create_session, prepare_world, seed_evidence
from tests.phase6_fixtures import phase6_fixture_rules

PHASE7_CODES = (
    DISCRIMINATION,
    SENSITIVITY,
    ZERO_RETURN,
    CREEP,
    STABILITY_EQUILIBRIUM,
)


def _rename_rule(rule: dict, mapping: dict[str, str]) -> dict:
    result = dict(rule)
    result["key"] = mapping.get(result["key"], result["key"])
    result["dependencies"] = [mapping.get(value, value) for value in result["dependencies"]]
    return result


def phase7_fixture_rules() -> RuleSet:
    """One labelled synthetic artifact through Phase 7."""

    payload = phase6_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE7_INTEGRATION"
    payload["metadata"]["edition"] = "TEST-PHASE7-v1"
    payload["metadata"]["supported_test_codes"] = list(IMPLEMENTED_TEST_CODES)
    tests = {item["code"]: item for item in payload["tests"]}
    existing_rule_keys = {rule["key"] for rule in payload["rules"]}

    factories = (
        (
            lambda: discrimination_rules(mode="DIGITAL"),
            DISCRIMINATION,
        ),
        (sensitivity_rules, SENSITIVITY),
        (zero_return_rules, ZERO_RETURN),
        (lambda: creep_rules(mode="SHORT"), CREEP),
        (stability_rules, STABILITY_EQUILIBRIUM),
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


def phase7_fixture_engine() -> R76Engine:
    registrations = tuple(
        replace(item, synthetic_fixture=True) for item in implemented_registry().registrations
    )
    return R76Engine(EvaluatorRegistry(registrations))


class SyntheticPhase7TestingService(TestingService):
    __test__ = False

    def __init__(self, session, request_context):
        super().__init__(session, request_context)
        self.engine = phase7_fixture_engine()

    def artifact_is_production(self, rules):
        assert synthetic_artifact(rules)
        return True

    def require_production_output(self, synthetic):
        assert synthetic is True


async def install_phase7_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase7_fixture_rules()
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

    async def service(request: Request):
        async with world.factory() as session:
            yield SyntheticPhase7TestingService(
                session,
                context(request),
            )

    world.app.dependency_overrides[testing_service] = service


async def configured_phase7(client, world):
    response, _, _ = await create_session(client, world, synthetic=True)
    path = "/api/v1/test-sessions/" + response.json()["id"]
    snapshot = instrument(
        indication_type="DIGITAL",
        is_self_indicating=False,
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


async def started_phase7_runs(client, world):
    response, session_path = await configured_phase7(client, world)
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
    DISCRIMINATION: discrimination_context,
    SENSITIVITY: sensitivity_context,
    ZERO_RETURN: zero_return_context,
    CREEP: creep_context,
    STABILITY_EQUILIBRIUM: stability_context,
}
OBSERVATIONS = {
    DISCRIMINATION: discrimination_observations,
    SENSITIVITY: sensitivity_observations,
    ZERO_RETURN: zero_return_observations,
    CREEP: creep_observations,
    STABILITY_EQUILIBRIUM: stability_observations,
}


async def populate_phase7_run(client, world, code, run_path):
    current = await client.get(run_path)
    procedure = CONTEXTS[code](
        environment=(),
        equipment=(),
        evidence_hashes=(),
    )
    response = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": procedure.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text

    for row in OBSERVATIONS[code]().rows:
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
        },
    )
    assert response.status_code == 201, response.text

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC",
            "reference_number": (f"SYNTHETIC_PHASE7_{code}_{uuid4().hex}"),
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


async def prepare_phase7_world(world, monkeypatch):
    world = await prepare_world(world)
    await install_phase7_synthetic(world, monkeypatch)
    return world
