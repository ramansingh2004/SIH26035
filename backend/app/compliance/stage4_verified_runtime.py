"""Phase 25 Fix 11 — executable native-v2 runtime for Sections 11, 13, 14 and 15.

Fix 11 closes the engineering mismatch discovered during executable-rule review:
the source-native v2 contracts existed, but the production registry deliberately
restricted these four procedure rules to legacy v1 policies.

This module does not supply regulatory values. It provides:
- verified-rule schema shapes that can express relative/source-native semantics;
- deterministic v2 runtime validation and mechanics;
- v1-preserving wrapper evaluators; and
- replacement registrations with new implementation identities.

Regulatory values still come only from a verified pinned RuleSet.
Candidate-v1 remains non-authoritative and activation remains separately gated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import (
    AcceptanceLimit,
    ComplianceOutcome,
    EvaluationOutput,
    FailedCondition,
    Frozen,
    Number,
    PositiveInt,
    ProcedureValidationIssue,
    Text,
)
from app.compliance.evaluators import RulePolicyRegistration
from app.compliance.numbers import Operator, Semantics, exact
from app.compliance.phase8 import (
    VOLTAGE_MPE,
    VOLTAGE_POLICY,
    VoltageVariationEvaluator,
)
from app.compliance.phase8 import (
    voltage_variation_registration as _legacy_voltage_registration,
)
from app.compliance.phase9 import (
    DAMP_HEAT_MPE,
    DAMP_HEAT_POLICY,
    SPAN_STABILITY_MPE,
    SPAN_STABILITY_POLICY,
    DampHeatEvaluator,
    SpanStabilityEvaluator,
)
from app.compliance.phase9 import (
    damp_heat_registration as _legacy_damp_heat_registration,
)
from app.compliance.phase9 import (
    span_stability_registration as _legacy_span_stability_registration,
)
from app.compliance.phase11 import (
    ENDURANCE_MPE,
    ENDURANCE_POLICY,
    EnduranceEvaluator,
)
from app.compliance.phase11 import (
    endurance_registration as _legacy_endurance_registration,
)
from app.compliance.registries import ContextRegistration, ProcedureContextRegistry
from app.compliance.regulatory import (
    DependencyResolution,
    RegulatoryBlocked,
    calculate_mpe_compatible,
    dependencies,
    rule_policy,
)
from app.compliance.stage4_native_mechanics import (
    Stage4Limit,
    Stage4LoadLimit,
    damp_heat_mechanics,
    endurance_mechanics,
    span_stability_mechanics,
    voltage_variation_mechanics,
)
from app.compliance.stage4_native_schemas import (
    EnduranceContextV2,
    SpanStabilityContextV2,
    VoltageVariationContextV2,
)


class Stage4EvidencePolicyV2(Frozen):
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


class VerifiedVoltageTargetV2(Frozen):
    target_id: Text
    source: Literal[
        "ABSOLUTE_V",
        "NOMINAL_MULTIPLIER",
        "DECLARED_MIN_OR_NOMINAL_MULTIPLIER",
        "DECLARED_MAX_OR_NOMINAL_MULTIPLIER",
        "MINIMUM_OPERATING_MULTIPLIER",
    ]
    value: Number = Field(gt=0)


class VerifiedVoltageLoadRequirementV2(Frozen):
    load_id: Text
    source: Literal["E_MULTIPLE", "MAX_FRACTION_INTERVAL"]
    value: Number | None = Field(None, gt=0)
    minimum_fraction_of_max: Number | None = Field(None, ge=0, le=1)
    maximum_fraction_of_max: Number | None = Field(None, ge=0, le=1)
    required_distinct_loads: PositiveInt

    @model_validator(mode="after")
    def shape(self):
        if self.source == "E_MULTIPLE":
            if self.value is None:
                raise ValueError("E_MULTIPLE requires value")
            if (
                self.minimum_fraction_of_max is not None
                or self.maximum_fraction_of_max is not None
            ):
                raise ValueError("E_MULTIPLE cannot carry Max-fraction bounds")
        else:
            if self.value is not None:
                raise ValueError("MAX_FRACTION_INTERVAL cannot carry value")
            if (
                self.minimum_fraction_of_max is None
                or self.maximum_fraction_of_max is None
            ):
                raise ValueError("MAX_FRACTION_INTERVAL requires both bounds")
            if self.minimum_fraction_of_max > self.maximum_fraction_of_max:
                raise ValueError("Max-fraction bounds are reversed")
        return self


class VerifiedVoltageVariationProfileV2(Frozen):
    power_supply_profile: Literal[
        "AC_MAINS",
        "EXTERNAL_SUPPLY",
        "BATTERY_NO_CHARGING",
        "VEHICLE_SUPPLY",
    ]
    nominal_voltage_v: Number | None = Field(None, gt=0)
    required_voltage_targets: tuple[VerifiedVoltageTargetV2, ...] = Field(
        min_length=1
    )
    required_loads: tuple[VerifiedVoltageLoadRequirementV2, ...] = Field(
        min_length=1
    )
    allow_switch_off: StrictBool
    require_functions_operational_when_indicating: StrictBool
    successive_phase_application_required: StrictBool
    indication_limit_basis: Literal["MPE"]
    indication_limit_multiplier: Number = Field(gt=0)
    indication_operator: Operator
    indication_semantics: Semantics

    @model_validator(mode="after")
    def unique_values(self):
        target_ids = [item.target_id for item in self.required_voltage_targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("Duplicate voltage target id")
        load_ids = [item.load_id for item in self.required_loads]
        if len(load_ids) != len(set(load_ids)):
            raise ValueError("Duplicate voltage-load requirement id")
        return self


class VerifiedVoltageVariationPolicyV2(Stage4EvidencePolicyV2):
    schema_version: Literal["v2"]
    evaluation_context: Text
    profiles: tuple[VerifiedVoltageVariationProfileV2, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_profiles(self):
        keys = [
            (item.power_supply_profile, item.nominal_voltage_v)
            for item in self.profiles
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate voltage variation profile selector")
        return self

    def select(self, context: VoltageVariationContextV2):
        matches = []
        for profile in self.profiles:
            if profile.power_supply_profile != context.procedure_variant:
                continue
            if (
                profile.nominal_voltage_v is not None
                and context.nominal_voltage_v != profile.nominal_voltage_v
            ):
                continue
            matches.append(profile)
        if len(matches) != 1:
            raise ValueError(
                "Verified voltage policy profile coverage is missing or ambiguous"
            )
        return matches[0]


class VerifiedDampHeatStageV2(Frozen):
    stage: Literal["INITIAL", "HIGH_HUMIDITY", "FINAL"]
    temperature_source: Literal[
        "REFERENCE_TEMPERATURE",
        "DECLARED_HIGH_TEMPERATURE",
    ]
    relative_humidity_percent: Number = Field(ge=0, le=100)
    minimum_stabilization_seconds: Number = Field(ge=0)
    minimum_exposure_seconds: Number = Field(ge=0)


class VerifiedDampHeatPolicyV2(Stage4EvidencePolicyV2):
    schema_version: Literal["v2"]
    evaluation_context: Text
    excluded_accuracy_classes: tuple[
        Literal["I", "II", "III", "IIII"], ...
    ] = ()
    class_ii_minimum_e_g: Number | None = Field(None, ge=0)
    minimum_distinct_loads: PositiveInt
    reference_temperature_c: Number
    reference_temperature_fallback: Literal["DECLARED_MEAN_IF_OUTSIDE_RANGE"]
    stage_requirements: tuple[VerifiedDampHeatStageV2, ...] = Field(min_length=3)
    require_same_reference_weights: StrictBool
    require_functions_operational: StrictBool
    indication_limit_basis: Literal["MPE"]
    indication_limit_multiplier: Number = Field(gt=0)
    indication_operator: Operator
    indication_semantics: Semantics

    @model_validator(mode="after")
    def stage_shape(self):
        stages = tuple(item.stage for item in self.stage_requirements)
        if stages != ("INITIAL", "HIGH_HUMIDITY", "FINAL"):
            raise ValueError(
                "Damp-heat stages must be INITIAL/HIGH_HUMIDITY/FINAL"
            )
        return self


class VerifiedSpanStabilityPolicyV2(Stage4EvidencePolicyV2):
    schema_version: Literal["v2"]
    evaluation_context: Text
    excluded_accuracy_classes: tuple[
        Literal["I", "II", "III", "IIII"], ...
    ] = ()
    test_load_target: Literal["CLOSE_TO_MAX"]
    require_test_load_near_max_confirmation: StrictBool
    maximum_duration_seconds: Number = Field(gt=0)
    minimum_measurements: PositiveInt
    minimum_interval_seconds: Number = Field(gt=0)
    maximum_interval_seconds: Number = Field(gt=0)
    required_power_disconnections: PositiveInt
    minimum_power_disconnection_seconds: Number = Field(gt=0)
    normal_recovery_seconds: Number = Field(gt=0)
    post_environmental_test_recovery_seconds: Number = Field(gt=0)
    first_measurement_repeat_count: PositiveInt
    require_same_reference_weights: StrictBool
    require_zero_tracking_disabled: StrictBool
    require_builtin_span_adjustment_active_if_present: StrictBool
    require_temperature_test_completed: StrictBool
    require_damp_heat_completed_if_applicable: StrictBool
    prohibit_endurance_test_during_span: StrictBool
    variation_limit_basis: Literal["MAX_OF_E_AND_MPE"]
    variation_e_multiplier: Number = Field(ge=0)
    variation_mpe_multiplier: Number = Field(ge=0)
    variation_operator: Operator
    variation_semantics: Semantics
    trend_extension_required_if_detected: StrictBool

    @model_validator(mode="after")
    def intervals(self):
        if self.minimum_interval_seconds > self.maximum_interval_seconds:
            raise ValueError("Span-stability interval bounds reversed")
        return self


class VerifiedEndurancePolicyV2(Stage4EvidencePolicyV2):
    schema_version: Literal["v2"]
    evaluation_context: Text
    applicable_accuracy_classes: tuple[
        Literal["I", "II", "III", "IIII"], ...
    ] = Field(min_length=1)
    maximum_capacity_limit_g: Number = Field(gt=0)
    required_cycles: PositiveInt
    completed_cycles_operator: Literal["==", ">="]
    cycling_load_fraction_of_max: Number = Field(gt=0, le=1)
    require_cycling_load_approximation_confirmation: StrictBool
    require_after_other_tests: StrictBool
    require_loaded_equilibrium_each_cycle: StrictBool
    require_unloaded_equilibrium_each_cycle: StrictBool
    require_normal_loading_force: StrictBool
    require_same_reference_weights: StrictBool
    require_abnormal_events_resolved: StrictBool
    minimum_performance_load_points: PositiveInt
    require_max_performance_point: StrictBool
    require_pre_post_weighing_procedure_confirmation: StrictBool
    require_stabilized_performance_observations: StrictBool
    durability_formula: Literal["ABS_CORRECTED_ERROR_CHANGE"]
    durability_limit_basis: Literal["MPE"]
    durability_mpe_multiplier: Number = Field(gt=0)
    durability_operator: Operator
    durability_semantics: Semantics

    @model_validator(mode="after")
    def canonical_classes(self):
        object.__setattr__(
            self,
            "applicable_accuracy_classes",
            tuple(sorted(set(self.applicable_accuracy_classes))),
        )
        return self


class VerifiedSpanStabilityContextV2(SpanStabilityContextV2):
    test_load_near_max_confirmed: StrictBool
    builtin_span_adjustment_present: StrictBool
    damp_heat_applicable: StrictBool
    endurance_test_performed_during_span: StrictBool
    trend_detected: StrictBool


class VerifiedEnduranceContextV2(EnduranceContextV2):
    cycling_load_approximation_confirmed: StrictBool
    pre_post_weighing_procedure_confirmed: StrictBool


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code=(
            "MISSING_REQUIRED_OBSERVATIONS"
            if missing
            else "EVALUATION_NOT_POSSIBLE"
        ),
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


def _policy_blocked(ruleset, key: str):
    return RegulatoryBlocked(
        DependencyResolution(
            unresolved_rule_ids=(key,),
            rule_references=dependencies(ruleset, (key,)).rule_references,
        )
    )


def _refs(ruleset, evaluator):
    return dependencies(
        ruleset,
        evaluator.required_rules(),
    ).rule_references


def _evidence_issues(policy, context, rows, refs):
    issues = []

    def check(ok, category, reason, *, missing=False, sequence=None):
        if not ok:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                    sequence=sequence,
                )
            )

    check(
        context.evaluation_context == policy.evaluation_context,
        "STAGE",
        "Evaluation context incompatible with verified v2 procedure",
    )
    check(
        not policy.require_environment or bool(context.environment),
        "ENVIRONMENT",
        "Required environment evidence missing",
        missing=True,
    )
    check(
        not policy.require_equipment or bool(context.equipment),
        "EQUIPMENT",
        "Required equipment evidence missing",
        missing=True,
    )
    if policy.require_certificate:
        check(
            bool(context.equipment)
            and all(item.calibration_certificate_no for item in context.equipment),
            "EQUIPMENT",
            "Required calibration-certificate identity missing",
            missing=True,
        )
    check(
        not policy.require_evidence or bool(context.evidence_hashes),
        "EVIDENCE",
        "Required supporting evidence missing",
        missing=True,
    )
    if policy.require_monotonic_timestamps:
        previous = None
        for row in rows:
            if previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Observation timestamps are not monotonic",
                    sequence=row.sequence_no,
                )
            previous = row.measured_at
    return issues


def _native_output(result, refs, family):
    calculations = tuple(
        item.model_copy(update={"rule_references": refs})
        for item in result.calculations
    )
    limits = []
    failures = []
    for assertion in result.assertions:
        limit = AcceptanceLimit(
            name=assertion.limit.name,
            value=assertion.limit.value,
            unit=assertion.limit.unit,
            operator=assertion.limit.operator,
            semantics=assertion.limit.semantics,
            rule_references=refs,
        )
        limits.append(limit)
        if not assertion.passed:
            failures.append(
                FailedCondition(
                    code=f"{family}_LIMIT_EXCEEDED",
                    reason=(
                        f"{family} verified native-v2 assertion failed: "
                        f"{assertion.name}"
                    ),
                    actual=assertion.actual,
                    limit=limit,
                )
            )
    return EvaluationOutput(
        compliance_outcome=(
            ComplianceOutcome.NONCOMPLIANT
            if failures
            else ComplianceOutcome.COMPLIANT
        ),
        calculations=calculations,
        acceptance_limits=tuple(limits),
        failed_conditions=tuple(failures),
        reasons=(
            f"{family} evaluated using the pinned verified native-v2 policy",
        ),
    )


def _stage4_limit_from_mpe(
    *,
    mpe,
    multiplier,
    operator,
    semantics,
    name,
):
    return Stage4Limit(
        name=name,
        value=exact("multiply", mpe.value, multiplier),
        operator=operator,
        semantics=semantics,
        unit="g",
    )


def _replace_policy_schema(registration, kind, schema):
    policies = tuple(
        RulePolicyRegistration(kind, schema)
        if item.kind == kind
        else item
        for item in registration.policy_schemas
    )
    if not any(item.kind == kind for item in policies):
        raise ValueError(f"Missing policy registration: {kind}")
    return replace(registration, policy_schemas=policies)


def _replace_v2_context(registration, schema):
    rows = []
    found = False
    for item in registration.contexts.registrations:
        if item.procedure_schema_version == "v2":
            rows.append(
                ContextRegistration(
                    item.test_code,
                    item.procedure_variant,
                    item.procedure_schema_version,
                    schema,
                )
            )
            found = True
        else:
            rows.append(item)
    if not found:
        raise ValueError("Expected a registered v2 procedure context")
    return replace(
        registration,
        contexts=ProcedureContextRegistry(tuple(rows)),
    )


def _resolve_voltage_target(target, context):
    if target.source == "ABSOLUTE_V":
        return target.value
    if target.source == "NOMINAL_MULTIPLIER":
        base = context.nominal_voltage_v
    elif target.source == "DECLARED_MIN_OR_NOMINAL_MULTIPLIER":
        base = (
            context.declared_min_voltage_v
            if context.declared_min_voltage_v is not None
            else context.nominal_voltage_v
        )
    elif target.source == "DECLARED_MAX_OR_NOMINAL_MULTIPLIER":
        base = (
            context.declared_max_voltage_v
            if context.declared_max_voltage_v is not None
            else context.nominal_voltage_v
        )
    elif target.source == "MINIMUM_OPERATING_MULTIPLIER":
        base = context.minimum_operating_voltage_v
    else:
        base = None
    if base is None:
        return None
    return exact("multiply", base, target.value)


def _voltage_load_matches(requirement, load_g, selected):
    if requirement.source == "E_MULTIPLE":
        expected = exact(
            "multiply",
            selected.verification_interval_e_g,
            requirement.value,
        )
        return load_g == expected
    lower = exact(
        "multiply",
        selected.max_capacity_g,
        requirement.minimum_fraction_of_max,
    )
    upper = exact(
        "multiply",
        selected.max_capacity_g,
        requirement.maximum_fraction_of_max,
    )
    return lower <= load_g <= upper


def _voltage_policy_and_profile(ruleset, context):
    policy = rule_policy(
        ruleset,
        VOLTAGE_POLICY,
        "voltage_variation_procedure_v2",
        VerifiedVoltageVariationPolicyV2,
    )
    try:
        return policy, policy.select(context)
    except ValueError as exc:
        raise _policy_blocked(ruleset, VOLTAGE_POLICY) from exc


def _validate_voltage_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy, profile = _voltage_policy_and_profile(ruleset, procedure_context)
    refs = _refs(ruleset, evaluator)
    rows = observations.rows
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    issues = list(_evidence_issues(policy, procedure_context, rows, refs))

    def check(ok, category, reason, *, missing=False, sequence=None):
        if not ok:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                    sequence=sequence,
                )
            )

    for attr, expected in (
        ("nominal_voltage", procedure_context.nominal_voltage_v),
        ("min_voltage", procedure_context.declared_min_voltage_v),
        ("max_voltage", procedure_context.declared_max_voltage_v),
    ):
        actual = getattr(instrument_snapshot, attr)
        if actual is not None and expected is not None:
            check(
                actual == expected,
                "POWER",
                f"Instrument {attr} differs from v2 procedure context",
            )

    resolved_targets = {}
    for target in profile.required_voltage_targets:
        resolved = _resolve_voltage_target(target, procedure_context)
        check(
            resolved is not None,
            "POWER",
            (
                f"Voltage target {target.target_id} cannot be resolved "
                "from declared supply facts"
            ),
        )
        if resolved is not None:
            resolved_targets[target.target_id] = resolved

    observed_loads = tuple(sorted({row.load_g for row in rows}))
    matched_loads = {}
    for requirement in profile.required_loads:
        values = tuple(
            value
            for value in observed_loads
            if _voltage_load_matches(requirement, value, selected)
        )
        matched_loads[requirement.load_id] = values
        check(
            len(values) == requirement.required_distinct_loads,
            "LOAD_COVERAGE",
            (
                f"Voltage load requirement {requirement.load_id} expected "
                f"{requirement.required_distinct_loads} distinct matching load(s)"
            ),
            missing=len(values) < requirement.required_distinct_loads,
        )

    allowed_loads = {
        value
        for values in matched_loads.values()
        for value in values
    }
    for row in rows:
        check(
            row.target_id in resolved_targets,
            "POWER",
            "Unexpected voltage target id",
            sequence=row.sequence_no,
        )
        if row.target_id in resolved_targets:
            check(
                row.applied_voltage_v == resolved_targets[row.target_id],
                "POWER",
                "Applied voltage differs from resolved verified target",
                sequence=row.sequence_no,
            )
        check(
            row.load_g in allowed_loads,
            "LOAD_COVERAGE",
            "Unexpected voltage-test load",
            sequence=row.sequence_no,
        )
        if row.operational_state == "SWITCHED_OFF":
            check(
                profile.allow_switch_off,
                "FUNCTIONAL",
                "Switch-off is not permitted by verified voltage profile",
                sequence=row.sequence_no,
            )
        elif profile.require_functions_operational_when_indicating:
            check(
                row.functions_operational,
                "FUNCTIONAL",
                "Required functions are not operational while indicating",
                sequence=row.sequence_no,
            )

    phases = (
        tuple(range(1, procedure_context.phase_count + 1))
        if profile.successive_phase_application_required
        and procedure_context.phase_count > 1
        else (None,)
    )
    for target_id in resolved_targets:
        for values in matched_loads.values():
            for load_g in values:
                for phase in phases:
                    matches = []
                    for row in rows:
                        if row.target_id != target_id or row.load_g != load_g:
                            continue
                        if phase is None:
                            if row.phase_no not in (None, 1):
                                continue
                        elif row.phase_no != phase:
                            continue
                        matches.append(row)
                    check(
                        len(matches) == 1,
                        "COUNT",
                        (
                            "Each required voltage/load/phase combination "
                            "needs exactly one observation"
                        ),
                        missing=not matches,
                    )

    check(
        procedure_context.protection_behavior_checked,
        "FUNCTIONAL",
        "Voltage protection behavior was not checked",
    )
    return tuple(issues)


def _evaluate_voltage_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    _, profile = _voltage_policy_and_profile(ruleset, procedure_context)
    refs = _refs(ruleset, evaluator)
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    limits = []
    for load_g in sorted(
        {
            row.load_g
            for row in observations.rows
            if row.operational_state == "INDICATING"
        }
    ):
        mpe = calculate_mpe_compatible(
            load_g=load_g,
            selected_range=selected,
            accuracy_class=instrument_snapshot.accuracy_class,
            evaluation_context=procedure_context.evaluation_context,
            ruleset=ruleset,
            rule_id=VOLTAGE_MPE,
        )
        limits.append(
            Stage4LoadLimit(
                load_g=load_g,
                limit=_stage4_limit_from_mpe(
                    mpe=mpe,
                    multiplier=profile.indication_limit_multiplier,
                    operator=profile.indication_operator,
                    semantics=profile.indication_semantics,
                    name=f"voltage_mpe:{load_g}",
                ),
            )
        )
    result = voltage_variation_mechanics(
        observations.rows,
        verification_interval_e_g=selected.verification_interval_e_g,
        load_limits=tuple(limits),
    )
    return _native_output(result, refs, "VOLTAGE_VARIATION")


@dataclass(frozen=True)
class VoltageVariationFix11Evaluator:
    delegate: VoltageVariationEvaluator

    def required_rules(self, **kwargs):
        return self.delegate.required_rules(**kwargs)

    def applicability(self, **kwargs):
        return self.delegate.applicability(**kwargs)

    def validate_procedure(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.validate_procedure(**kwargs)
        return _validate_voltage_v2(self, **kwargs)

    def evaluate(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.evaluate(**kwargs)
        return _evaluate_voltage_v2(self, **kwargs)


def _damp_policy(ruleset):
    return rule_policy(
        ruleset,
        DAMP_HEAT_POLICY,
        "damp_heat_procedure_v2",
        VerifiedDampHeatPolicyV2,
    )


def _reference_temperature(policy, context):
    target = policy.reference_temperature_c
    if (
        context.declared_low_temperature_c
        <= target
        <= context.declared_high_temperature_c
    ):
        return target
    return exact(
        "multiply",
        exact(
            "add",
            context.declared_low_temperature_c,
            context.declared_high_temperature_c,
        ),
        "0.5",
    )


def _validate_damp_heat_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _damp_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    rows = observations.rows
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    issues = list(_evidence_issues(policy, procedure_context, rows, refs))

    def check(ok, category, reason, *, missing=False, sequence=None):
        if not ok:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                    sequence=sequence,
                )
            )

    check(
        procedure_context.declared_low_temperature_c
        <= procedure_context.declared_high_temperature_c,
        "ENVIRONMENT",
        "Declared damp-heat temperature bounds are reversed",
    )
    if instrument_snapshot.declared_temp_min_c is not None:
        check(
            instrument_snapshot.declared_temp_min_c
            == procedure_context.declared_low_temperature_c,
            "ENVIRONMENT",
            "Damp-heat low temperature differs from instrument declaration",
        )
    if instrument_snapshot.declared_temp_max_c is not None:
        check(
            instrument_snapshot.declared_temp_max_c
            == procedure_context.declared_high_temperature_c,
            "ENVIRONMENT",
            "Damp-heat high temperature differs from instrument declaration",
        )

    check(
        instrument_snapshot.accuracy_class not in policy.excluded_accuracy_classes,
        "STAGE",
        "Accuracy class is excluded by the verified damp-heat policy",
    )
    if (
        instrument_snapshot.accuracy_class == "II"
        and policy.class_ii_minimum_e_g is not None
    ):
        check(
            selected.verification_interval_e_g >= policy.class_ii_minimum_e_g,
            "STAGE",
            "Class II verification interval is below damp-heat policy scope",
        )

    check(
        len(set(procedure_context.loads_g)) >= policy.minimum_distinct_loads,
        "LOAD_COVERAGE",
        "Insufficient distinct damp-heat loads",
        missing=True,
    )
    for load_g in procedure_context.loads_g:
        check(
            load_g <= selected.max_capacity_g,
            "RANGE",
            "Damp-heat load exceeds selected range",
        )
    if policy.require_same_reference_weights:
        check(
            procedure_context.same_reference_weights_confirmed,
            "EQUIPMENT",
            "Verified damp-heat policy requires the same reference weights",
        )

    expected_reference = _reference_temperature(policy, procedure_context)
    check(
        procedure_context.reference_temperature_c == expected_reference,
        "ENVIRONMENT",
        "Reference temperature differs from verified source-native rule",
    )

    expected_pairs = tuple(
        (stage.stage, load_g)
        for stage in policy.stage_requirements
        for load_g in procedure_context.loads_g
    )
    actual_pairs = tuple((row.stage, row.load_g) for row in rows)
    check(
        actual_pairs == expected_pairs,
        "ORDER",
        "Damp-heat stage/load sequence is incomplete or out of order",
        missing=len(actual_pairs) < len(expected_pairs),
    )

    stage_map = {item.stage: item for item in policy.stage_requirements}
    for row in rows:
        requirement = stage_map.get(row.stage)
        if requirement is None:
            check(
                False,
                "STAGE",
                "Unexpected damp-heat stage",
                sequence=row.sequence_no,
            )
            continue
        expected_temp = (
            expected_reference
            if requirement.temperature_source == "REFERENCE_TEMPERATURE"
            else procedure_context.declared_high_temperature_c
        )
        check(
            row.temperature_c == expected_temp,
            "ENVIRONMENT",
            "Damp-heat temperature differs from verified stage target",
            sequence=row.sequence_no,
        )
        check(
            row.relative_humidity_percent
            == requirement.relative_humidity_percent,
            "ENVIRONMENT",
            "Damp-heat relative humidity differs from verified stage target",
            sequence=row.sequence_no,
        )
        check(
            row.stabilized,
            "STABILIZATION",
            "Damp-heat observation is not stabilized",
            sequence=row.sequence_no,
        )
        check(
            row.stabilization_elapsed_s
            >= requirement.minimum_stabilization_seconds,
            "STABILIZATION",
            "Damp-heat stabilization duration is insufficient",
            sequence=row.sequence_no,
        )
        check(
            row.exposure_elapsed_s >= requirement.minimum_exposure_seconds,
            "TIMING",
            "Damp-heat exposure duration is insufficient",
            sequence=row.sequence_no,
        )
        if policy.require_functions_operational:
            check(
                row.functions_operational,
                "FUNCTIONAL",
                "Instrument functions are not operational during damp-heat test",
                sequence=row.sequence_no,
            )
    return tuple(issues)


def _evaluate_damp_heat_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _damp_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    limits = []
    for load_g in procedure_context.loads_g:
        mpe = calculate_mpe_compatible(
            load_g=load_g,
            selected_range=selected,
            accuracy_class=instrument_snapshot.accuracy_class,
            evaluation_context=procedure_context.evaluation_context,
            ruleset=ruleset,
            rule_id=DAMP_HEAT_MPE,
        )
        limits.append(
            Stage4LoadLimit(
                load_g=load_g,
                limit=_stage4_limit_from_mpe(
                    mpe=mpe,
                    multiplier=policy.indication_limit_multiplier,
                    operator=policy.indication_operator,
                    semantics=policy.indication_semantics,
                    name=f"damp_heat_mpe:{load_g}",
                ),
            )
        )
    result = damp_heat_mechanics(
        observations.rows,
        verification_interval_e_g=selected.verification_interval_e_g,
        load_limits=tuple(limits),
    )
    return _native_output(result, refs, "DAMP_HEAT")


@dataclass(frozen=True)
class DampHeatFix11Evaluator:
    delegate: DampHeatEvaluator

    def required_rules(self, **kwargs):
        return self.delegate.required_rules(**kwargs)

    def applicability(self, **kwargs):
        return self.delegate.applicability(**kwargs)

    def validate_procedure(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.validate_procedure(**kwargs)
        return _validate_damp_heat_v2(self, **kwargs)

    def evaluate(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.evaluate(**kwargs)
        return _evaluate_damp_heat_v2(self, **kwargs)


def _span_policy(ruleset):
    return rule_policy(
        ruleset,
        SPAN_STABILITY_POLICY,
        "span_stability_procedure_v2",
        VerifiedSpanStabilityPolicyV2,
    )


def _validate_span_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _span_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    rows = observations.rows
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    issues = list(_evidence_issues(policy, procedure_context, rows, refs))

    def check(ok, category, reason, *, missing=False, sequence=None):
        if not ok:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                    sequence=sequence,
                )
            )

    check(
        instrument_snapshot.accuracy_class not in policy.excluded_accuracy_classes,
        "STAGE",
        "Accuracy class is excluded by the verified span-stability policy",
    )
    if policy.require_test_load_near_max_confirmation:
        check(
            procedure_context.test_load_near_max_confirmed,
            "LOAD_COVERAGE",
            "Near-Max span-stability load has not been confirmed",
        )
    check(
        procedure_context.test_load_g <= selected.max_capacity_g,
        "RANGE",
        "Span-stability test load exceeds selected range",
    )
    check(
        procedure_context.planned_duration_s <= policy.maximum_duration_seconds,
        "TIMING",
        "Planned span-stability duration exceeds verified maximum duration",
    )
    if policy.require_same_reference_weights:
        check(
            procedure_context.same_reference_weights_confirmed,
            "EQUIPMENT",
            "Span stability requires the same reference weights",
        )
    if policy.require_zero_tracking_disabled:
        check(
            procedure_context.zero_tracking_disabled,
            "FUNCTIONAL",
            "Span stability requires zero tracking to be disabled",
        )
    if (
        policy.require_builtin_span_adjustment_active_if_present
        and procedure_context.builtin_span_adjustment_present
    ):
        check(
            procedure_context.builtin_span_adjustment_active,
            "FUNCTIONAL",
            "Built-in span adjustment is present but not active",
        )
    if policy.require_temperature_test_completed:
        check(
            procedure_context.temperature_test_completed,
            "STAGE",
            "Temperature test must be completed within span-stability workflow",
        )
    if (
        policy.require_damp_heat_completed_if_applicable
        and procedure_context.damp_heat_applicable
    ):
        check(
            procedure_context.damp_heat_completed_if_applicable,
            "STAGE",
            "Applicable damp-heat test has not been completed",
        )
    if policy.prohibit_endurance_test_during_span:
        check(
            not procedure_context.endurance_test_performed_during_span,
            "STAGE",
            (
                "Endurance test must not be included in "
                "span-stability performance-test period"
            ),
        )
    if (
        policy.trend_extension_required_if_detected
        and procedure_context.trend_detected
    ):
        check(
            procedure_context.extension_completed,
            "TIMING",
            (
                "Detected span trend requires extension until "
                "the verified stopping condition"
            ),
        )

    grouped = {}
    for row in rows:
        grouped.setdefault(row.measurement_no, []).append(row)
        check(
            row.load_g == procedure_context.test_load_g,
            "LOAD_COVERAGE",
            "Span-stability observation load differs from verified test load",
            sequence=row.sequence_no,
        )
        if row.power_disconnection_event:
            check(
                row.power_disconnection_duration_s is not None
                and row.power_disconnection_duration_s
                >= policy.minimum_power_disconnection_seconds,
                "POWER",
                "Power disconnection duration is below verified minimum",
                sequence=row.sequence_no,
            )
        required_recovery = (
            policy.post_environmental_test_recovery_seconds
            if row.after_environmental_test
            else policy.normal_recovery_seconds
        )
        check(
            row.recovery_elapsed_s >= required_recovery,
            "TIMING",
            "Span-stability recovery time is insufficient",
            sequence=row.sequence_no,
        )

    numbers = sorted(grouped)
    check(
        len(numbers) >= policy.minimum_measurements,
        "COUNT",
        "Insufficient span-stability measurements",
        missing=True,
    )
    check(
        numbers == list(range(1, len(numbers) + 1)),
        "ORDER",
        "Span-stability measurement numbers must be contiguous",
    )
    if 1 in grouped:
        check(
            len(grouped[1]) == policy.first_measurement_repeat_count,
            "COUNT",
            (
                "First span-stability measurement repeat count "
                "differs from verified policy"
            ),
            missing=len(grouped[1]) < policy.first_measurement_repeat_count,
        )
    for number in numbers[1:]:
        check(
            len(grouped[number]) == 1,
            "COUNT",
            "Later span-stability measurements must have one normal reading",
        )

    first_rows = [grouped[number][0] for number in numbers]
    for left, right in zip(first_rows, first_rows[1:], strict=False):
        interval = exact("subtract", right.elapsed_s, left.elapsed_s)
        check(
            interval >= policy.minimum_interval_seconds,
            "TIMING",
            "Span-stability measurement interval is below verified minimum",
            sequence=right.sequence_no,
        )
        check(
            interval <= policy.maximum_interval_seconds,
            "TIMING",
            "Span-stability measurement interval exceeds verified maximum",
            sequence=right.sequence_no,
        )
    if first_rows:
        check(
            first_rows[-1].elapsed_s <= policy.maximum_duration_seconds,
            "TIMING",
            "Recorded span-stability duration exceeds verified maximum",
        )

    power_events = [row for row in rows if row.power_disconnection_event]
    check(
        len(power_events) >= policy.required_power_disconnections,
        "POWER",
        "Required span-stability power disconnections are missing",
        missing=True,
    )
    return tuple(issues)


def _evaluate_span_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _span_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    mpe = calculate_mpe_compatible(
        load_g=procedure_context.test_load_g,
        selected_range=selected,
        accuracy_class=instrument_snapshot.accuracy_class,
        evaluation_context=procedure_context.evaluation_context,
        ruleset=ruleset,
        rule_id=SPAN_STABILITY_MPE,
    )
    e_limit = exact(
        "multiply",
        selected.verification_interval_e_g,
        policy.variation_e_multiplier,
    )
    mpe_limit = exact(
        "multiply",
        mpe.value.copy_abs(),
        policy.variation_mpe_multiplier,
    )
    limit = Stage4Limit(
        name="span_stability_variation",
        value=max(e_limit, mpe_limit),
        operator=policy.variation_operator,
        semantics=policy.variation_semantics,
        unit="g",
    )
    result = span_stability_mechanics(
        observations.rows,
        verification_interval_e_g=selected.verification_interval_e_g,
        variation_limit=limit,
    )
    return _native_output(result, refs, "SPAN_STABILITY")


@dataclass(frozen=True)
class SpanStabilityFix11Evaluator:
    delegate: SpanStabilityEvaluator

    def required_rules(self, **kwargs):
        return self.delegate.required_rules(**kwargs)

    def applicability(self, **kwargs):
        return self.delegate.applicability(**kwargs)

    def validate_procedure(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.validate_procedure(**kwargs)
        return _validate_span_v2(self, **kwargs)

    def evaluate(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.evaluate(**kwargs)
        return _evaluate_span_v2(self, **kwargs)


def _endurance_policy(ruleset):
    return rule_policy(
        ruleset,
        ENDURANCE_POLICY,
        "endurance_procedure_v2",
        VerifiedEndurancePolicyV2,
    )


def _validate_endurance_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _endurance_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    rows = observations.rows
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    issues = list(_evidence_issues(policy, procedure_context, rows, refs))

    def check(ok, category, reason, *, missing=False, sequence=None):
        if not ok:
            issues.append(
                _issue(
                    refs,
                    category,
                    reason,
                    missing=missing,
                    sequence=sequence,
                )
            )

    check(
        instrument_snapshot.accuracy_class in policy.applicable_accuracy_classes,
        "STAGE",
        "Accuracy class is outside verified endurance scope",
    )
    check(
        selected.max_capacity_g <= policy.maximum_capacity_limit_g,
        "RANGE",
        "Selected range Max exceeds verified endurance scope",
    )
    check(
        procedure_context.planned_cycles == policy.required_cycles,
        "COUNT",
        "Planned endurance cycle count differs from verified procedure",
    )
    completed_ok = (
        procedure_context.completed_cycles == policy.required_cycles
        if policy.completed_cycles_operator == "=="
        else procedure_context.completed_cycles >= policy.required_cycles
    )
    check(
        completed_ok,
        "COUNT",
        "Required endurance cycles are incomplete",
        missing=True,
    )
    if policy.require_cycling_load_approximation_confirmation:
        check(
            procedure_context.cycling_load_approximation_confirmed,
            "LOAD_COVERAGE",
            (
                "Approximate cycling load has not been confirmed "
                "against the verified rule"
            ),
        )
    check(
        procedure_context.cycling_target_load_g <= selected.max_capacity_g,
        "RANGE",
        "Endurance cycling target exceeds selected range",
    )
    if policy.require_after_other_tests:
        check(
            procedure_context.after_other_tests_confirmed,
            "STAGE",
            "Endurance test was not confirmed after the other required tests",
        )
    if policy.require_loaded_equilibrium_each_cycle:
        check(
            procedure_context.loaded_equilibrium_each_cycle_confirmed,
            "FUNCTIONAL",
            "Loaded equilibrium for each endurance cycle is not confirmed",
        )
    if policy.require_unloaded_equilibrium_each_cycle:
        check(
            procedure_context.unloaded_equilibrium_each_cycle_confirmed,
            "FUNCTIONAL",
            "Unloaded equilibrium for each endurance cycle is not confirmed",
        )
    if policy.require_normal_loading_force:
        check(
            procedure_context.normal_loading_force_confirmed,
            "FUNCTIONAL",
            "Normal loading-force condition is not confirmed",
        )
    if policy.require_same_reference_weights:
        check(
            procedure_context.same_reference_weights_confirmed,
            "EQUIPMENT",
            (
                "Initial/final endurance measurements require "
                "the same reference weights"
            ),
        )
    if policy.require_abnormal_events_resolved:
        check(
            not procedure_context.abnormal_events
            or procedure_context.abnormal_events_resolved,
            "FUNCTIONAL",
            "Endurance run contains unresolved abnormal events",
        )
    if policy.require_pre_post_weighing_procedure_confirmation:
        check(
            procedure_context.pre_post_weighing_procedure_confirmed,
            "STAGE",
            "Pre/post weighing procedure confirmation is missing",
        )

    grouped = {}
    for row in rows:
        grouped.setdefault(row.point_id, []).append(row)
        check(
            row.load_g <= selected.max_capacity_g,
            "RANGE",
            "Endurance performance load exceeds selected range",
            sequence=row.sequence_no,
        )
        if policy.require_stabilized_performance_observations:
            check(
                row.stabilized,
                "STABILIZATION",
                "Endurance performance observation is not stabilized",
                sequence=row.sequence_no,
            )

    check(
        len(grouped) >= policy.minimum_performance_load_points,
        "LOAD_COVERAGE",
        (
            "Insufficient distinct pre/post endurance "
            "performance load points"
        ),
        missing=True,
    )
    if policy.require_max_performance_point:
        check(
            any(
                any(row.load_g == selected.max_capacity_g for row in point_rows)
                for point_rows in grouped.values()
            ),
            "LOAD_COVERAGE",
            "Endurance pre/post weighing coverage does not include Max",
            missing=True,
        )
    for point_id, point_rows in grouped.items():
        initial = [row for row in point_rows if row.phase == "INITIAL"]
        final = [row for row in point_rows if row.phase == "FINAL"]
        check(
            len(initial) == 1 and len(final) == 1,
            "COUNT",
            (
                f"Endurance point {point_id} requires exactly one "
                "initial and one final observation"
            ),
            missing=not initial or not final,
        )
        if len(initial) == 1 and len(final) == 1:
            check(
                initial[0].load_g == final[0].load_g,
                "LOAD_COVERAGE",
                f"Endurance initial/final load differs at {point_id}",
            )
    return tuple(issues)


def _evaluate_endurance_v2(
    evaluator,
    instrument_snapshot,
    procedure_context,
    observations,
    ruleset,
):
    policy = _endurance_policy(ruleset)
    refs = _refs(ruleset, evaluator)
    selected = instrument_snapshot.select_range(procedure_context.range_no)
    loads = sorted({row.load_g for row in observations.rows})
    limits = []
    for load_g in loads:
        mpe = calculate_mpe_compatible(
            load_g=load_g,
            selected_range=selected,
            accuracy_class=instrument_snapshot.accuracy_class,
            evaluation_context=procedure_context.evaluation_context,
            ruleset=ruleset,
            rule_id=ENDURANCE_MPE,
        )
        limits.append(
            Stage4LoadLimit(
                load_g=load_g,
                limit=_stage4_limit_from_mpe(
                    mpe=mpe,
                    multiplier=policy.durability_mpe_multiplier,
                    operator=policy.durability_operator,
                    semantics=policy.durability_semantics,
                    name=f"endurance_durability_mpe:{load_g}",
                ),
            )
        )
    result = endurance_mechanics(
        observations.rows,
        verification_interval_e_g=selected.verification_interval_e_g,
        durability_limits=tuple(limits),
    )
    return _native_output(result, refs, "ENDURANCE")


@dataclass(frozen=True)
class EnduranceFix11Evaluator:
    delegate: EnduranceEvaluator

    def required_rules(self, **kwargs):
        return self.delegate.required_rules(**kwargs)

    def applicability(self, **kwargs):
        return self.delegate.applicability(**kwargs)

    def validate_procedure(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.validate_procedure(**kwargs)
        return _validate_endurance_v2(self, **kwargs)

    def evaluate(self, **kwargs):
        if kwargs["procedure_context"].procedure_schema_version == "v1":
            return self.delegate.evaluate(**kwargs)
        return _evaluate_endurance_v2(self, **kwargs)


def voltage_variation_registration():
    registration = _legacy_voltage_registration()
    registration = _replace_policy_schema(
        registration,
        "voltage_variation_procedure_v2",
        VerifiedVoltageVariationPolicyV2,
    )
    return replace(
        registration,
        evaluator=VoltageVariationFix11Evaluator(registration.evaluator),
        implementation_version="section11-fix11-v2",
    )


def damp_heat_registration():
    registration = _legacy_damp_heat_registration()
    registration = _replace_policy_schema(
        registration,
        "damp_heat_procedure_v2",
        VerifiedDampHeatPolicyV2,
    )
    return replace(
        registration,
        evaluator=DampHeatFix11Evaluator(registration.evaluator),
        implementation_version="section13-fix11-v2",
    )


def span_stability_registration():
    registration = _legacy_span_stability_registration()
    registration = _replace_policy_schema(
        registration,
        "span_stability_procedure_v2",
        VerifiedSpanStabilityPolicyV2,
    )
    registration = _replace_v2_context(
        registration,
        VerifiedSpanStabilityContextV2,
    )
    return replace(
        registration,
        evaluator=SpanStabilityFix11Evaluator(registration.evaluator),
        implementation_version="section14-fix11-v2",
    )


def endurance_registration():
    registration = _legacy_endurance_registration()
    registration = _replace_policy_schema(
        registration,
        "endurance_procedure_v2",
        VerifiedEndurancePolicyV2,
    )
    registration = _replace_v2_context(
        registration,
        VerifiedEnduranceContextV2,
    )
    return replace(
        registration,
        evaluator=EnduranceFix11Evaluator(registration.evaluator),
        implementation_version="section15-fix11-v2",
    )


__all__ = [
    "DampHeatFix11Evaluator",
    "EnduranceFix11Evaluator",
    "SpanStabilityFix11Evaluator",
    "VerifiedDampHeatPolicyV2",
    "VerifiedEnduranceContextV2",
    "VerifiedEndurancePolicyV2",
    "VerifiedSpanStabilityContextV2",
    "VerifiedSpanStabilityPolicyV2",
    "VerifiedVoltageVariationPolicyV2",
    "VoltageVariationFix11Evaluator",
    "damp_heat_registration",
    "endurance_registration",
    "span_stability_registration",
    "voltage_variation_registration",
]
