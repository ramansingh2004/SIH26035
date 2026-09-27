"""Fix 1: Section 1 static-temperature mechanics using synthetic verified policy only."""

import json
from dataclasses import replace

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import RuleSet
from app.compliance.weighing import (
    CODE,
    POLICY,
    StaticTemperatureWeighingContext,
    section1_registration,
)
from domain_tests.fixtures.synthetic import instrument
from domain_tests.fixtures.weighing import fixture_rules


def static_rules(*, include_conditional=True):
    data = fixture_rules().model_dump(mode="json")
    for rule in data["rules"]:
        if rule["kind"] == "applicability_policy_v1":
            app = json.loads(rule["parameters"][0]["value"])
            app["scenarios"] = [
                {"procedure_variant": "STATIC_TEMPERATURE", "scenario": "static"}
            ]
            rule["parameters"][0]["value"] = json.dumps(app)
        if rule["key"] == POLICY:
            stages = [
                {
                    "stage_code": "REFERENCE_INITIAL",
                    "temperature": {"basis": "ABSOLUTE_C", "value": "20"},
                },
                {
                    "stage_code": "HIGH",
                    "temperature": {"basis": "DECLARED_MAX"},
                },
                {
                    "stage_code": "LOW",
                    "temperature": {"basis": "DECLARED_MIN"},
                },
            ]
            if include_conditional:
                stages.append(
                    {
                        "stage_code": "FIVE_C",
                        "temperature": {"basis": "ABSOLUTE_C", "value": "5"},
                        "include_when_declared_min_lte_c": "0",
                    }
                )
            stages.append(
                {
                    "stage_code": "REFERENCE_FINAL",
                    "temperature": {"basis": "ABSOLUTE_C", "value": "20"},
                }
            )
            policy = {
                "schema_version": "v2",
                "cases": [
                    {
                        "selector": {
                            "accuracy_classes": ["III"],
                            "evaluation_contexts": ["SYNTHETIC"],
                            "indication_types": ["DIGITAL"],
                            "range_types": ["SINGLE"],
                        },
                        "minimum_count": 2,
                        "stages": ["UP", "DOWN"],
                        "required_loads": [
                            {
                                "direction": "UP",
                                "load": {"basis": "ABSOLUTE_G", "value": "10000"},
                            },
                            {
                                "direction": "DOWN",
                                "load": {"basis": "ABSOLUTE_G", "value": "0"},
                            },
                        ],
                        "transition_loads": [],
                        "require_min": False,
                        "require_max": False,
                        "require_preload": True,
                        "require_stabilization": True,
                        "minimum_warmup_seconds": "1",
                        "zero_condition": "SYNTHETIC_ZERO",
                        "require_environment": True,
                        "temperature_min_c": "-10",
                        "temperature_max_c": "40",
                        "humidity_min_percent": None,
                        "humidity_max_percent": None,
                        "require_equipment": True,
                        "require_certificate": False,
                        "require_evidence": True,
                        "require_monotonic_timestamps": True,
                        "static_temperature": {
                            "stage_sequence": stages,
                            "minimum_exposure_after_stability_seconds": "7200",
                            "maximum_transition_rate_c_per_minute": "1",
                            "steady_temperature_span_fraction": "0.2",
                            "steady_temperature_span_cap_c": "5",
                            "steady_temperature_max_rate_c_per_hour": "5",
                            "high_temperature_stage_code": "HIGH",
                            "maximum_high_temperature_absolute_humidity_g_m3": "20",
                            "require_free_air_conditions": True,
                            "require_class_i_barometric_pressure_accounting": True,
                        },
                    }
                ],
            }
            rule["kind"] = "weighing_procedure_v2"
            rule["parameters"] = [
                {"name": "POLICY_JSON", "value": json.dumps(policy)}
            ]
    return RuleSet.model_validate(data)


def stage_records(*, declared_min="-10", short_exposure=False, high_humidity="10"):
    codes = ["REFERENCE_INITIAL", "HIGH", "LOW"]
    targets = ["20", "40", declared_min]
    if declared_min.startswith("-") or declared_min == "0":
        codes.append("FIVE_C")
        targets.append("5")
    codes.append("REFERENCE_FINAL")
    targets.append("20")
    rows = []
    for index, (code, target) in enumerate(zip(codes, targets, strict=True)):
        base_hour = index * 6
        stable = f"2000-01-0{1 + (base_hour // 24)}T{base_hour % 24:02d}:00:00Z"
        start_hour = base_hour + (1 if short_exposure and index == 0 else 2)
        start = f"2000-01-0{1 + (start_hour // 24)}T{start_hour % 24:02d}:00:00Z"
        end = f"2000-01-0{1 + (start_hour // 24)}T{start_hour % 24:02d}:10:00Z"
        rows.append(
            {
                "stage_code": code,
                "target_temperature_c": target,
                "temperature_stability_reached_at": stable,
                "weighing_started_at": start,
                "weighing_completed_at": end,
                "preloaded": True,
                "weighing_stabilized": True,
                "free_air_conditions": True,
                "absolute_humidity_g_m3": high_humidity if code == "HIGH" else None,
                "barometric_pressure_accounted": None,
            }
        )
    return rows


