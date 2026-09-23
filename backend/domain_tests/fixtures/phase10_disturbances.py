"""Synthetic-only Phase 10 disturbance fixtures. Not regulatory data."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.numbers import exact
from app.compliance.phase10 import (
    CONTEXT_SCHEMAS,
    DISTURBANCE_BURST,
    DISTURBANCE_CALIBRATION,
    DISTURBANCE_CLASSIFICATION,
    DISTURBANCE_CODES,
    DISTURBANCE_CONDUCTED_RF,
    DISTURBANCE_ESD,
    DISTURBANCE_POLICY_KEYS,
    DISTURBANCE_RADIATED_RF,
    DISTURBANCE_SURGE,
    DISTURBANCE_VEHICLE_SUPPLY,
    DISTURBANCE_VOLTAGE_DIP,
    OBSERVATION_SCHEMAS,
    DisturbanceSeverity,
    disturbance_registrations,
)
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument

SYNTHETIC_RESPONSE = "SYNTHETIC_ACCEPTED_RESPONSE"


def _rule(key, kind, policy=None, *, verified=True, dependencies=("BASE",)):
    return dict(
        key=key,
        kind=kind,
        description="SYNTHETIC TEST FIXTURE ONLY",
        source=SOURCE,
        verification=VERIFICATION if verified else {},
        dependencies=list(dependencies),
        parameters=[] if policy is None else [dict(name="POLICY_JSON", value=json.dumps(policy))],
    )


def variants(code):
    return tuple(variant for variant, _ in CONTEXT_SCHEMAS[code])


def severities(code, variant=None):
    if code == DISTURBANCE_VOLTAGE_DIP:
        rows = (
            dict(severity_id="dip-a", case="SYNTHETIC_DIP_A", reduction_percent="25", cycles="2"),
            dict(
                severity_id="interrupt-a",
                case="SYNTHETIC_INTERRUPTION",
                reduction_percent="0",
                cycles="3",
            ),
        )
    elif code == DISTURBANCE_BURST:
        rows = (
            dict(
                severity_id="burst-power-positive",
                line_type="POWER",
                polarity="POSITIVE",
                amplitude_v="100",
                duration_s="1",
            ),
            dict(
                severity_id="burst-io-negative",
                line_type="IO",
                port="SYNTHETIC_IO",
                polarity="NEGATIVE",
                amplitude_v="50",
                duration_s="1",
            ),
        )
    elif code == DISTURBANCE_SURGE:
        rows = (
            dict(
                severity_id="surge-ll-positive",
                line_type="POWER",
                coupling_mode="LINE_TO_LINE",
                polarity="POSITIVE",
                voltage_kv="0.25",
                phase_angle_deg="0",
            ),
            dict(
                severity_id="surge-le-negative",
                line_type="POWER",
                coupling_mode="LINE_TO_EARTH",
                polarity="NEGATIVE",
                voltage_kv="0.5",
                phase_angle_deg="90",
            ),
        )
    elif code == DISTURBANCE_ESD:
        rows = (
            dict(
                severity_id="esd-direct-contact",
                application_type="DIRECT",
                discharge_mode="CONTACT",
                location="SYNTHETIC_PANEL",
                polarity="POSITIVE",
                voltage_kv="2",
            ),
            dict(
                severity_id="esd-indirect-air",
                application_type="INDIRECT",
                discharge_mode="AIR",
                location="SYNTHETIC_PLANE",
                polarity="NEGATIVE",
                voltage_kv="3",
            ),
        )
    elif code == DISTURBANCE_RADIATED_RF:
        rows = (
            dict(
                severity_id="radiated-low",
                frequency_hz="1000000",
                field_strength_v_per_m="2",
                modulation_percent="25",
                modulation_frequency_hz="100",
            ),
            dict(
                severity_id="radiated-high",
                frequency_hz="2000000",
                field_strength_v_per_m="2",
                modulation_percent="25",
                modulation_frequency_hz="100",
            ),
        )
    elif code == DISTURBANCE_CONDUCTED_RF:
        rows = (
            dict(
                severity_id="conducted-power",
                frequency_hz="100000",
                amplitude_v="2",
                port="SYNTHETIC_POWER",
                modulation_percent="25",
                modulation_frequency_hz="100",
            ),
            dict(
                severity_id="conducted-data",
                frequency_hz="200000",
                amplitude_v="2",
                port="SYNTHETIC_DATA",
                modulation_percent="25",
                modulation_frequency_hz="100",
            ),
        )
    elif code == DISTURBANCE_VEHICLE_SUPPLY:
        if variant == "NON_SUPPLY_LINE_COUPLING":
            rows = (
                dict(
                    severity_id="vehicle-coupling-a",
                    pulse="SYNTHETIC_A",
                    line_type="NON_SUPPLY",
                    port="SYNTHETIC_SIGNAL",
                    battery_voltage_v="12",
                    conducted_voltage_v="5",
                ),
                dict(
                    severity_id="vehicle-coupling-b",
                    pulse="SYNTHETIC_B",
                    line_type="NON_SUPPLY",
                    port="SYNTHETIC_CONTROL",
                    battery_voltage_v="12",
                    conducted_voltage_v="-5",
                ),
            )
        else:
            rows = (
                dict(
                    severity_id="vehicle-supply-1",
                    pulse="SYNTHETIC_1",
                    line_type="SUPPLY",
                    battery_voltage_v="12",
                    conducted_voltage_v="8",
                ),
                dict(
                    severity_id="vehicle-supply-2",
                    pulse="SYNTHETIC_2",
                    line_type="SUPPLY",
                    battery_voltage_v="12",
                    conducted_voltage_v="-8",
                ),
            )
    else:
        raise ValueError("Unknown disturbance code")

    return tuple(
        DisturbanceSeverity.model_validate(
            row
            | {
                "waveform_reference": f"SYNTHETIC_TRACE_{row['severity_id']}",
                "standard_profile_reference": "SYNTHETIC_PROFILE_ONLY",
            }
        )
        for row in rows
    )


def _profile(code, variant):
    return dict(
        procedure_variant=variant,
        evaluation_context="SYNTHETIC",
        required_severities=[x.model_dump(mode="json") for x in severities(code, variant)],
        repetitions_per_severity=2,
        deviation_limit_multiplier_e="1",
        deviation_operator="<=",
        deviation_semantics="ABSOLUTE",
        accepted_fault_responses=[SYNTHETIC_RESPONSE],
        require_warm_up=True,
        require_environment_stabilized=True,
        require_peripherals_connected=True,
        require_no_load_deviation=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_waveform_reference=True,
        require_fault_response_evidence=True,
        require_state_trace=True,
        require_monotonic_timestamps=True,
    )


def _app_policy(code):
    scenarios = [dict(procedure_variant=variant, scenario="fixture") for variant in variants(code)]
    if code == DISTURBANCE_VEHICLE_SUPPLY:
        cases = [
            dict(
                when=dict(kind="boolean", feature="vehicle_powered", expected=True),
                decision="REQUIRED",
                reason="SYNTHETIC vehicle-powered branch",
            ),
            dict(
                when=dict(kind="boolean", feature="vehicle_powered", expected=False),
                decision="NOT_APPLICABLE",
                reason="SYNTHETIC non-vehicle branch",
            ),
        ]
    else:
        cases = [
            dict(
                when={"kind": "always"},
                decision="REQUIRED",
                reason="SYNTHETIC required branch",
            )
        ]
    return dict(schema_version="v1", scope="EACH_RANGE", scenarios=scenarios, cases=cases)


def disturbance_rules(code, *, unverified=None):
    app_key = f"{code}_APP"
    policy_key = DISTURBANCE_POLICY_KEYS[code]
    policy = dict(
        schema_version="v1",
        test_code=code,
        profiles=[_profile(code, variant) for variant in variants(code)],
    )
    rules = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule(
            app_key, "applicability_policy_v1", _app_policy(code), verified=unverified != app_key
        ),
        _rule(policy_key, "disturbance_procedure_v1", policy, verified=unverified != policy_key),
        _rule(
            DISTURBANCE_CLASSIFICATION,
            "dependency_v1",
            verified=unverified != DISTURBANCE_CLASSIFICATION,
        ),
        _rule(
            DISTURBANCE_CALIBRATION, "dependency_v1", verified=unverified != DISTURBANCE_CALIBRATION
        ),
    ]
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-PHASE10-v1",
                version=f"SYNTHETIC_TEST_PHASE10_{code}",
                standard_parts=[SOURCE],
                supported_test_codes=[code],
                source_reference="SYNTHETIC TEST FIXTURE ONLY",
            ),
            rules=rules,
            tests=[
                dict(
                    code=code,
                    section=12,
                    name="SYNTHETIC TEST FIXTURE ONLY",
                    source=SOURCE,
                    dependencies=[
                        app_key,
                        policy_key,
                        DISTURBANCE_CLASSIFICATION,
                        DISTURBANCE_CALIBRATION,
                    ],
                    implemented=True,
                    verification=VERIFICATION,
                )
            ],
            checklist=[],
        )
    )


def disturbance_context(
    code,
    *,
    variant=None,
    omit_severity=False,
    missing_waveform=False,
    **changes,
):
    variant = variant or variants(code)[0]
    items = list(severities(code, variant))
    if omit_severity:
        items = items[:-1]
    if missing_waveform:
        payload = items[0].model_dump(mode="python")
        payload["waveform_reference"] = None
        items[0] = DisturbanceSeverity.model_validate(payload)

    schema = dict(CONTEXT_SCHEMAS[code])[variant]
    payload = dict(
        procedure_variant=variant,
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        test_load_g="1000",
        warm_up_completed=True,
        environment_stabilized=True,
        peripherals_connected=True,
        no_load_deviation_g="0",
        severity_cases=[x.model_dump(mode="json") for x in items],
        environment=[
            dict(
                measured_at="2000-01-01T00:00:00Z",
                temperature_c="20",
                relative_humidity_percent="50",
                pressure_hpa="1000",
                phase="SYNTHETIC_PHASE10",
            )
        ],
        equipment=[
            dict(
                reference="SYNTHETIC_PHASE10_GENERATOR",
                category="SYNTHETIC",
            )
        ],
        evidence_hashes=["d" * 64],
    )
    payload.update(changes)
    return schema.model_validate(payload)


def disturbance_observations(
    code,
    *,
    variant=None,
    deviation_g="10",
    handled=False,
    accepted_response=True,
    omit_last=False,
    bad_repetition_order=False,
    missing_response=False,
    missing_fault_evidence=False,
    missing_state=False,
):
    variant = variant or variants(code)[0]
    schema = OBSERVATION_SCHEMAS[code]
    base = datetime(2000, 1, 1, tzinfo=UTC)
    rows = []
    sequence = 1
    for severity in severities(code, variant):
        for repetition in (1, 2):
            current_repetition = repetition
            if bad_repetition_order and sequence == 1:
                current_repetition = 2
            response = None
            response_hash = None
            if handled:
                response = (
                    SYNTHETIC_RESPONSE if accepted_response else "SYNTHETIC_UNACCEPTED_RESPONSE"
                )
                response_hash = "e" * 64
                if missing_response:
                    response = None
                if missing_fault_evidence:
                    response_hash = None
            rows.append(
                schema.model_validate(
                    dict(
                        sequence_no=sequence,
                        severity_id=severity.severity_id,
                        repetition_no=current_repetition,
                        reference_indication_g="1000",
                        disturbed_indication_g=exact("add", "1000", deviation_g),
                        fault_detected=handled,
                        fault_response=response,
                        fault_response_evidence_hash=response_hash,
                        state_before="SYNTHETIC_BEFORE",
                        state_during=None
                        if missing_state and sequence == 1
                        else "SYNTHETIC_DURING",
                        state_after="SYNTHETIC_AFTER",
                        measured_at=(base + timedelta(seconds=sequence)).isoformat(),
                    )
                )
            )
            sequence += 1
    if omit_last:
        rows = rows[:-1]

    registration = next(item for item in disturbance_registrations() if item.test_code == code)
    return registration.observations.parse(
        test_code=code,
        protocol="DISTURBANCE_V1",
        version="v1",
        rows=[row.model_dump(mode="json") for row in rows],
    )


def disturbance_engine(code):
    registration = next(item for item in disturbance_registrations() if item.test_code == code)
    return R76Engine(EvaluatorRegistry((replace(registration, synthetic_fixture=True),)))


def evaluate_disturbance(code, *, variant=None, vehicle_powered=True, **changes):
    snapshot = instrument(
        **({"vehicle_powered": vehicle_powered} if code == DISTURBANCE_VEHICLE_SUPPLY else {})
    )
    arguments = dict(
        test_code=code,
        instrument_snapshot=snapshot,
        procedure_context=disturbance_context(code, variant=variant),
        observations=disturbance_observations(code, variant=variant),
        ruleset=disturbance_rules(code),
    )
    arguments.update(changes)
    return disturbance_engine(code).evaluate(**arguments)


__all__ = [
    "DISTURBANCE_CODES",
    "disturbance_context",
    "disturbance_observations",
    "disturbance_rules",
    "evaluate_disturbance",
]
