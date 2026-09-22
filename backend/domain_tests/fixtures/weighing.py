"""SYNTHETIC TEST FIXTURE ONLY: never seeded or registered by the application."""

import json
from dataclasses import replace

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import RuleSet
from app.compliance.weighing import (
    CALIBRATION,
    CLASSIFICATION,
    CODE,
    MPE,
    POLICY,
    WeighingContext,
    section1_registration,
)
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument, ruleset


def fixture_rules(**changes):
    data = ruleset().model_dump(mode="json")
    app = json.loads(data["rules"][0]["parameters"][0]["value"])
    app["scenarios"] = [{"procedure_variant": "DIGITAL_PRE_ROUNDING", "scenario": "fixture"}]
    data["rules"][0]["parameters"][0]["value"] = json.dumps(app)
    data["rules"][1]["key"] = MPE
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        indication_type="DIGITAL",
        range_type="SINGLE",
        interval_basis="e",
        minimum_count=2,
        stages=["UP", "DOWN"],
        required_loads=[
            {"direction": "UP", "load_g": "10000"},
            {"direction": "DOWN", "load_g": "0"},
        ],
        transition_loads=[],
        require_min=False,
        require_max=False,
        require_preload=True,
        require_stabilization=True,
        minimum_warmup_seconds="1",
        zero_condition="SYNTHETIC_ZERO",
        require_environment=True,
        temperature_min_c="15",
        temperature_max_c="25",
        humidity_min_percent=None,
        humidity_max_percent=None,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    policy.update(changes)
    data["rules"][2].update(
        key=POLICY,
        kind="weighing_procedure_v1",
        parameters=[dict(name="POLICY_JSON", value=json.dumps(policy))],
    )
    for key in (CLASSIFICATION, CALIBRATION):
        data["rules"].append(
            dict(
                key=key,
                kind="dependency_v1",
                description="SYNTHETIC ONLY",
                source=SOURCE,
                verification=VERIFICATION,
                dependencies=["BASE"],
            )
        )
    data["tests"][0]["dependencies"] = ["APP", MPE, POLICY, CLASSIFICATION, CALIBRATION]
    return RuleSet.model_validate(data)


def fixture_context(**changes):
    return WeighingContext.model_validate(
        dict(
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            stages=["UP", "DOWN"],
            preloaded=True,
            warmed_up_seconds="2",
            stabilized=True,
            zero_condition="SYNTHETIC_ZERO",
            environment=[dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20")],
            equipment=[dict(reference="SYNTHETIC_WEIGHT", category="SYNTHETIC")],
            evidence_hashes=["b" * 64],
        )
        | changes
    )


def fixture_observations(error="20"):
    from app.compliance.numbers import exact

    return section1_registration().observations.parse(
        test_code=CODE,
        protocol="WEIGHING_V1",
        version="v1",
        rows=[
            dict(
                sequence_no=1,
                load_g="10000",
                indication_g=exact("add", "10000", error),
                additional_load_g="5",
                zero_error_g="0",
                direction="UP",
                measured_at="2000-01-01T00:00:01Z",
            ),
            dict(
                sequence_no=2,
                load_g="0",
                indication_g="0",
                additional_load_g="5",
                zero_error_g="0",
                direction="DOWN",
                measured_at="2000-01-01T00:00:02Z",
            ),
        ],
    )


def fixture_engine():
    return R76Engine(EvaluatorRegistry((replace(section1_registration(), synthetic_fixture=True),)))


def evaluate(**changes):
    return fixture_engine().evaluate(
        **(
            dict(
                test_code=CODE,
                instrument_snapshot=instrument(indication_type="DIGITAL"),
                procedure_context=fixture_context(),
                observations=fixture_observations(),
                ruleset=fixture_rules(),
            )
            | changes
        )
    )
