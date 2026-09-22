"""SYNTHETIC TEST FIXTURES for Phase 9 climatic/long-duration evaluators.

All values here exist only to exercise deterministic software mechanics.  They
are not verified OIML thresholds or production regulatory authority.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase9 import (
    DAMP_HEAT,
    DAMP_HEAT_CALIBRATION,
    DAMP_HEAT_CLASSIFICATION,
    DAMP_HEAT_MPE,
    DAMP_HEAT_POLICY,
    SPAN_STABILITY,
    SPAN_STABILITY_CALIBRATION,
    SPAN_STABILITY_CLASSIFICATION,
    SPAN_STABILITY_MPE,
    SPAN_STABILITY_POLICY,
    DampHeatContext,
    SpanStabilityContext,
    damp_heat_registration,
    span_stability_registration,
)
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument


def _rule(
    key,
    kind,
    policy=None,
    *,
    verified=True,
    dependencies=("BASE",),
):
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


def _app_policy(variant, *, damp_heat=False):
    cases = []
    if damp_heat:
        cases.append(
            dict(
                when=dict(
                    kind="choice",
                    feature="accuracy_class",
                    expected="I",
                ),
                decision="NOT_APPLICABLE",
                reason=("SYNTHETIC Class I damp-heat exclusion fixture"),
            )
        )
    cases.append(
        dict(
            when={"kind": "always"},
            decision="REQUIRED",
            reason="SYNTHETIC required fixture",
        )
    )
    return dict(
        schema_version="v1",
        scope="EACH_RANGE",
        scenarios=[
            dict(
                procedure_variant=variant,
                scenario="fixture",
            )
        ],
        cases=cases,
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
    mpe_key,
    extras,
    accuracy_class="III",
    unverified=None,
    damp_heat=False,
):
    app_key = f"{code}_APP"
    rules = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule(
            app_key,
            "applicability_policy_v1",
            _app_policy(
                variant,
                damp_heat=damp_heat,
            ),
            verified=unverified != app_key,
        ),
        _rule(
            policy_key,
            policy_kind,
            policy,
            verified=unverified != policy_key,
        ),
        _rule(
            mpe_key,
            "mpe_profile_v1",
            _mpe_policy(accuracy_class=accuracy_class),
            verified=unverified != mpe_key,
        ),
    ]
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
        mpe_key,
        *extras,
    ]
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-PHASE9-v1",
                version=(f"SYNTHETIC_TEST_PHASE9_{code}_{variant}"),
                standard_parts=[SOURCE],
                supported_test_codes=[code],
                source_reference=("SYNTHETIC TEST FIXTURE ONLY"),
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
                relative_humidity_percent="50",
                pressure_hpa="1000",
            )
        ],
        equipment=[
            dict(
                reference="SYNTHETIC_PHASE9_EQUIPMENT",
                category="SYNTHETIC",
            )
        ],
        evidence_hashes=["9" * 64],
    )


def _engine(registration):
    return R76Engine(
        EvaluatorRegistry(
            (
                replace(
                    registration,
                    synthetic_fixture=True,
                ),
            )
        )
    )


# ---------------------------------------------------------------------------
# Section 13 — damp heat
# ---------------------------------------------------------------------------


def damp_heat_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=6,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        stage_requirements=[
            dict(
                stage="INITIAL",
                temperature_min_c="19",
                temperature_max_c="21",
                temperature_lower_operator=">=",
                temperature_upper_operator="<=",
                humidity_min_percent="45",
                humidity_max_percent="55",
                humidity_lower_operator=">=",
                humidity_upper_operator="<=",
                minimum_stabilization_s="10",
                minimum_exposure_s="10",
            ),
            dict(
                stage="HIGH_HUMIDITY",
                temperature_min_c="39",
                temperature_max_c="41",
                temperature_lower_operator=">=",
                temperature_upper_operator="<=",
                humidity_min_percent="80",
                humidity_max_percent="90",
                humidity_lower_operator=">=",
                humidity_upper_operator="<=",
                minimum_stabilization_s="20",
                minimum_exposure_s="20",
            ),
            dict(
                stage="FINAL",
                temperature_min_c="19",
                temperature_max_c="21",
                temperature_lower_operator=">=",
                temperature_upper_operator="<=",
                humidity_min_percent="45",
                humidity_max_percent="55",
                humidity_lower_operator=">=",
                humidity_upper_operator="<=",
                minimum_stabilization_s="10",
                minimum_exposure_s="10",
            ),
        ],
        required_loads_g=["1000", "10000"],
        require_same_reference_weights=True,
        require_functions_operational=True,
    )
    policy.update(changes)
    return policy


def damp_heat_rules(
    *,
    accuracy_class="III",
    unverified=None,
    **changes,
):
    return _ruleset(
        code=DAMP_HEAT,
        section=13,
        variant="STEADY_STATE",
        policy_key=DAMP_HEAT_POLICY,
        policy_kind="damp_heat_procedure_v1",
        policy=damp_heat_policy(**changes),
        mpe_key=DAMP_HEAT_MPE,
        extras=(
            DAMP_HEAT_CLASSIFICATION,
            DAMP_HEAT_CALIBRATION,
        ),
        accuracy_class=accuracy_class,
        unverified=unverified,
        damp_heat=True,
    )


def damp_heat_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        stages=["INITIAL", "HIGH_HUMIDITY", "FINAL"],
        loads_g=["1000", "10000"],
        same_reference_weights_confirmed=True,
        **_context_evidence(),
    )
    payload.update(changes)
    return DampHeatContext.model_validate(payload)


def damp_heat_observations(
    *,
    error_g="10",
    functional_failure=False,
    bad_environment_stage=None,
    short_exposure_stage=None,
    omit_last=False,
    reverse_final_loads=False,
):
    stages = (
        ("INITIAL", 20, 50, 10, 10),
        ("HIGH_HUMIDITY", 40, 85, 20, 20),
        ("FINAL", 20, 50, 10, 10),
    )
    rows = []
    sequence = 1
    for stage, temperature, humidity, stable_s, exposure_s in stages:
        loads = [1000, 10000]
        if reverse_final_loads and stage == "FINAL":
            loads.reverse()
        for load in loads:
            current_temperature = temperature
            if bad_environment_stage == stage:
                current_temperature = temperature + 5
            current_exposure = exposure_s
            if short_exposure_stage == stage:
                current_exposure = max(0, exposure_s - 1)
            rows.append(
                dict(
                    sequence_no=sequence,
                    stage=stage,
                    load_g=str(load),
                    indication_g=str(load + int(error_g)),
                    additional_load_g="5",
                    zero_error_g="0",
                    temperature_c=str(current_temperature),
                    relative_humidity_percent=str(humidity),
                    stage_elapsed_s=str(stable_s),
                    exposure_elapsed_s=str(current_exposure),
                    stabilized=True,
                    functions_operational=not (
                        functional_failure and stage == "HIGH_HUMIDITY" and load == 10000
                    ),
                    measured_at=(
                        datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=sequence)
                    ).isoformat(),
                )
            )
            sequence += 1
    if omit_last:
        rows = rows[:-1]
    return damp_heat_registration().observations.parse(
        test_code=DAMP_HEAT,
        protocol="DAMP_HEAT_V1",
        version="v1",
        rows=rows,
    )


def evaluate_damp_heat(
    *,
    accuracy_class="III",
    **changes,
):
    arguments = dict(
        test_code=DAMP_HEAT,
        instrument_snapshot=instrument(
            accuracy_class=accuracy_class,
        ),
        procedure_context=damp_heat_context(),
        observations=damp_heat_observations(),
        ruleset=damp_heat_rules(
            accuracy_class=accuracy_class,
        ),
    )
    arguments.update(changes)
    return _engine(damp_heat_registration()).evaluate(**arguments)


# ---------------------------------------------------------------------------
# Section 14 — span stability
# ---------------------------------------------------------------------------


def span_policy(*, trend=False, correction_mode="NONE", **changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=4,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        test_load_g="10000",
        minimum_duration_s="300",
        duration_operator=">=",
        minimum_interval_s="90",
        minimum_interval_operator=">=",
        maximum_interval_s="110",
        maximum_interval_operator="<=",
        require_same_reference_weights=True,
        required_power_disconnections=2,
        minimum_power_disconnection_s="50",
        correction_mode=correction_mode,
        variation_formula="MAX_E_AND_MPE_MULTIPLIERS",
        e_multiplier="1",
        mpe_multiplier="1",
        variation_operator="<=",
        variation_semantics="ABSOLUTE",
        trend_extension_required=trend,
        trend_window_count=3 if trend else None,
        trend_limit_g="5" if trend else None,
        trend_operator=">" if trend else None,
        minimum_extension_measurements=2 if trend else 0,
    )
    policy.update(changes)
    return policy


def span_rules(
    *,
    trend=False,
    correction_mode="NONE",
    unverified=None,
    **changes,
):
    return _ruleset(
        code=SPAN_STABILITY,
        section=14,
        variant="LONG_DURATION",
        policy_key=SPAN_STABILITY_POLICY,
        policy_kind="span_stability_procedure_v1",
        policy=span_policy(
            trend=trend,
            correction_mode=correction_mode,
            **changes,
        ),
        mpe_key=SPAN_STABILITY_MPE,
        extras=(
            SPAN_STABILITY_CLASSIFICATION,
            SPAN_STABILITY_CALIBRATION,
        ),
        unverified=unverified,
    )


def span_context(
    *,
    extension_completed=False,
    **changes,
):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        test_load_g="10000",
        planned_duration_s="300",
        same_reference_weights_confirmed=True,
        extension_completed=extension_completed,
        **_context_evidence(),
    )
    payload.update(changes)
    return SpanStabilityContext.model_validate(payload)


def span_observations(
    *,
    errors=(0, 3, 6, 10),
    elapsed=(0, 100, 200, 300),
    missing_power_event=False,
    short_power_event=False,
    corrections=None,
    extension_errors=(),
):
    if corrections is None:
        corrections = (0,) * len(errors)
    rows = []
    base = datetime(2000, 1, 1, tzinfo=UTC)
    for index, (error, seconds, correction) in enumerate(
        zip(errors, elapsed, corrections, strict=True),
        1,
    ):
        power_event = index in {2, 3}
        if missing_power_event and index == 3:
            power_event = False
        power_duration = None
        if power_event:
            power_duration = 49 if short_power_event and index == 2 else 50
        rows.append(
            dict(
                sequence_no=index,
                measurement_no=index,
                elapsed_s=str(seconds),
                location="SYNTHETIC LAB",
                temperature_c="20",
                relative_humidity_percent="50",
                barometric_pressure_hpa="1000",
                event_since_previous_measurement=("SYNTHETIC POWER EVENT" if power_event else None),
                power_disconnection_event=power_event,
                power_disconnection_duration_s=(
                    str(power_duration) if power_duration is not None else None
                ),
                temperature_test_event=False,
                damp_heat_event=False,
                extension_measurement=False,
                load_g="10000",
                zero_indication_g="0",
                zero_additional_load_g="5",
                loaded_indication_g=str(10000 + error),
                loaded_additional_load_g="5",
                influence_correction_g=str(correction),
                measured_at=(base + timedelta(seconds=seconds)).isoformat(),
            )
        )

    next_index = len(rows) + 1
    next_elapsed = elapsed[-1] if elapsed else 0
    for offset, error in enumerate(extension_errors, 1):
        seconds = next_elapsed + 100 * offset
        rows.append(
            dict(
                sequence_no=next_index,
                measurement_no=next_index,
                elapsed_s=str(seconds),
                location="SYNTHETIC LAB",
                temperature_c="20",
                relative_humidity_percent="50",
                barometric_pressure_hpa="1000",
                event_since_previous_measurement=("SYNTHETIC EXTENSION"),
                power_disconnection_event=False,
                power_disconnection_duration_s=None,
                temperature_test_event=False,
                damp_heat_event=False,
                extension_measurement=True,
                load_g="10000",
                zero_indication_g="0",
                zero_additional_load_g="5",
                loaded_indication_g=str(10000 + error),
                loaded_additional_load_g="5",
                influence_correction_g="0",
                measured_at=(base + timedelta(seconds=seconds)).isoformat(),
            )
        )
        next_index += 1

    return span_stability_registration().observations.parse(
        test_code=SPAN_STABILITY,
        protocol="SPAN_STABILITY_V1",
        version="v1",
        rows=rows,
    )


def evaluate_span(**changes):
    arguments = dict(
        test_code=SPAN_STABILITY,
        instrument_snapshot=instrument(),
        procedure_context=span_context(),
        observations=span_observations(),
        ruleset=span_rules(),
    )
    arguments.update(changes)
    return _engine(span_stability_registration()).evaluate(**arguments)


__all__ = [
    "damp_heat_context",
    "damp_heat_observations",
    "damp_heat_rules",
    "evaluate_damp_heat",
    "evaluate_span",
    "span_context",
    "span_observations",
    "span_rules",
]
