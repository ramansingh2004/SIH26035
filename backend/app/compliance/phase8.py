"""Phase 8 influence-test mechanics.

REG-05, REG-11, REG-12 and REG-16 remain regulatory gates.  This module
contains typed procedure/observation contracts and deterministic mechanics,
but no hard-coded OIML thresholds.  Acceptance values are supplied only by a
verified or explicitly synthetic pinned RuleSet policy.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.applicability import ApplicabilityEngine, ApplicabilityPolicy
from app.compliance.domain import (
    AcceptanceLimit,
    CalculationTraceEntry,
    ComplianceOutcome,
    Digest,
    EvaluationOutput,
    FailedCondition,
    Frozen,
    Number,
    Observation,
    PositiveInt,
    ProcedureValidationIssue,
    RangeProcedureContext,
    Text,
    ordered_unique,
)
from app.compliance.evaluators import EvaluatorRegistration, RulePolicyRegistration
from app.compliance.numbers import (
    calculate_corrected_error,
    calculate_error,
    calculate_prerounding_indication,
    compare,
    exact,
)
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import (
    MpeProfile,
    calculate_mpe,
    dependencies,
    rule_policy,
)
from app.compliance.weighing import (
    MeasurementTime,
    WeighingEnvironment,
    WeighingEquipment,
)


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code=("MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE"),
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


def _functional_limit(*, name, value, operator, semantics, refs, unit="1"):
    return AcceptanceLimit(
        name=name,
        value=value,
        unit=unit,
        operator=operator,
        semantics=semantics,
        rule_references=refs,
    )


class _EvidenceContext(RangeProcedureContext):
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_evidence(self):
        object.__setattr__(
            self,
            "equipment",
            ordered_unique(self.equipment, lambda item: item.reference),
        )
        object.__setattr__(
            self,
            "evidence_hashes",
            tuple(sorted(set(self.evidence_hashes))),
        )
        return self


class CommonInfluencePolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    minimum_count: PositiveInt
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


def _common_issues(policy, context, refs):
    issues = []

    def check(condition, category, reason):
        if not condition:
            issues.append(_issue(refs, category, reason))

    check(
        context.evaluation_context == policy.evaluation_context,
        "STAGE",
        "Evaluation context incompatible with verified procedure",
    )
    check(
        not policy.require_environment or bool(context.environment),
        "ENVIRONMENT",
        "Required environment evidence missing",
    )
    check(
        not policy.require_equipment or bool(context.equipment),
        "EQUIPMENT",
        "Required equipment evidence missing",
    )
    if policy.require_certificate:
        check(
            bool(context.equipment)
            and all(
                item.calibration_certificate_no and item.certificate_content_hash
                for item in context.equipment
            ),
            "EQUIPMENT",
            "Required calibration certificate evidence missing",
        )
    check(
        not policy.require_evidence or bool(context.evidence_hashes),
        "EVIDENCE",
        "Required supporting evidence missing",
    )
    return issues


# ---------------------------------------------------------------------------
# Section 2 — temperature effect on no-load indication
# ---------------------------------------------------------------------------

TEMPERATURE_ZERO = "TEMPERATURE_ZERO"
TEMPERATURE_ZERO_POLICY = "SECTION2_TEMPERATURE_ZERO_PROCEDURE"
TEMPERATURE_ZERO_CLASSIFICATION = "SECTION2_CLASSIFICATION"
TEMPERATURE_ZERO_CALIBRATION = "SECTION2_CALIBRATION"


class TemperatureZeroContext(_EvidenceContext):
    test_code: Literal["TEMPERATURE_ZERO"] = TEMPERATURE_ZERO
    procedure_variant: Literal["TEMPERATURE_SEQUENCE"] = "TEMPERATURE_SEQUENCE"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["TEMPERATURE_ZERO_V1"] = "TEMPERATURE_ZERO_V1"
    temperature_sequence_c: tuple[Number, ...] = Field(min_length=2)
    zero_tracking_disabled: StrictBool | None = None

    @model_validator(mode="after")
    def unique_temperature_sequence(self):
        if len(set(self.temperature_sequence_c)) != len(self.temperature_sequence_c):
            raise ValueError("Duplicate temperature point")
        return self


class TemperatureZeroObservation(Observation):
    test_code: Literal["TEMPERATURE_ZERO"] = TEMPERATURE_ZERO
    protocol: Literal["TEMPERATURE_ZERO_V1"] = "TEMPERATURE_ZERO_V1"
    observation_schema_version: Literal["v1"] = "v1"
    temperature_c: Number
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    stabilized: StrictBool
    zero_tracking_active: StrictBool | None = None
    measured_at: MeasurementTime


class TemperatureZeroPolicy(CommonInfluencePolicy):
    accuracy_class: Literal["I", "II", "III", "IIII"]
    required_temperature_sequence_c: tuple[Number, ...] = Field(min_length=2)
    normalization_span_c: Number = Field(gt=0)
    limit_multiplier_e: Number = Field(ge=0)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]
    require_stabilized_observations: StrictBool
    require_zero_tracking_disabled: StrictBool
    require_declared_temperature_range: StrictBool

    @model_validator(mode="after")
    def sequence(self):
        if len(set(self.required_temperature_sequence_c)) != len(
            self.required_temperature_sequence_c
        ):
            raise ValueError("Duplicate required temperature point")
        return self


@dataclass(frozen=True)
class TemperatureZeroEvaluator:
    def required_rules(self, **kwargs):
        return (
            TEMPERATURE_ZERO_POLICY,
            TEMPERATURE_ZERO_CLASSIFICATION,
            TEMPERATURE_ZERO_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=TEMPERATURE_ZERO,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            TEMPERATURE_ZERO_POLICY,
            "temperature_zero_procedure_v1",
            TemperatureZeroPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        issues = list(_common_issues(policy, procedure_context, refs))
        rows = observations.rows

        def check(
            condition,
            category,
            reason,
            sequence=None,
            missing=False,
        ):
            if not condition:
                issues.append(
                    _issue(
                        refs,
                        category,
                        reason,
                        sequence=sequence,
                        missing=missing,
                    )
                )

        instrument_snapshot.select_range(procedure_context.range_no)
        check(
            instrument_snapshot.accuracy_class == policy.accuracy_class,
            "STAGE",
            "Accuracy class differs from verified temperature policy",
        )
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required temperature observations missing",
            missing=True,
        )
        check(
            procedure_context.temperature_sequence_c == policy.required_temperature_sequence_c,
            "STAGE",
            "Temperature sequence differs from verified procedure",
        )
        check(
            tuple(row.temperature_c for row in rows) == policy.required_temperature_sequence_c,
            "ORDER",
            "Observed temperature sequence is incomplete or out of order",
            missing=True,
        )
        if policy.require_zero_tracking_disabled:
            check(
                procedure_context.zero_tracking_disabled is True,
                "FUNCTIONAL",
                "Verified procedure requires zero tracking to be disabled",
            )

        if policy.require_declared_temperature_range:
            check(
                instrument_snapshot.declared_temp_min_c is not None
                and instrument_snapshot.declared_temp_max_c is not None,
                "ENVIRONMENT",
                "Declared temperature range is required",
            )
            if (
                instrument_snapshot.declared_temp_min_c is not None
                and instrument_snapshot.declared_temp_max_c is not None
            ):
                for value in policy.required_temperature_sequence_c:
                    check(
                        instrument_snapshot.declared_temp_min_c
                        <= value
                        <= instrument_snapshot.declared_temp_max_c,
                        "ENVIRONMENT",
                        "Required temperature is outside declared range",
                    )

        previous = None
        for row in rows:
            if policy.require_stabilized_observations:
                check(
                    row.stabilized,
                    "STABILIZATION",
                    "Temperature observation is not stabilized",
                    row.sequence_no,
                )
            if policy.require_zero_tracking_disabled:
                check(
                    row.zero_tracking_active is False,
                    "FUNCTIONAL",
                    "Zero tracking state could mask temperature zero drift",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous = row.measured_at
        return tuple(issues)

    def evaluate(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            TEMPERATURE_ZERO_POLICY,
            "temperature_zero_procedure_v1",
            TemperatureZeroPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        limit_value = exact(
            "multiply",
            selected.verification_interval_e_g,
            policy.limit_multiplier_e,
        )
        limit = _functional_limit(
            name="normalized_zero_drift",
            value=limit_value,
            operator=policy.operator,
            semantics=policy.semantics,
            refs=refs,
            unit="g",
        )

        prerounding = []
        calculations = []
        limits = []
        failures = []

        for row in observations.rows:
            value = calculate_prerounding_indication(
                row.indication_g,
                selected.verification_interval_e_g,
                row.additional_load_g,
            )
            prerounding.append((row, value))
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:zero_prerounding",
                    expression="I0 + 0.5e - additional_load",
                    value=value,
                    unit="g",
                    rule_references=refs,
                )
            )

        for (left_row, left), (right_row, right) in zip(
            prerounding,
            prerounding[1:],
            strict=False,
        ):
            zero_change = exact(
                "subtract",
                right,
                left,
            ).copy_abs()
            temperature_change = exact(
                "subtract",
                right_row.temperature_c,
                left_row.temperature_c,
            ).copy_abs()
            normalized = exact(
                "divide",
                exact(
                    "multiply",
                    zero_change,
                    policy.normalization_span_c,
                ),
                temperature_change,
            )
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{left_row.sequence_no}-{right_row.sequence_no}:normalized_zero_drift"),
                    expression=("|P2-P1| * normalization_span / |T2-T1|"),
                    value=normalized,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(
                normalized,
                limit.value,
                operator=limit.operator,
                semantics=limit.semantics,
            ):
                failures.append(
                    FailedCondition(
                        code="TEMPERATURE_ZERO_DRIFT_LIMIT_EXCEEDED",
                        reason=("Normalized zero drift violates the verified temperature limit"),
                        actual=normalized,
                        limit=limit,
                    )
                )

        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failures else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=(
                "Complete temperature-zero procedure evaluated using pinned verified dependencies",
            ),
        )


def temperature_zero_registration():
    return EvaluatorRegistration(
        TEMPERATURE_ZERO,
        TemperatureZeroEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(
                    TEMPERATURE_ZERO,
                    "TEMPERATURE_SEQUENCE",
                    "v1",
                    TemperatureZeroContext,
                ),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    TEMPERATURE_ZERO,
                    "TEMPERATURE_ZERO_V1",
                    "v1",
                    TemperatureZeroObservation,
                ),
            )
        ),
        implementation_version="section2-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "temperature_zero_procedure_v1",
                TemperatureZeroPolicy,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Section 8 — tilting
# ---------------------------------------------------------------------------

TILTING = "TILTING"
TILTING_POLICY = "SECTION8_TILTING_PROCEDURE"
TILTING_MPE = "SECTION8_MPE"
TILTING_CLASSIFICATION = "SECTION8_CLASSIFICATION"
TILTING_CALIBRATION = "SECTION8_CALIBRATION"

TiltMode = Literal[
    "LEVEL_INDICATOR",
    "AUTOMATIC_TILT_SENSOR",
    "NO_LEVEL_DEVICE",
    "MOBILE_AUTOMATIC_TILT_SENSOR",
    "MOBILE_CARDANIC",
]
TiltDirection = Literal["FORWARD", "BACKWARD", "LEFT", "RIGHT"]


class TiltingContext(_EvidenceContext):
    test_code: Literal["TILTING"] = TILTING
    procedure_variant: TiltMode
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["TILTING_V1"] = "TILTING_V1"
    tilt_mode: TiltMode
    reference_tilt_value: Number
    test_tilt_value: Number
    directions: tuple[TiltDirection, ...] = Field(min_length=1)
    reference_position_confirmed: StrictBool
    protection_behavior_checked: StrictBool | None = None

    @model_validator(mode="after")
    def mode_and_directions(self):
        if self.tilt_mode != self.procedure_variant:
            raise ValueError("Tilt mode must match procedure variant")
        object.__setattr__(
            self,
            "directions",
            ordered_unique(self.directions, lambda value: value),
        )
        return self


class TiltingObservation(Observation):
    test_code: Literal["TILTING"] = TILTING
    protocol: Literal["TILTING_V1"] = "TILTING_V1"
    observation_schema_version: Literal["v1"] = "v1"
    direction: TiltDirection
    stage: Literal["REFERENCE", "TILTED"]
    tilt_value: Number
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    warning_generated: StrictBool | None = None
    display_operational: StrictBool | None = None
    printing_inhibited: StrictBool | None = None
    transmission_inhibited: StrictBool | None = None
    measured_at: MeasurementTime


class TiltingPolicy(CommonInfluencePolicy):
    tilt_mode: TiltMode
    required_directions: tuple[TiltDirection, ...] = Field(min_length=1)
    required_loads_g: tuple[Number, ...] = Field(min_length=1)
    reference_tilt_value: Number
    test_tilt_value: Number
    unloaded_limit_multiplier_e: Number = Field(ge=0)
    unloaded_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    unloaded_semantics: Literal["SIGNED", "ABSOLUTE"]
    require_reference_position: StrictBool
    required_warning: StrictBool | None = None
    required_display_operational: StrictBool | None = None
    required_printing_inhibited: StrictBool | None = None
    required_transmission_inhibited: StrictBool | None = None

    @model_validator(mode="after")
    def canonical_policy(self):
        object.__setattr__(
            self,
            "required_directions",
            ordered_unique(
                self.required_directions,
                lambda value: value,
            ),
        )
        if len(set(self.required_loads_g)) != len(self.required_loads_g):
            raise ValueError("Duplicate required tilt load")
        object.__setattr__(
            self,
            "required_loads_g",
            tuple(sorted(self.required_loads_g)),
        )
        return self


@dataclass(frozen=True)
class TiltingEvaluator:
    def required_rules(self, **kwargs):
        return (
            TILTING_POLICY,
            TILTING_MPE,
            TILTING_CLASSIFICATION,
            TILTING_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=TILTING,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            TILTING_POLICY,
            "tilting_procedure_v1",
            TiltingPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        issues = list(_common_issues(policy, procedure_context, refs))
        rows = observations.rows
        selected = instrument_snapshot.select_range(procedure_context.range_no)

        def check(
            condition,
            category,
            reason,
            sequence=None,
            missing=False,
        ):
            if not condition:
                issues.append(
                    _issue(
                        refs,
                        category,
                        reason,
                        sequence=sequence,
                        missing=missing,
                    )
                )

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required tilt observations missing",
            missing=True,
        )
        check(
            procedure_context.tilt_mode == policy.tilt_mode,
            "STAGE",
            "Tilt mode differs from verified procedure",
        )
        check(
            procedure_context.reference_tilt_value == policy.reference_tilt_value
            and procedure_context.test_tilt_value == policy.test_tilt_value,
            "STAGE",
            "Tilt values differ from verified procedure",
        )
        check(
            set(procedure_context.directions) == set(policy.required_directions),
            "STAGE",
            "Tilt directions differ from verified procedure",
        )
        if policy.require_reference_position:
            check(
                procedure_context.reference_position_confirmed,
                "STAGE",
                "Reference position was not confirmed",
            )

        for load in policy.required_loads_g:
            check(
                load <= selected.max_capacity_g,
                "RANGE",
                "Required tilt load exceeds selected range",
            )
            for direction in policy.required_directions:
                for stage in ("REFERENCE", "TILTED"):
                    matches = [
                        row
                        for row in rows
                        if row.load_g == load and row.direction == direction and row.stage == stage
                    ]
                    check(
                        len(matches) == 1,
                        "LOAD_COVERAGE",
                        (
                            "Each verified direction/load requires exactly "
                            "one reference and one tilted observation"
                        ),
                        missing=not matches,
                    )

        previous = None
        for row in rows:
            check(
                row.direction in policy.required_directions,
                "STAGE",
                "Unexpected tilt direction",
                row.sequence_no,
            )
            check(
                row.load_g in policy.required_loads_g,
                "LOAD_COVERAGE",
                "Unexpected tilt load",
                row.sequence_no,
            )
            expected_tilt = (
                policy.reference_tilt_value if row.stage == "REFERENCE" else policy.test_tilt_value
            )
            check(
                row.tilt_value == expected_tilt,
                "STAGE",
                "Observed tilt value differs from verified stage",
                row.sequence_no,
            )
            if policy.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous = row.measured_at

        functional_required = any(
            value is not None
            for value in (
                policy.required_warning,
                policy.required_display_operational,
                policy.required_printing_inhibited,
                policy.required_transmission_inhibited,
            )
        )
        if functional_required:
            check(
                procedure_context.protection_behavior_checked is True,
                "FUNCTIONAL",
                "Verified tilt protection behavior was not checked",
            )
            for row in rows:
                if row.stage != "TILTED":
                    continue
                for actual, expected, label in (
                    (
                        row.warning_generated,
                        policy.required_warning,
                        "warning",
                    ),
                    (
                        row.display_operational,
                        policy.required_display_operational,
                        "display",
                    ),
                    (
                        row.printing_inhibited,
                        policy.required_printing_inhibited,
                        "printing",
                    ),
                    (
                        row.transmission_inhibited,
                        policy.required_transmission_inhibited,
                        "transmission",
                    ),
                ):
                    if expected is not None:
                        check(
                            actual is not None,
                            "FUNCTIONAL",
                            (f"Required tilt protection {label} behavior was not recorded"),
                            row.sequence_no,
                            missing=True,
                        )
        return tuple(issues)

    def evaluate(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            TILTING_POLICY,
            "tilting_procedure_v1",
            TiltingPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        rows = observations.rows
        calculations = []
        limits = []
        failures = []

        def corrected(row):
            prerounding = calculate_prerounding_indication(
                row.indication_g,
                selected.verification_interval_e_g,
                row.additional_load_g,
            )
            error = calculate_error(prerounding, row.load_g)
            return prerounding, calculate_corrected_error(
                error,
                row.zero_error_g,
            )

        for load in policy.required_loads_g:
            for direction in policy.required_directions:
                reference = next(
                    row
                    for row in rows
                    if row.load_g == load
                    and row.direction == direction
                    and row.stage == "REFERENCE"
                )
                tilted = next(
                    row
                    for row in rows
                    if row.load_g == load and row.direction == direction and row.stage == "TILTED"
                )
                reference_p, reference_ec = corrected(reference)
                tilted_p, tilted_ec = corrected(tilted)

                if load == 0:
                    actual = exact(
                        "subtract",
                        tilted_p,
                        reference_p,
                    )
                    limit = _functional_limit(
                        name="tilt_unloaded_difference",
                        value=exact(
                            "multiply",
                            selected.verification_interval_e_g,
                            policy.unloaded_limit_multiplier_e,
                        ),
                        operator=policy.unloaded_operator,
                        semantics=policy.unloaded_semantics,
                        refs=refs,
                        unit="g",
                    )
                else:
                    actual = exact(
                        "subtract",
                        tilted_ec,
                        reference_ec,
                    )
                    limit = calculate_mpe(
                        load_g=load,
                        selected_range=selected,
                        accuracy_class=instrument_snapshot.accuracy_class,
                        evaluation_context=(procedure_context.evaluation_context),
                        ruleset=ruleset,
                        rule_id=TILTING_MPE,
                    )

                calculations.append(
                    CalculationTraceEntry(
                        name=(f"{direction.lower()}:{load}:tilt_difference"),
                        expression=("tilted result - reference-position result"),
                        value=actual,
                        unit="g",
                        rule_references=refs,
                    )
                )
                limits.append(limit)
                if not compare(
                    actual,
                    limit.value,
                    operator=limit.operator,
                    semantics=limit.semantics,
                ):
                    failures.append(
                        FailedCondition(
                            code="TILT_MEASUREMENT_LIMIT_EXCEEDED",
                            reason=(
                                f"{direction} tilt result at load {load} violates verified limit"
                            ),
                            actual=actual,
                            limit=limit,
                        )
                    )

        functional_limit = _functional_limit(
            name="required_tilt_protection_behavior",
            value="1",
            operator="==",
            semantics="SIGNED",
            refs=refs,
        )
        for row in rows:
            if row.stage != "TILTED":
                continue
            checks = (
                (
                    row.warning_generated,
                    policy.required_warning,
                ),
                (
                    row.display_operational,
                    policy.required_display_operational,
                ),
                (
                    row.printing_inhibited,
                    policy.required_printing_inhibited,
                ),
                (
                    row.transmission_inhibited,
                    policy.required_transmission_inhibited,
                ),
            )
            active = [actual == expected for actual, expected in checks if expected is not None]
            if not active:
                continue
            behavior_ok = all(active)
            value = "1" if behavior_ok else "0"
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:tilt_protection_behavior"),
                    expression="verified tilt protection behavior",
                    value=value,
                    unit="1",
                    rule_references=refs,
                )
            )
            limits.append(functional_limit)
            if not behavior_ok:
                failures.append(
                    FailedCondition(
                        code="TILT_PROTECTION_BEHAVIOR_FAILED",
                        reason=(
                            f"Observation {row.sequence_no} violates "
                            "verified tilt protection behavior"
                        ),
                        actual=value,
                        limit=functional_limit,
                    )
                )

        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failures else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=("Complete tilting procedure evaluated using pinned verified dependencies",),
        )


def tilting_registration():
    variants = (
        "LEVEL_INDICATOR",
        "AUTOMATIC_TILT_SENSOR",
        "NO_LEVEL_DEVICE",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
        "MOBILE_CARDANIC",
    )
    return EvaluatorRegistration(
        TILTING,
        TiltingEvaluator(),
        ProcedureContextRegistry(
            tuple(
                ContextRegistration(
                    TILTING,
                    variant,
                    "v1",
                    TiltingContext,
                )
                for variant in variants
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    TILTING,
                    "TILTING_V1",
                    "v1",
                    TiltingObservation,
                ),
            )
        ),
        implementation_version="section8-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "tilting_procedure_v1",
                TiltingPolicy,
            ),
            RulePolicyRegistration(
                "mpe_profile_v1",
                MpeProfile,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Section 10 — warm-up time
# ---------------------------------------------------------------------------

WARM_UP = "WARM_UP"
WARM_UP_POLICY = "SECTION10_WARM_UP_PROCEDURE"
WARM_UP_MPE = "SECTION10_MPE"
WARM_UP_CLASSIFICATION = "SECTION10_CLASSIFICATION"
WARM_UP_CALIBRATION = "SECTION10_CALIBRATION"


class WarmUpContext(_EvidenceContext):
    test_code: Literal["WARM_UP"] = WARM_UP
    procedure_variant: Literal["WARM_UP"] = "WARM_UP"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["WARM_UP_V1"] = "WARM_UP_V1"
    power_off_seconds: Number = Field(ge=0)
    test_load_g: Number = Field(ge=0)
    first_stable_indication_observed: StrictBool
    zero_set_after_power_on: StrictBool


class WarmUpObservation(Observation):
    test_code: Literal["WARM_UP"] = WARM_UP
    protocol: Literal["WARM_UP_V1"] = "WARM_UP_V1"
    observation_schema_version: Literal["v1"] = "v1"
    elapsed_s: Number = Field(ge=0)
    zero_indication_g: Number
    zero_additional_load_g: Number = Field(ge=0)
    load_g: Number = Field(ge=0)
    loaded_indication_g: Number
    loaded_additional_load_g: Number = Field(ge=0)
    temperature_c: Number | None = None
    stabilized: StrictBool
    measured_at: MeasurementTime


class WarmUpPolicy(CommonInfluencePolicy):
    minimum_power_off_seconds: Number = Field(ge=0)
    required_checkpoints_s: tuple[Number, ...] = Field(min_length=1)
    checkpoint_tolerance_s: Number = Field(ge=0)
    test_load_g: Number = Field(ge=0)
    require_first_stable_indication: StrictBool
    require_zero_after_power_on: StrictBool
    require_stabilized_observations: StrictBool

    @model_validator(mode="after")
    def checkpoints(self):
        ordered = tuple(sorted(self.required_checkpoints_s))
        if len(set(ordered)) != len(ordered):
            raise ValueError("Duplicate warm-up checkpoint")
        twice_tolerance = exact(
            "multiply",
            self.checkpoint_tolerance_s,
            "2",
        )
        for left, right in zip(
            ordered,
            ordered[1:],
            strict=False,
        ):
            if exact("subtract", right, left) <= twice_tolerance:
                raise ValueError("Warm-up checkpoint tolerance windows overlap")
        object.__setattr__(
            self,
            "required_checkpoints_s",
            ordered,
        )
        return self


def _warm_up_checkpoint_rows(policy, rows):
    result = []
    for checkpoint in policy.required_checkpoints_s:
        matches = [
            row
            for row in rows
            if exact(
                "subtract",
                row.elapsed_s,
                checkpoint,
            ).copy_abs()
            <= policy.checkpoint_tolerance_s
        ]
        if len(matches) == 1:
            result.append((checkpoint, matches[0]))
    return tuple(result)


@dataclass(frozen=True)
class WarmUpEvaluator:
    def required_rules(self, **kwargs):
        return (
            WARM_UP_POLICY,
            WARM_UP_MPE,
            WARM_UP_CLASSIFICATION,
            WARM_UP_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=WARM_UP,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            WARM_UP_POLICY,
            "warm_up_procedure_v1",
            WarmUpPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        issues = list(_common_issues(policy, procedure_context, refs))
        rows = observations.rows
        selected = instrument_snapshot.select_range(procedure_context.range_no)

        def check(
            condition,
            category,
            reason,
            sequence=None,
            missing=False,
        ):
            if not condition:
                issues.append(
                    _issue(
                        refs,
                        category,
                        reason,
                        sequence=sequence,
                        missing=missing,
                    )
                )

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required warm-up checkpoints missing",
            missing=True,
        )
        check(
            procedure_context.power_off_seconds >= policy.minimum_power_off_seconds,
            "TIMING",
            "Required power-off prerequisite was not reached",
        )
        check(
            procedure_context.test_load_g == policy.test_load_g,
            "LOAD_COVERAGE",
            "Warm-up test load differs from verified procedure",
        )
        check(
            procedure_context.test_load_g <= selected.max_capacity_g,
            "RANGE",
            "Warm-up load exceeds selected range",
        )
        if policy.require_first_stable_indication:
            check(
                procedure_context.first_stable_indication_observed,
                "STABILIZATION",
                "First stable indication was not observed",
            )
        if policy.require_zero_after_power_on:
            check(
                procedure_context.zero_set_after_power_on,
                "STAGE",
                "Verified procedure requires zeroing after power-on",
            )

        matches = _warm_up_checkpoint_rows(policy, rows)
        for checkpoint in policy.required_checkpoints_s:
            count = sum(1 for matched_checkpoint, _ in matches if matched_checkpoint == checkpoint)
            check(
                count == 1,
                "TIMING",
                (f"Required warm-up checkpoint {checkpoint} s is missing or ambiguous"),
                missing=True,
            )

        previous_elapsed = None
        previous_time = None
        for row in rows:
            check(
                row.load_g == policy.test_load_g,
                "LOAD_COVERAGE",
                "Warm-up observation load differs from verified procedure",
                row.sequence_no,
            )
            if policy.require_stabilized_observations:
                check(
                    row.stabilized,
                    "STABILIZATION",
                    "Warm-up observation is not stabilized",
                    row.sequence_no,
                )
            if previous_elapsed is not None:
                check(
                    row.elapsed_s > previous_elapsed,
                    "ORDER",
                    "Warm-up elapsed times must increase",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous_time is not None:
                check(
                    row.measured_at >= previous_time,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous_elapsed = row.elapsed_s
            previous_time = row.measured_at
        return tuple(issues)

    def evaluate(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            WARM_UP_POLICY,
            "warm_up_procedure_v1",
            WarmUpPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations = []
        limits = []
        failures = []

        for checkpoint, row in _warm_up_checkpoint_rows(
            policy,
            observations.rows,
        ):
            zero_p = calculate_prerounding_indication(
                row.zero_indication_g,
                selected.verification_interval_e_g,
                row.zero_additional_load_g,
            )
            zero_error = calculate_error(zero_p, "0")
            loaded_p = calculate_prerounding_indication(
                row.loaded_indication_g,
                selected.verification_interval_e_g,
                row.loaded_additional_load_g,
            )
            loaded_error = calculate_error(
                loaded_p,
                row.load_g,
            )
            corrected = calculate_corrected_error(
                loaded_error,
                zero_error,
            )
            limit = calculate_mpe(
                load_g=row.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=WARM_UP_MPE,
            )
            calculations.append(
                CalculationTraceEntry(
                    name=f"{checkpoint}:warm_up_corrected_error",
                    expression="loaded_error - zero_error",
                    value=corrected,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(
                corrected,
                limit.value,
                operator=limit.operator,
                semantics=limit.semantics,
            ):
                failures.append(
                    FailedCondition(
                        code="WARM_UP_ERROR_LIMIT_EXCEEDED",
                        reason=(f"Warm-up checkpoint {checkpoint} s violates verified MPE"),
                        actual=corrected,
                        limit=limit,
                    )
                )

        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failures else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=("Complete warm-up procedure evaluated using pinned verified dependencies",),
        )


def warm_up_registration():
    return EvaluatorRegistration(
        WARM_UP,
        WarmUpEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(
                    WARM_UP,
                    "WARM_UP",
                    "v1",
                    WarmUpContext,
                ),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    WARM_UP,
                    "WARM_UP_V1",
                    "v1",
                    WarmUpObservation,
                ),
            )
        ),
        implementation_version="section10-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "warm_up_procedure_v1",
                WarmUpPolicy,
            ),
            RulePolicyRegistration(
                "mpe_profile_v1",
                MpeProfile,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Section 11 — voltage variations
# ---------------------------------------------------------------------------

VOLTAGE_VARIATION = "VOLTAGE_VARIATION"
VOLTAGE_POLICY = "SECTION11_VOLTAGE_PROCEDURE"
VOLTAGE_MPE = "SECTION11_MPE"
VOLTAGE_CLASSIFICATION = "SECTION11_CLASSIFICATION"
VOLTAGE_CALIBRATION = "SECTION11_CALIBRATION"

PowerProfile = Literal[
    "AC_MAINS",
    "EXTERNAL_SUPPLY",
    "BATTERY_NO_CHARGING",
    "VEHICLE_SUPPLY",
]


class VoltageVariationContext(_EvidenceContext):
    test_code: Literal["VOLTAGE_VARIATION"] = VOLTAGE_VARIATION
    procedure_variant: PowerProfile
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["VOLTAGE_VARIATION_V1"] = "VOLTAGE_VARIATION_V1"
    power_supply_profile: PowerProfile
    reference_voltage_v: Number = Field(gt=0)
    protection_behavior_checked: StrictBool

    @model_validator(mode="after")
    def profile(self):
        if self.power_supply_profile != self.procedure_variant:
            raise ValueError("Power supply profile must match procedure variant")
        return self


class VoltageVariationObservation(Observation):
    test_code: Literal["VOLTAGE_VARIATION"] = VOLTAGE_VARIATION
    protocol: Literal["VOLTAGE_VARIATION_V1"] = "VOLTAGE_VARIATION_V1"
    observation_schema_version: Literal["v1"] = "v1"
    applied_voltage_v: Number = Field(gt=0)
    load_g: Number = Field(ge=0)
    operational_state: Literal["INDICATING", "SWITCHED_OFF"]
    functions_operational: StrictBool
    indication_g: Number | None = None
    additional_load_g: Number | None = Field(None, ge=0)
    zero_error_g: Number | None = None
    measured_at: MeasurementTime

    @model_validator(mode="after")
    def measurement_state(self):
        values = (
            self.indication_g,
            self.additional_load_g,
            self.zero_error_g,
        )
        if self.operational_state == "INDICATING":
            if any(value is None for value in values):
                raise ValueError("Indicating voltage observation requires measurement values")
        return self


class VoltageVariationPolicy(CommonInfluencePolicy):
    power_supply_profile: PowerProfile
    instrument_power_supply_type: Text
    reference_voltage_v: Number = Field(gt=0)
    expected_nominal_voltage_v: Number | None = Field(None, gt=0)
    expected_min_voltage_v: Number | None = Field(None, gt=0)
    expected_max_voltage_v: Number | None = Field(None, gt=0)
    required_voltages_v: tuple[Number, ...] = Field(min_length=1)
    required_loads_g: tuple[Number, ...] = Field(min_length=1)
    permit_switch_off: StrictBool
    require_functions_operational_when_indicating: StrictBool

    @model_validator(mode="after")
    def canonical_values(self):
        for field in ("required_voltages_v", "required_loads_g"):
            values = getattr(self, field)
            if len(set(values)) != len(values):
                raise ValueError(f"Duplicate value in {field}")
            object.__setattr__(
                self,
                field,
                tuple(sorted(values)),
            )
        return self


@dataclass(frozen=True)
class VoltageVariationEvaluator:
    def required_rules(self, **kwargs):
        return (
            VOLTAGE_POLICY,
            VOLTAGE_MPE,
            VOLTAGE_CLASSIFICATION,
            VOLTAGE_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=VOLTAGE_VARIATION,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            VOLTAGE_POLICY,
            "voltage_variation_procedure_v1",
            VoltageVariationPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        issues = list(_common_issues(policy, procedure_context, refs))
        rows = observations.rows
        selected = instrument_snapshot.select_range(procedure_context.range_no)

        def check(
            condition,
            category,
            reason,
            sequence=None,
            missing=False,
        ):
            if not condition:
                issues.append(
                    _issue(
                        refs,
                        category,
                        reason,
                        sequence=sequence,
                        missing=missing,
                    )
                )

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required voltage/load observations missing",
            missing=True,
        )
        check(
            procedure_context.power_supply_profile == policy.power_supply_profile,
            "POWER",
            "Power profile differs from verified procedure",
        )
        check(
            procedure_context.reference_voltage_v == policy.reference_voltage_v,
            "POWER",
            "Reference voltage differs from verified procedure",
        )
        check(
            instrument_snapshot.power_supply_type == policy.instrument_power_supply_type,
            "POWER",
            "Instrument power supply type differs from verified policy",
        )
        for field_name, expected in (
            (
                "nominal_voltage",
                policy.expected_nominal_voltage_v,
            ),
            (
                "min_voltage",
                policy.expected_min_voltage_v,
            ),
            (
                "max_voltage",
                policy.expected_max_voltage_v,
            ),
        ):
            if expected is not None:
                check(
                    getattr(instrument_snapshot, field_name) == expected,
                    "POWER",
                    (f"Instrument {field_name} differs from verified power profile"),
                )

        for load in policy.required_loads_g:
            check(
                load <= selected.max_capacity_g,
                "RANGE",
                "Required voltage-test load exceeds selected range",
            )
            for voltage in policy.required_voltages_v:
                matches = [
                    row for row in rows if row.load_g == load and row.applied_voltage_v == voltage
                ]
                check(
                    len(matches) == 1,
                    "POWER",
                    ("Each verified voltage/load combination requires exactly one observation"),
                    missing=not matches,
                )

        previous = None
        for row in rows:
            check(
                row.load_g in policy.required_loads_g,
                "LOAD_COVERAGE",
                "Unexpected voltage-test load",
                row.sequence_no,
            )
            check(
                row.applied_voltage_v in policy.required_voltages_v,
                "POWER",
                "Unexpected applied voltage",
                row.sequence_no,
            )
            if row.operational_state == "SWITCHED_OFF":
                check(
                    policy.permit_switch_off,
                    "FUNCTIONAL",
                    "Switch-off is not permitted by verified policy",
                    row.sequence_no,
                )
            elif policy.require_functions_operational_when_indicating:
                check(
                    row.functions_operational,
                    "FUNCTIONAL",
                    ("Required functions are not operational while the instrument is indicating"),
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous = row.measured_at

        check(
            procedure_context.protection_behavior_checked,
            "FUNCTIONAL",
            "Voltage protection behavior was not checked",
        )
        return tuple(issues)

    def evaluate(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        observations,
        ruleset,
    ):
        policy = rule_policy(
            ruleset,
            VOLTAGE_POLICY,
            "voltage_variation_procedure_v1",
            VoltageVariationPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations = []
        limits = []
        failures = []
        functional_limit = _functional_limit(
            name="required_voltage_functional_behavior",
            value="1",
            operator="==",
            semantics="SIGNED",
            refs=refs,
        )

        for row in observations.rows:
            if row.operational_state == "SWITCHED_OFF":
                behavior_ok = policy.permit_switch_off
            else:
                behavior_ok = (
                    not policy.require_functions_operational_when_indicating
                    or row.functions_operational
                )
            functional_value = "1" if behavior_ok else "0"
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:voltage_functional_behavior"),
                    expression="verified voltage operational behavior",
                    value=functional_value,
                    unit="1",
                    rule_references=refs,
                )
            )
            limits.append(functional_limit)
            if not behavior_ok:
                failures.append(
                    FailedCondition(
                        code="VOLTAGE_FUNCTIONAL_BEHAVIOR_FAILED",
                        reason=(
                            f"Observation {row.sequence_no} violates verified voltage behavior"
                        ),
                        actual=functional_value,
                        limit=functional_limit,
                    )
                )

            if row.operational_state != "INDICATING":
                continue

            prerounding = calculate_prerounding_indication(
                row.indication_g,
                selected.verification_interval_e_g,
                row.additional_load_g,
            )
            error = calculate_error(
                prerounding,
                row.load_g,
            )
            corrected = calculate_corrected_error(
                error,
                row.zero_error_g,
            )
            limit = calculate_mpe(
                load_g=row.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=VOLTAGE_MPE,
            )
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:voltage_corrected_error"),
                    expression="error - zero_error",
                    value=corrected,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(
                corrected,
                limit.value,
                operator=limit.operator,
                semantics=limit.semantics,
            ):
                failures.append(
                    FailedCondition(
                        code="VOLTAGE_ERROR_LIMIT_EXCEEDED",
                        reason=(f"Observation {row.sequence_no} violates verified MPE"),
                        actual=corrected,
                        limit=limit,
                    )
                )

        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failures else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=(
                "Complete voltage-variation procedure evaluated using pinned verified dependencies",
            ),
        )


def voltage_variation_registration():
    variants = (
        "AC_MAINS",
        "EXTERNAL_SUPPLY",
        "BATTERY_NO_CHARGING",
        "VEHICLE_SUPPLY",
    )
    return EvaluatorRegistration(
        VOLTAGE_VARIATION,
        VoltageVariationEvaluator(),
        ProcedureContextRegistry(
            tuple(
                ContextRegistration(
                    VOLTAGE_VARIATION,
                    variant,
                    "v1",
                    VoltageVariationContext,
                )
                for variant in variants
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    VOLTAGE_VARIATION,
                    "VOLTAGE_VARIATION_V1",
                    "v1",
                    VoltageVariationObservation,
                ),
            )
        ),
        implementation_version="section11-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "voltage_variation_procedure_v1",
                VoltageVariationPolicy,
            ),
            RulePolicyRegistration(
                "mpe_profile_v1",
                MpeProfile,
            ),
        ),
    )
