"""SYNTHETIC TEST FIXTURES for Phase 8 influence evaluators only.

All values here are test mechanics, not verified OIML requirements.  Production
evaluation remains blocked unless the pinned RuleSet carries verified source
evidence for REG-05, REG-11, REG-12 and REG-16 dependencies.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase8 import (
    TEMPERATURE_ZERO,
    TEMPERATURE_ZERO_CALIBRATION,
    TEMPERATURE_ZERO_CLASSIFICATION,
    TEMPERATURE_ZERO_POLICY,
    TILTING,
    TILTING_CALIBRATION,
    TILTING_CLASSIFICATION,
    TILTING_MPE,
    TILTING_POLICY,
    VOLTAGE_CALIBRATION,
    VOLTAGE_CLASSIFICATION,
    VOLTAGE_MPE,
    VOLTAGE_POLICY,
    VOLTAGE_VARIATION,
    WARM_UP,
    WARM_UP_CALIBRATION,
    WARM_UP_CLASSIFICATION,
    WARM_UP_MPE,
    WARM_UP_POLICY,
    TemperatureZeroContext,
    TiltingContext,
    VoltageVariationContext,
    WarmUpContext,
    temperature_zero_registration,
    tilting_registration,
    voltage_variation_registration,
    warm_up_registration,
)
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument


def _rule(key, kind, policy=None, *, verified=True, dependencies=("BASE",)):
    return dict(
        key=key,
        kind=kind,
        description="SYNTHETIC TEST FIXTURE ONLY",
        source=SOURCE,
        verification=VERIFICATION if verified else {},
        dependencies=list(dependencies),
        parameters=(
            []
            if policy is None
            else [
                dict(
                    name="POLICY_JSON",
                    value=json.dumps(policy),
                )
            ]
        ),
    )


def _app_policy(variant):
    return dict(
        schema_version="v1",
        scope="EACH_RANGE",
        scenarios=[
            dict(
                procedure_variant=variant,
                scenario="fixture",
            )
        ],
        cases=[
            dict(
                when={"kind": "always"},
                decision="REQUIRED",
                reason="SYNTHETIC required fixture",
            )
        ],
    )


def _mpe_policy(*, accuracy_class="III"):
    return dict(
        schema_version="v1",
        accuracy_class=accuracy_class,
        evaluation_context="SYNTHETIC",
        operator="<=",
        semantics="ABSOLUTE",
        bands=[
            dict(
                lower_e="0",
                upper_e=None,
                lower_operator=">=",
                upper_operator="<=",
                multiplier_e="1",
            )
        ],
    )


def _ruleset(
    *,
    code,
    section,
    variant,
    policy_key,
    policy_kind,
    policy,
    extras=(),
    mpe_key=None,
    accuracy_class="III",
    unverified=None,
):
    app_key = f"{code}_APP"
    rules = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule(
            app_key,
            "applicability_policy_v1",
            _app_policy(variant),
            verified=unverified != app_key,
        ),
        _rule(
            policy_key,
            policy_kind,
            policy,
            verified=unverified != policy_key,
        ),
    ]
    if mpe_key is not None:
        rules.append(
            _rule(
                mpe_key,
                "mpe_profile_v1",
                _mpe_policy(accuracy_class=accuracy_class),
                verified=unverified != mpe_key,
            )
        )
    rules.extend(
        _rule(
            key,
            "dependency_v1",
            verified=unverified != key,
        )
        for key in extras
    )
    dependencies = [
        app_key,
        policy_key,
        *([mpe_key] if mpe_key else []),
        *extras,
    ]
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-PHASE8-v1",
                version=f"SYNTHETIC_TEST_PHASE8_{code}_{variant}",
                standard_parts=[SOURCE],
                supported_test_codes=[code],
                source_reference="SYNTHETIC TEST FIXTURE ONLY",
            ),
            rules=rules,
            tests=[
                dict(
                    code=code,
                    section=section,
                    name="SYNTHETIC TEST FIXTURE ONLY",
                    source=SOURCE,
                    dependencies=dependencies,
                    implemented=True,
                    verification=VERIFICATION,
                )
            ],
            checklist=[],
        )
    )


def _context_evidence():
    return dict(
        environment=[
            dict(
                measured_at="2000-01-01T00:00:00Z",
                temperature_c="20",
            )
        ],
        equipment=[
            dict(
                reference="SYNTHETIC_INFLUENCE_EQUIPMENT",
                category="SYNTHETIC",
            )
        ],
        evidence_hashes=["f" * 64],
    )


def _engine(registration):
    return R76Engine(EvaluatorRegistry((replace(registration, synthetic_fixture=True),)))


# ---------------------------------------------------------------------------
# Section 2
# ---------------------------------------------------------------------------


def temperature_policy(*, accuracy_class="III", **changes):
    if accuracy_class == "I":
        sequence = ["0", "1"]
        span = "1"
    else:
        sequence = ["0", "5"]
        span = "5"
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=2,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        accuracy_class=accuracy_class,
        required_temperature_sequence_c=sequence,
        normalization_span_c=span,
        limit_multiplier_e="1",
        operator="<",
        semantics="ABSOLUTE",
        require_stabilized_observations=True,
        require_zero_tracking_disabled=True,
        require_declared_temperature_range=True,
    )
    policy.update(changes)
    return policy


def temperature_rules(
    *,
    accuracy_class="III",
    unverified=None,
    **changes,
):
    return _ruleset(
        code=TEMPERATURE_ZERO,
        section=2,
        variant="TEMPERATURE_SEQUENCE",
        policy_key=TEMPERATURE_ZERO_POLICY,
        policy_kind="temperature_zero_procedure_v1",
        policy=temperature_policy(
            accuracy_class=accuracy_class,
            **changes,
        ),
        extras=(
            TEMPERATURE_ZERO_CLASSIFICATION,
            TEMPERATURE_ZERO_CALIBRATION,
        ),
        accuracy_class=accuracy_class,
        unverified=unverified,
    )


def temperature_context(*, accuracy_class="III", **changes):
    sequence = ["0", "1"] if accuracy_class == "I" else ["0", "5"]
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        temperature_sequence_c=sequence,
        zero_tracking_disabled=True,
        **_context_evidence(),
    )
    payload.update(changes)
    return TemperatureZeroContext.model_validate(payload)


def temperature_observations(
    *,
    accuracy_class="III",
    drift_g="9",
    stabilized=True,
    reverse=False,
    omit_last=False,
):
    sequence = [0, 1] if accuracy_class == "I" else [0, 5]
    rows = [
        dict(
            sequence_no=1,
            temperature_c=str(sequence[0]),
            indication_g="0",
            additional_load_g="5",
            stabilized=stabilized,
            zero_tracking_active=False,
            measured_at="2000-01-01T00:00:01Z",
        ),
        dict(
            sequence_no=2,
            temperature_c=str(sequence[1]),
            indication_g=drift_g,
            additional_load_g="5",
            stabilized=stabilized,
            zero_tracking_active=False,
            measured_at="2000-01-01T00:00:02Z",
        ),
    ]
    if reverse:
        rows = [
            dict(rows[1], sequence_no=1),
            dict(rows[0], sequence_no=2),
        ]
    if omit_last:
        rows = rows[:1]
    return temperature_zero_registration().observations.parse(
        test_code=TEMPERATURE_ZERO,
        protocol="TEMPERATURE_ZERO_V1",
        version="v1",
        rows=rows,
    )


def evaluate_temperature(*, accuracy_class="III", **changes):
    arguments = dict(
        test_code=TEMPERATURE_ZERO,
        instrument_snapshot=instrument(
            accuracy_class=accuracy_class,
            declared_temp_min_c="-10",
            declared_temp_max_c="40",
            zero_tracking_available=True,
        ),
        procedure_context=temperature_context(accuracy_class=accuracy_class),
        observations=temperature_observations(accuracy_class=accuracy_class),
        ruleset=temperature_rules(accuracy_class=accuracy_class),
    )
    arguments.update(changes)
    return _engine(temperature_zero_registration()).evaluate(**arguments)


# ---------------------------------------------------------------------------
# Section 8
# ---------------------------------------------------------------------------


def tilting_policy(*, mode="NO_LEVEL_DEVICE", **changes):
    sensor_mode = mode in {
        "AUTOMATIC_TILT_SENSOR",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
    }
    directions = ["FORWARD"] if sensor_mode else ["FORWARD", "LEFT"]
    loads = ["0"] if sensor_mode else ["0", "10000"]
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=len(directions) * len(loads) * 2,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        tilt_mode=mode,
        required_directions=directions,
        required_loads_g=loads,
        reference_tilt_value="0",
        test_tilt_value="0.05",
        unloaded_limit_multiplier_e="2",
        unloaded_operator="<=",
        unloaded_semantics="ABSOLUTE",
        require_reference_position=True,
        required_warning=True if sensor_mode else None,
        required_display_operational=False if sensor_mode else None,
        required_printing_inhibited=True if sensor_mode else None,
        required_transmission_inhibited=True if sensor_mode else None,
    )
    policy.update(changes)
    return policy


def tilting_rules(*, mode="NO_LEVEL_DEVICE", unverified=None, **changes):
    return _ruleset(
        code=TILTING,
        section=8,
        variant=mode,
        policy_key=TILTING_POLICY,
        policy_kind="tilting_procedure_v1",
        policy=tilting_policy(mode=mode, **changes),
        extras=(
            TILTING_CLASSIFICATION,
            TILTING_CALIBRATION,
        ),
        mpe_key=TILTING_MPE,
        unverified=unverified,
    )


def tilting_context(*, mode="NO_LEVEL_DEVICE", **changes):
    sensor_mode = mode in {
        "AUTOMATIC_TILT_SENSOR",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
    }
    directions = ["FORWARD"] if sensor_mode else ["FORWARD", "LEFT"]
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        procedure_variant=mode,
        tilt_mode=mode,
        reference_tilt_value="0",
        test_tilt_value="0.05",
        directions=directions,
        reference_position_confirmed=True,
        protection_behavior_checked=sensor_mode,
        **_context_evidence(),
    )
    payload.update(changes)
    return TiltingContext.model_validate(payload)


def tilting_observations(
    *,
    mode="NO_LEVEL_DEVICE",
    loaded_difference_g="10",
    unloaded_difference_g="20",
    bad_protection=False,
    omit_last=False,
):
    sensor_mode = mode in {
        "AUTOMATIC_TILT_SENSOR",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
    }
    directions = ["FORWARD"] if sensor_mode else ["FORWARD", "LEFT"]
    loads = [0] if sensor_mode else [0, 10000]
    rows = []
    sequence = 1
    for direction in directions:
        for load in loads:
            reference_indication = load
            delta = unloaded_difference_g if load == 0 else loaded_difference_g
            tilted_indication = load + int(delta)
            for stage, indication, tilt in (
                ("REFERENCE", reference_indication, "0"),
                ("TILTED", tilted_indication, "0.05"),
            ):
                row = dict(
                    sequence_no=sequence,
                    direction=direction,
                    stage=stage,
                    tilt_value=tilt,
                    load_g=str(load),
                    indication_g=str(indication),
                    additional_load_g="5",
                    zero_error_g="0",
                    measured_at=(
                        datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=sequence)
                    ).isoformat(),
                )
                if sensor_mode and stage == "TILTED":
                    row.update(
                        warning_generated=True,
                        display_operational=False,
                        printing_inhibited=True,
                        transmission_inhibited=True,
                    )
                    if bad_protection:
                        row["printing_inhibited"] = False
                rows.append(row)
                sequence += 1
    if omit_last:
        rows = rows[:-1]
    return tilting_registration().observations.parse(
        test_code=TILTING,
        protocol="TILTING_V1",
        version="v1",
        rows=rows,
    )


def evaluate_tilting(*, mode="NO_LEVEL_DEVICE", **changes):
    sensor_mode = mode in {
        "AUTOMATIC_TILT_SENSOR",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
    }
    arguments = dict(
        test_code=TILTING,
        instrument_snapshot=instrument(
            level_indicator_available=(mode == "LEVEL_INDICATOR"),
            automatic_tilt_sensor=sensor_mode,
            is_mobile=mode.startswith("MOBILE"),
        ),
        procedure_context=tilting_context(mode=mode),
        observations=tilting_observations(mode=mode),
        ruleset=tilting_rules(mode=mode),
    )
    arguments.update(changes)
    return _engine(tilting_registration()).evaluate(**arguments)


# ---------------------------------------------------------------------------
# Section 10
# ---------------------------------------------------------------------------


def warm_up_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=4,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        minimum_power_off_seconds="100",
        required_checkpoints_s=["0", "300", "900", "1800"],
        checkpoint_tolerance_s="5",
        test_load_g="10000",
        require_first_stable_indication=True,
        require_zero_after_power_on=True,
        require_stabilized_observations=True,
    )
    policy.update(changes)
    return policy


def warm_up_rules(*, unverified=None, **changes):
    return _ruleset(
        code=WARM_UP,
        section=10,
        variant="WARM_UP",
        policy_key=WARM_UP_POLICY,
        policy_kind="warm_up_procedure_v1",
        policy=warm_up_policy(**changes),
        extras=(
            WARM_UP_CLASSIFICATION,
            WARM_UP_CALIBRATION,
        ),
        mpe_key=WARM_UP_MPE,
        unverified=unverified,
    )


def warm_up_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        power_off_seconds="100",
        test_load_g="10000",
        first_stable_indication_observed=True,
        zero_set_after_power_on=True,
        **_context_evidence(),
    )
    payload.update(changes)
    return WarmUpContext.model_validate(payload)


def warm_up_observations(
    *,
    error_g="10",
    omit_checkpoint=None,
    shift_checkpoint=None,
    stabilized=True,
):
    checkpoints = [0, 300, 900, 1800]
    rows = []
    sequence = 1
    for checkpoint in checkpoints:
        if checkpoint == omit_checkpoint:
            continue
        elapsed = (
            shift_checkpoint[1]
            if shift_checkpoint and checkpoint == shift_checkpoint[0]
            else checkpoint
        )
        rows.append(
            dict(
                sequence_no=sequence,
                elapsed_s=str(elapsed),
                zero_indication_g="0",
                zero_additional_load_g="5",
                load_g="10000",
                loaded_indication_g=str(10000 + int(error_g)),
                loaded_additional_load_g="5",
                temperature_c="20",
                stabilized=stabilized,
                measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=elapsed)
                ).isoformat(),
            )
        )
        sequence += 1
    return warm_up_registration().observations.parse(
        test_code=WARM_UP,
        protocol="WARM_UP_V1",
        version="v1",
        rows=rows,
    )


def evaluate_warm_up(**changes):
    arguments = dict(
        test_code=WARM_UP,
        instrument_snapshot=instrument(is_electronic=True),
        procedure_context=warm_up_context(),
        observations=warm_up_observations(),
        ruleset=warm_up_rules(),
    )
    arguments.update(changes)
    return _engine(warm_up_registration()).evaluate(**arguments)


# ---------------------------------------------------------------------------
# Section 11
# ---------------------------------------------------------------------------

VOLTAGE_PROFILE_DATA = {
    "AC_MAINS": dict(
        power_supply_type="AC",
        reference_voltage_v="230",
        nominal="230",
        minimum="200",
        maximum="250",
        voltages=["200", "230", "250"],
        permit_switch_off=False,
    ),
    "EXTERNAL_SUPPLY": dict(
        power_supply_type="EXTERNAL",
        reference_voltage_v="12",
        nominal="12",
        minimum="10",
        maximum="14",
        voltages=["10", "12", "14"],
        permit_switch_off=False,
    ),
    "BATTERY_NO_CHARGING": dict(
        power_supply_type="BATTERY",
        reference_voltage_v="12",
        nominal="12",
        minimum="9",
        maximum="12",
        voltages=["9", "12"],
        permit_switch_off=True,
    ),
    "VEHICLE_SUPPLY": dict(
        power_supply_type="VEHICLE",
        reference_voltage_v="12",
        nominal="12",
        minimum="10",
        maximum="16",
        voltages=["10", "12", "16"],
        permit_switch_off=True,
    ),
}


def voltage_policy(*, profile="AC_MAINS", **changes):
    data = VOLTAGE_PROFILE_DATA[profile]
    loads = ["100", "10000"]
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=len(data["voltages"]) * len(loads),
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        power_supply_profile=profile,
        instrument_power_supply_type=data["power_supply_type"],
        reference_voltage_v=data["reference_voltage_v"],
        expected_nominal_voltage_v=data["nominal"],
        expected_min_voltage_v=data["minimum"],
        expected_max_voltage_v=data["maximum"],
        required_voltages_v=data["voltages"],
        required_loads_g=loads,
        permit_switch_off=data["permit_switch_off"],
        require_functions_operational_when_indicating=True,
    )
    policy.update(changes)
    return policy


def voltage_rules(*, profile="AC_MAINS", unverified=None, **changes):
    return _ruleset(
        code=VOLTAGE_VARIATION,
        section=11,
        variant=profile,
        policy_key=VOLTAGE_POLICY,
        policy_kind="voltage_variation_procedure_v1",
        policy=voltage_policy(profile=profile, **changes),
        extras=(
            VOLTAGE_CLASSIFICATION,
            VOLTAGE_CALIBRATION,
        ),
        mpe_key=VOLTAGE_MPE,
        unverified=unverified,
    )


def voltage_context(*, profile="AC_MAINS", **changes):
    data = VOLTAGE_PROFILE_DATA[profile]
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        procedure_variant=profile,
        power_supply_profile=profile,
        reference_voltage_v=data["reference_voltage_v"],
        protection_behavior_checked=True,
        **_context_evidence(),
    )
    payload.update(changes)
    return VoltageVariationContext.model_validate(payload)


def voltage_instrument(*, profile="AC_MAINS"):
    data = VOLTAGE_PROFILE_DATA[profile]
    return instrument(
        power_supply_type=data["power_supply_type"],
        nominal_voltage=data["nominal"],
        min_voltage=data["minimum"],
        max_voltage=data["maximum"],
        battery_charging_during_operation=(False if profile == "BATTERY_NO_CHARGING" else None),
        vehicle_powered=(True if profile == "VEHICLE_SUPPLY" else None),
    )


def voltage_observations(
    *,
    profile="AC_MAINS",
    error_g="10",
    switched_off=None,
    unexpected_voltage=None,
):
    data = VOLTAGE_PROFILE_DATA[profile]
    rows = []
    sequence = 1
    for load in (100, 10000):
        for voltage in map(int, data["voltages"]):
            applied = (
                int(unexpected_voltage)
                if unexpected_voltage is not None and sequence == 1
                else voltage
            )
            off = switched_off == (str(load), str(voltage))
            row = dict(
                sequence_no=sequence,
                applied_voltage_v=str(applied),
                load_g=str(load),
                operational_state=("SWITCHED_OFF" if off else "INDICATING"),
                functions_operational=not off,
                measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=sequence)
                ).isoformat(),
            )
            if not off:
                row.update(
                    indication_g=str(load + int(error_g)),
                    additional_load_g="5",
                    zero_error_g="0",
                )
            rows.append(row)
            sequence += 1
    return voltage_variation_registration().observations.parse(
        test_code=VOLTAGE_VARIATION,
        protocol="VOLTAGE_VARIATION_V1",
        version="v1",
        rows=rows,
    )


def evaluate_voltage(*, profile="AC_MAINS", **changes):
    arguments = dict(
        test_code=VOLTAGE_VARIATION,
        instrument_snapshot=voltage_instrument(profile=profile),
        procedure_context=voltage_context(profile=profile),
        observations=voltage_observations(profile=profile),
        ruleset=voltage_rules(profile=profile),
    )
    arguments.update(changes)
    return _engine(voltage_variation_registration()).evaluate(**arguments)


__all__ = [
    "VOLTAGE_PROFILE_DATA",
    "evaluate_temperature",
    "evaluate_tilting",
    "evaluate_voltage",
    "evaluate_warm_up",
    "temperature_context",
    "temperature_observations",
    "temperature_rules",
    "tilting_context",
    "tilting_observations",
    "tilting_rules",
    "voltage_context",
    "voltage_instrument",
    "voltage_observations",
    "voltage_rules",
    "warm_up_context",
    "warm_up_observations",
    "warm_up_rules",
]
