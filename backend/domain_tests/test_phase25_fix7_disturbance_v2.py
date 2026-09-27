"""Phase 25 Fix 7: native v2 disturbance runtime contracts."""

import json
from datetime import UTC, datetime, timedelta

from app.compliance.phase10 import (
    DISTURBANCE_BURST,
    DISTURBANCE_POLICY_KEYS,
    disturbance_registrations,
)
from app.compliance.ruleset import RuleSet
from app.compliance.stage4_native_schemas import (
    DisturbanceContextV2,
    DisturbanceObservationV2,
)
from domain_tests.fixtures.phase10_disturbances import (
    disturbance_engine,
    disturbance_rules,
)
from domain_tests.fixtures.synthetic import instrument


def rules_v2():
    data = disturbance_rules(DISTURBANCE_BURST).model_dump(mode="json")
    key = DISTURBANCE_POLICY_KEYS[DISTURBANCE_BURST]
    rule = next(item for item in data["rules"] if item["key"] == key)
    rule["kind"] = "disturbance_procedure_v2"
    rule["parameters"] = [
        {
            "name": "POLICY_JSON",
            "value": json.dumps(
                {
                    "schema_version": "v2",
                    "test_code": DISTURBANCE_BURST,
                    "profiles": [
                        {
                            "procedure_variant": "BURST_LINES",
                            "evaluation_context": "SYNTHETIC",
                            "severities": [
                                {
                                    "severity_id": "power-positive",
                                    "standard_reference": "SYNTHETIC-STANDARD",
                                    "application": "POWER_LINE",
                                    "level": "SYNTHETIC",
                                    "amplitude": "1",
                                    "amplitude_unit": "kV",
                                    "duration_seconds": "1",
                                    "polarity": "POSITIVE",
                                    "port_category": "POWER",
                                }
                            ],
                            "repetitions_per_severity": 2,
                            "minimum_interval_seconds": "10",
                            "deviation_limit_multiplier_e": "1",
                            "deviation_operator": "<=",
                            "deviation_semantics": "ABSOLUTE",
                            "require_warm_up": True,
                            "require_environment_stabilized": True,
                            "require_peripherals_connected": True,
                            "require_no_load_deviation": True,
                            "require_environment": True,
                            "require_equipment": True,
                            "require_certificate": False,
                            "require_evidence": True,
                            "require_fault_response_evidence": True,
                            "require_state_trace": True,
                            "require_monotonic_timestamps": True,
                            "accepted_fault_responses": [
                                "SYNTHETIC_ACCEPTED_RESPONSE"
                            ],
                        }
                    ],
                }
            ),
        }
    ]
    return RuleSet.model_validate(data)


def context(*, standard_identity="SYNTHETIC-STANDARD"):
    return DisturbanceContextV2(
        test_code=DISTURBANCE_BURST,
        procedure_variant="BURST_LINES",
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        test_load_g="1000",
        warm_up_completed=True,
        environment_stabilized=True,
        peripherals_connected=True,
        no_load_deviation_g="0",
        standard_identity=standard_identity,
        port_category="POWER",
        environment=[
            {
                "measured_at": "2000-01-01T00:00:00Z",
                "temperature_c": "20",
            }
        ],
        equipment=[
            {
                "reference": "SYNTHETIC-GENERATOR",
                "category": "SYNTHETIC",
            }
        ],
        evidence_hashes=["d" * 64],
    )


def observations(*, interval_seconds=10, deviation="10", handled=False):
    base = datetime(2000, 1, 1, tzinfo=UTC)
    rows = []
    for repetition in (1, 2):
        response = "SYNTHETIC_ACCEPTED_RESPONSE" if handled else None
        rows.append(
            DisturbanceObservationV2(
                test_code=DISTURBANCE_BURST,
                sequence_no=repetition,
                severity_id="power-positive",
                repetition_no=repetition,
                application="POWER_LINE",
                port_category="POWER",
                polarity="POSITIVE",
                reference_indication_g="1000",
                disturbed_indication_g=str(1000 + int(deviation)),
                fault_detected=handled,
                fault_response=response,
                fault_response_evidence_hash=("e" * 64 if handled else None),
                state_before="BEFORE",
                state_during="DURING",
                state_after="AFTER",
                measured_at=(
                    base + timedelta(seconds=(repetition - 1) * interval_seconds)
                ),
            )
        )
    registration = next(
        item
        for item in disturbance_registrations()
        if item.test_code == DISTURBANCE_BURST
    )
    return registration.observations.parse(
        test_code=DISTURBANCE_BURST,
        protocol="DISTURBANCE_V2",
        version="v2",
        rows=[row.model_dump(mode="json") for row in rows],
    )


def evaluate(**changes):
    arguments = {
        "test_code": DISTURBANCE_BURST,
        "instrument_snapshot": instrument(),
        "procedure_context": context(),
        "observations": observations(),
        "ruleset": rules_v2(),
    }
    arguments.update(changes)
    return disturbance_engine(DISTURBANCE_BURST).evaluate(**arguments)


def test_v2_disturbance_runtime_completes_at_minimum_interval_boundary():
    result = evaluate()
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"


def test_v2_disturbance_runtime_rejects_short_event_interval():
    result = evaluate(observations=observations(interval_seconds=9))
    assert result.evaluation_status == "INCOMPLETE"
    assert any(
        item.category == "TIMING"
        and "below verified minimum" in item.reason
        for item in result.procedure_issues
    )


def test_v2_disturbance_runtime_requires_matching_standard_identity():
    result = evaluate(
        procedure_context=context(standard_identity="WRONG-STANDARD")
    )
    assert result.evaluation_status == "INCOMPLETE"
    assert any(item.category == "EVIDENCE" for item in result.procedure_issues)


def test_v2_disturbance_runtime_preserves_accepted_fault_branch():
    result = evaluate(
        observations=observations(deviation="20", handled=True)
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"


def test_v2_disturbance_runtime_excessive_unhandled_effect_fails():
    result = evaluate(observations=observations(deviation="20"))
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
