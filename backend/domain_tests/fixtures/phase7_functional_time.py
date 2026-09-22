"""SYNTHETIC TEST FIXTURES for Phase 7 functional/time evaluators only.

These values exist only to exercise deterministic software mechanics. They are
not OIML thresholds, source verification, or production regulatory authority.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase7 import (
    CREEP,
    CREEP_CALIBRATION,
    CREEP_POLICY,
    DISCRIMINATION,
    DISCRIMINATION_CALIBRATION,
    DISCRIMINATION_CLASSIFICATION,
    DISCRIMINATION_POLICY,
    SENSITIVITY,
    SENSITIVITY_CALIBRATION,
    SENSITIVITY_CLASSIFICATION,
    SENSITIVITY_POLICY,
    STABILITY_EQUILIBRIUM,
    STABILITY_POLICY,
    ZERO_RETURN,
    ZERO_RETURN_CALIBRATION,
    ZERO_RETURN_POLICY,
    CreepContext,
    DiscriminationContext,
    SensitivityContext,
    StabilityContext,
    ZeroReturnContext,
    creep_registration,
    discrimination_registration,
    sensitivity_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.ruleset import RuleSet
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument


def _app_policy(variant, *, sensitivity=False):
    cases = (
        [
            dict(
                when={
                    "kind": "boolean",
                    "feature": "is_self_indicating",
                    "expected": False,
                },
                decision="REQUIRED",
                reason="SYNTHETIC non-self-indicating sensitivity case",
            ),
            dict(
                when={"kind": "always"},
                decision="NOT_APPLICABLE",
                reason="SYNTHETIC self-indicating exclusion",
            ),
        ]
        if sensitivity
        else [
            dict(
                when={"kind": "always"},
                decision="REQUIRED",
                reason="SYNTHETIC required fixture",
            )
        ]
    )
    return dict(
        schema_version="v1",
        scope="EACH_RANGE",
        scenarios=[dict(procedure_variant=variant, scenario="fixture")],
        cases=cases,
    )


def _rule(key, kind, policy=None, *, verified=True, dependencies=("BASE",)):
    return dict(
        key=key,
        kind=kind,
        description="SYNTHETIC TEST FIXTURE ONLY",
        source=SOURCE,
        verification=VERIFICATION if verified else {},
        dependencies=list(dependencies),
        parameters=([] if policy is None else [dict(name="POLICY_JSON", value=json.dumps(policy))]),
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
    sensitivity=False,
    unverified=None,
):
    app_key = f"{code}_APP"
    rules = [
        _rule("BASE", "dependency_v1", dependencies=()),
        _rule(
            app_key,
            "applicability_policy_v1",
            _app_policy(variant, sensitivity=sensitivity),
            verified=unverified != app_key,
        ),
        _rule(
            policy_key,
            policy_kind,
            policy,
            verified=unverified != policy_key,
        ),
    ]
    rules.extend(_rule(key, "dependency_v1", verified=unverified != key) for key in extras)
    dependencies = [app_key, policy_key, *extras]
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-PHASE7-v1",
                version=f"SYNTHETIC_TEST_PHASE7_{code}_{variant}",
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
        stabilized=True,
        environment=[
            dict(
                measured_at="2000-01-01T00:00:00Z",
                temperature_c="20",
            )
        ],
        equipment=[
            dict(
                reference="SYNTHETIC_WEIGHT",
                category="SYNTHETIC",
            )
        ],
        evidence_hashes=["e" * 64],
    )


def _engine(registration):
    return R76Engine(EvaluatorRegistry((replace(registration, synthetic_fixture=True),)))


def discrimination_policy(*, mode="DIGITAL", **changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=1,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        indication_mode=mode,
        test_load_g="5000",
        extra_load_g="10",
        minimum_indication_change_g="10" if mode == "DIGITAL" else None,
        minimum_displacement_mm="2" if mode == "ANALOG" else None,
        operator=">=",
        semantics="SIGNED",
    )
    policy.update(changes)
    return policy


def discrimination_rules(*, mode="DIGITAL", unverified=None, **changes):
    return _ruleset(
        code=DISCRIMINATION,
        section=4,
        variant=mode,
        policy_key=DISCRIMINATION_POLICY,
        policy_kind="discrimination_procedure_v1",
        policy=discrimination_policy(mode=mode, **changes),
        extras=(
            DISCRIMINATION_CLASSIFICATION,
            DISCRIMINATION_CALIBRATION,
        ),
        unverified=unverified,
    )


def discrimination_context(*, mode="DIGITAL", **changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        procedure_variant=mode,
        indication_mode=mode,
        **_context_evidence(),
    )
    payload.update(changes)
    return DiscriminationContext.model_validate(payload)


def discrimination_observations(
    *,
    mode="DIGITAL",
    indication_change="10",
    displacement_mm="2",
):
    registration = discrimination_registration()
    row = dict(
        sequence_no=1,
        load_g="5000",
        extra_load_g="10",
        indication_before_g="5000",
        indication_after_g=str(5000 + int(indication_change)),
        displacement_mm=displacement_mm if mode == "ANALOG" else None,
        measured_at="2000-01-01T00:00:01Z",
    )
    return registration.observations.parse(
        test_code=DISCRIMINATION,
        protocol="DISCRIMINATION_V1",
        version="v1",
        rows=[row],
    )


def evaluate_discrimination(*, mode="DIGITAL", **changes):
    arguments = dict(
        test_code=DISCRIMINATION,
        instrument_snapshot=instrument(indication_type=mode),
        procedure_context=discrimination_context(mode=mode),
        observations=discrimination_observations(mode=mode),
        ruleset=discrimination_rules(mode=mode),
    )
    arguments.update(changes)
    return _engine(discrimination_registration()).evaluate(**arguments)


def sensitivity_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=1,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        test_load_g="5000",
        extra_load_g="10",
        minimum_displacement_mm="2",
        operator=">=",
        semantics="SIGNED",
    )
    policy.update(changes)
    return policy


def sensitivity_rules(*, unverified=None, **changes):
    return _ruleset(
        code=SENSITIVITY,
        section=4,
        variant="NON_SELF_INDICATING",
        policy_key=SENSITIVITY_POLICY,
        policy_kind="sensitivity_procedure_v1",
        policy=sensitivity_policy(**changes),
        extras=(SENSITIVITY_CLASSIFICATION, SENSITIVITY_CALIBRATION),
        sensitivity=True,
        unverified=unverified,
    )


def sensitivity_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        **_context_evidence(),
    )
    payload.update(changes)
    return SensitivityContext.model_validate(payload)


def sensitivity_observations(*, displacement_mm="2"):
    registration = sensitivity_registration()
    return registration.observations.parse(
        test_code=SENSITIVITY,
        protocol="SENSITIVITY_V1",
        version="v1",
        rows=[
            dict(
                sequence_no=1,
                load_g="5000",
                extra_load_g="10",
                permanent_displacement_mm=displacement_mm,
                measured_at="2000-01-01T00:00:01Z",
            )
        ],
    )


def evaluate_sensitivity(**changes):
    arguments = dict(
        test_code=SENSITIVITY,
        instrument_snapshot=instrument(is_self_indicating=False),
        procedure_context=sensitivity_context(),
        observations=sensitivity_observations(),
        ruleset=sensitivity_rules(),
    )
    arguments.update(changes)
    return _engine(sensitivity_registration()).evaluate(**arguments)


def zero_return_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=1,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        test_load_g="10000",
        minimum_hold_seconds="60",
        limit_g="5",
        operator="<=",
        semantics="ABSOLUTE",
    )
    policy.update(changes)
    return policy


def zero_return_rules(*, unverified=None, **changes):
    return _ruleset(
        code=ZERO_RETURN,
        section=6,
        variant="ZERO_RETURN",
        policy_key=ZERO_RETURN_POLICY,
        policy_kind="zero_return_procedure_v1",
        policy=zero_return_policy(**changes),
        extras=(ZERO_RETURN_CALIBRATION,),
        unverified=unverified,
    )


def zero_return_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        test_load_g="10000",
        hold_seconds="60",
        **_context_evidence(),
    )
    payload.update(changes)
    return ZeroReturnContext.model_validate(payload)


def zero_return_observations(*, zero_after_g="5"):
    registration = zero_return_registration()
    return registration.observations.parse(
        test_code=ZERO_RETURN,
        protocol="ZERO_RETURN_V1",
        version="v1",
        rows=[
            dict(
                sequence_no=1,
                zero_before_g="0",
                zero_after_g=zero_after_g,
                measured_at="2000-01-01T00:01:00Z",
            )
        ],
    )


def evaluate_zero_return(**changes):
    arguments = dict(
        test_code=ZERO_RETURN,
        instrument_snapshot=instrument(),
        procedure_context=zero_return_context(),
        observations=zero_return_observations(),
        ruleset=zero_return_rules(),
    )
    arguments.update(changes)
    return _engine(zero_return_registration()).evaluate(**arguments)


def creep_policy(*, mode="SHORT", **changes):
    if mode == "SHORT":
        checkpoints = ["0", "900", "1800"]
        duration = "1800"
    else:
        checkpoints = ["0", "1800", "3600"]
        duration = "3600"
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=3,
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        duration_kind=mode,
        test_load_g="10000",
        minimum_duration_s=duration,
        required_checkpoints_s=checkpoints,
        limit_g="5",
        operator="<=",
        semantics="ABSOLUTE",
    )
    policy.update(changes)
    return policy


def creep_rules(*, mode="SHORT", unverified=None, **changes):
    return _ruleset(
        code=CREEP,
        section=6,
        variant=mode,
        policy_key=CREEP_POLICY,
        policy_kind="creep_procedure_v1",
        policy=creep_policy(mode=mode, **changes),
        extras=(CREEP_CALIBRATION,),
        unverified=unverified,
    )


def creep_context(*, mode="SHORT", **changes):
    duration = "1800" if mode == "SHORT" else "3600"
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        procedure_variant=mode,
        test_load_g="10000",
        planned_duration_s=duration,
        **_context_evidence(),
    )
    payload.update(changes)
    return CreepContext.model_validate(payload)


def creep_observations(*, mode="SHORT", final_change="5", omit_final=False):
    checkpoints = (0, 900, 1800) if mode == "SHORT" else (0, 1800, 3600)
    changes = ("0", "3", final_change)
    registration = creep_registration()
    rows = []
    for index, (elapsed, change) in enumerate(
        zip(checkpoints, changes, strict=True),
        1,
    ):
        if omit_final and index == len(checkpoints):
            continue
        rows.append(
            dict(
                sequence_no=index,
                elapsed_s=str(elapsed),
                indication_g=str(10000 + int(change)),
                measured_at=(
                    datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=elapsed)
                ).isoformat(),
            )
        )
    return registration.observations.parse(
        test_code=CREEP,
        protocol="CREEP_V1",
        version="v1",
        rows=rows,
    )


def evaluate_creep(*, mode="SHORT", **changes):
    arguments = dict(
        test_code=CREEP,
        instrument_snapshot=instrument(),
        procedure_context=creep_context(mode=mode),
        observations=creep_observations(mode=mode),
        ruleset=creep_rules(mode=mode),
    )
    arguments.update(changes)
    return _engine(creep_registration()).evaluate(**arguments)


def stability_policy(**changes):
    policy = dict(
        schema_version="v1",
        evaluation_context="SYNTHETIC",
        minimum_count=8,
        require_stabilization=False,
        require_environment=True,
        require_equipment=True,
        require_certificate=False,
        require_evidence=True,
        require_monotonic_timestamps=True,
        required_functions=["PRINTING", "STORAGE", "ZERO", "TARE"],
        minimum_trials_per_function=2,
        inhibit_when_unstable=True,
        permit_when_stable=True,
        require_adjacent_value_check_for=["PRINTING", "STORAGE"],
    )
    policy.update(changes)
    return policy


def stability_rules(*, unverified=None, **changes):
    return _ruleset(
        code=STABILITY_EQUILIBRIUM,
        section=7,
        variant="FUNCTIONAL",
        policy_key=STABILITY_POLICY,
        policy_kind="stability_equilibrium_procedure_v1",
        policy=stability_policy(**changes),
        unverified=unverified,
    )


def stability_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        functions_under_test=["PRINTING", "STORAGE", "ZERO", "TARE"],
        **_context_evidence(),
    )
    payload.update(changes)
    return StabilityContext.model_validate(payload)


def stability_observations(*, failing_function=None, omit_function=None):
    registration = stability_registration()
    rows = []
    index = 1
    for function in ("PRINTING", "STORAGE", "ZERO", "TARE"):
        if function == omit_function:
            continue
        for stable in (False, True):
            performed = stable
            if function == failing_function and not stable:
                performed = True
            rows.append(
                dict(
                    sequence_no=index,
                    function=function,
                    trial_no=1 if not stable else 2,
                    equilibrium_stable=stable,
                    operation_performed=performed,
                    adjacent_values_consistent=(
                        True if function in {"PRINTING", "STORAGE"} else None
                    ),
                    measured_at=(
                        datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=index)
                    ).isoformat(),
                )
            )
            index += 1
    return registration.observations.parse(
        test_code=STABILITY_EQUILIBRIUM,
        protocol="STABILITY_EQUILIBRIUM_V1",
        version="v1",
        rows=rows,
    )


def evaluate_stability(**changes):
    arguments = dict(
        test_code=STABILITY_EQUILIBRIUM,
        instrument_snapshot=instrument(),
        procedure_context=stability_context(),
        observations=stability_observations(),
        ruleset=stability_rules(),
    )
    arguments.update(changes)
    return _engine(stability_registration()).evaluate(**arguments)


__all__ = [
    "creep_context",
    "creep_observations",
    "creep_rules",
    "discrimination_context",
    "discrimination_observations",
    "discrimination_rules",
    "evaluate_creep",
    "evaluate_discrimination",
    "evaluate_sensitivity",
    "evaluate_stability",
    "evaluate_zero_return",
    "sensitivity_context",
    "sensitivity_observations",
    "sensitivity_rules",
    "stability_context",
    "stability_observations",
    "stability_rules",
    "zero_return_context",
    "zero_return_observations",
    "zero_return_rules",
]