def context(*, declared_min="-10", short_exposure=False, high_humidity="10", environment=None):
    records = stage_records(
        declared_min=declared_min,
        short_exposure=short_exposure,
        high_humidity=high_humidity,
    )
    if environment is None:
        environment = []
        for record in records:
            environment.extend(
                [
                    {
                        "measured_at": record["temperature_stability_reached_at"],
                        "temperature_c": record["target_temperature_c"],
                        "phase": record["stage_code"],
                    },
                    {
                        "measured_at": record["weighing_started_at"],
                        "temperature_c": record["target_temperature_c"],
                        "phase": record["stage_code"],
                    },
                ]
            )
    return StaticTemperatureWeighingContext.model_validate(
        {
            "evaluation_context": "SYNTHETIC",
            "range_no": 1,
            "scenario": "static",
            "stages": ["UP", "DOWN"],
            "warmed_up_seconds": "2",
            "zero_condition": "SYNTHETIC_ZERO",
            "temperature_stages": records,
            "environment": environment,
            "equipment": [{"reference": "SYNTHETIC_WEIGHT", "category": "SYNTHETIC"}],
            "evidence_hashes": ["b" * 64],
        }
    )


def observations(ctx):
    rows = []
    sequence = 1
    for record in ctx.temperature_stages:
        rows.extend(
            [
                {
                    "sequence_no": sequence,
                    "load_g": "10000",
                    "indication_g": "10000",
                    "additional_load_g": "5",
                    "zero_error_g": "0",
                    "direction": "UP",
                    "measured_at": record.weighing_started_at,
                    "temperature_stage": record.stage_code,
                },
                {
                    "sequence_no": sequence + 1,
                    "load_g": "0",
                    "indication_g": "0",
                    "additional_load_g": "5",
                    "zero_error_g": "0",
                    "direction": "DOWN",
                    "measured_at": record.weighing_completed_at,
                    "temperature_stage": record.stage_code,
                },
            ]
        )
        sequence += 2
    return section1_registration().observations.parse(
        test_code=CODE,
        protocol="WEIGHING_STATIC_TEMPERATURE_V2",
        version="v2",
        rows=rows,
    )


def evaluate(ctx, rules=None, obs=None, snapshot=None):
    rules = rules or static_rules()
    snapshot = snapshot or instrument(
        indication_type="DIGITAL",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
    )
    obs = obs or observations(ctx)
    engine = R76Engine(
        EvaluatorRegistry((replace(section1_registration(), synthetic_fixture=True),))
    )
    return engine.evaluate(
        test_code=CODE,
        instrument_snapshot=snapshot,
        procedure_context=ctx,
        observations=obs,
        ruleset=rules,
    )


def test_static_temperature_complete_sequence_is_evaluable():
    ctx = context()
    result = evaluate(ctx)
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    assert len(result.calculations) == 10


def test_static_temperature_conditional_five_c_stage_is_required_when_applicable():
    ctx = context()
    data = ctx.model_dump(mode="json")
    data["temperature_stages"] = [
        item for item in data["temperature_stages"] if item["stage_code"] != "FIVE_C"
    ]
    bad = StaticTemperatureWeighingContext.model_validate(data)
    result = evaluate(bad, obs=observations(bad))
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"


def test_static_temperature_conditional_stage_is_omitted_when_declared_min_above_threshold():
    snapshot = instrument(
        indication_type="DIGITAL",
        declared_temp_min_c="10",
        declared_temp_max_c="40",
    )
    ctx = context(declared_min="10")
    result = evaluate(ctx, snapshot=snapshot)
    assert result.evaluation_status == "COMPLETE"


def test_static_temperature_requires_verified_post_stability_exposure():
    ctx = context(short_exposure=True)
    result = evaluate(ctx)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category == "TIMING" for issue in result.procedure_issues)


def test_static_temperature_high_stage_absolute_humidity_is_fail_closed():
    ctx = context(high_humidity="25")
    result = evaluate(ctx)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category == "ENVIRONMENT" for issue in result.procedure_issues)


def test_static_temperature_each_stage_requires_complete_loading_cycle():
    ctx = context()
    batch = observations(ctx)
    rows = [row.model_dump(mode="json") for row in batch.rows]
    rows.pop(3)
    for index, row in enumerate(rows, 1):
        row["sequence_no"] = index
    broken = section1_registration().observations.parse(
        test_code=CODE,
        protocol="WEIGHING_STATIC_TEMPERATURE_V2",
        version="v2",
        rows=rows,
    )
    result = evaluate(ctx, obs=broken)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(
        issue.category in {"COUNT", "ORDER", "LOAD_COVERAGE"}
        for issue in result.procedure_issues
    )


def test_section1_registry_keeps_v1_and_adds_explicit_v2_static_temperature():
    registration = section1_registration()
    assert registration.runtime_schema_versions("DIGITAL_PRE_ROUNDING") == ("v1", "v1")
    assert registration.runtime_schema_versions(
        "DIGITAL_PRE_ROUNDING",
        procedure_schema_version="v2",
        observation_schema_version="v2",
    ) == ("v2", "v2")
    assert registration.runtime_schema_versions(
        "STATIC_TEMPERATURE",
        procedure_schema_version="v2",
        observation_schema_version="v2",
    ) == ("v2", "v2")
