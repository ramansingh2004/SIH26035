"""Phase 9 climatic and long-duration test mechanics.

REG-14 and REG-16 remain regulatory gates.  This module supplies typed
procedure/observation contracts and deterministic mechanics for Sections 13
and 14, but it does not embed candidate OIML durations, environmental values,
counts, interval limits, correction rules or acceptance thresholds.
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


def _limit(*, name, value, operator, semantics, refs, unit):
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


class CommonLongDurationPolicy(Frozen):
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
# Section 13 — damp heat, steady state
# ---------------------------------------------------------------------------

DAMP_HEAT = "DAMP_HEAT"
DAMP_HEAT_POLICY = "SECTION13_DAMP_HEAT_PROCEDURE"
DAMP_HEAT_MPE = "SECTION13_MPE"
DAMP_HEAT_CLASSIFICATION = "SECTION13_CLASSIFICATION"
DAMP_HEAT_CALIBRATION = "SECTION13_CALIBRATION"

DampHeatStage = Literal["INITIAL", "HIGH_HUMIDITY", "FINAL"]


class DampHeatStageRequirement(Frozen):
    stage: DampHeatStage
    temperature_min_c: Number
    temperature_max_c: Number
    temperature_lower_operator: Literal[">", ">="]
    temperature_upper_operator: Literal["<", "<="]
    humidity_min_percent: Number = Field(ge=0, le=100)
    humidity_max_percent: Number = Field(ge=0, le=100)
    humidity_lower_operator: Literal[">", ">="]
    humidity_upper_operator: Literal["<", "<="]
    minimum_stabilization_s: Number = Field(ge=0)
    minimum_exposure_s: Number = Field(ge=0)

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.temperature_min_c > self.temperature_max_c:
            raise ValueError("Temperature bounds are reversed")
        if self.humidity_min_percent > self.humidity_max_percent:
            raise ValueError("Humidity bounds are reversed")
        return self


class DampHeatContext(_EvidenceContext):
    test_code: Literal["DAMP_HEAT"] = DAMP_HEAT
    procedure_variant: Literal["STEADY_STATE"] = "STEADY_STATE"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["DAMP_HEAT_V1"] = "DAMP_HEAT_V1"
    stages: tuple[DampHeatStage, ...] = Field(min_length=1)
    loads_g: tuple[Number, ...] = Field(min_length=1)
    same_reference_weights_confirmed: StrictBool

    @model_validator(mode="after")
    def unique_semantics(self):
        if len(set(self.stages)) != len(self.stages):
            raise ValueError("Duplicate damp-heat stage")
        if len(set(self.loads_g)) != len(self.loads_g):
            raise ValueError("Duplicate damp-heat load")
        return self


class DampHeatObservation(Observation):
    test_code: Literal["DAMP_HEAT"] = DAMP_HEAT
    protocol: Literal["DAMP_HEAT_V1"] = "DAMP_HEAT_V1"
    observation_schema_version: Literal["v1"] = "v1"
    stage: DampHeatStage
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    temperature_c: Number
    relative_humidity_percent: Number = Field(ge=0, le=100)
    stage_elapsed_s: Number = Field(ge=0)
    exposure_elapsed_s: Number = Field(ge=0)
    stabilized: StrictBool
    functions_operational: StrictBool
    measured_at: MeasurementTime


class DampHeatPolicy(CommonLongDurationPolicy):
    stage_requirements: tuple[DampHeatStageRequirement, ...] = Field(min_length=1)
    required_loads_g: tuple[Number, ...] = Field(min_length=1)
    require_same_reference_weights: StrictBool
    require_functions_operational: StrictBool

    @model_validator(mode="after")
    def canonical_requirements(self):
        stages = [item.stage for item in self.stage_requirements]
        if len(stages) != len(set(stages)):
            raise ValueError("Duplicate damp-heat stage policy")
        if len(set(self.required_loads_g)) != len(self.required_loads_g):
            raise ValueError("Duplicate required damp-heat load")
        return self


def _within(value, *, lower, lower_operator, upper, upper_operator):
    return compare(
        value,
        lower,
        operator=lower_operator,
        semantics="SIGNED",
    ) and compare(
        value,
        upper,
        operator=upper_operator,
        semantics="SIGNED",
    )


@dataclass(frozen=True)
class DampHeatEvaluator:
    def required_rules(self, **kwargs):
        return (
            DAMP_HEAT_POLICY,
            DAMP_HEAT_MPE,
            DAMP_HEAT_CLASSIFICATION,
            DAMP_HEAT_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=DAMP_HEAT,
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
            DAMP_HEAT_POLICY,
            "damp_heat_procedure_v1",
            DampHeatPolicy,
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

        required_stages = tuple(item.stage for item in policy.stage_requirements)
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required damp-heat observations missing",
            missing=True,
        )
        check(
            procedure_context.stages == required_stages,
            "STAGE",
            "Damp-heat stage sequence differs from verified procedure",
        )
        check(
            procedure_context.loads_g == policy.required_loads_g,
            "LOAD_COVERAGE",
            "Damp-heat loads differ from verified procedure",
        )
        if policy.require_same_reference_weights:
            check(
                procedure_context.same_reference_weights_confirmed,
                "EQUIPMENT",
                "Verified procedure requires the same reference weights",
            )

        expected_pairs = tuple(
            (stage, load) for stage in required_stages for load in policy.required_loads_g
        )
        actual_pairs = tuple((row.stage, row.load_g) for row in rows)
        check(
            actual_pairs == expected_pairs,
            "ORDER",
            "Damp-heat stage/load sequence is incomplete or out of order",
            missing=len(actual_pairs) < len(expected_pairs),
        )

        stage_policy = {item.stage: item for item in policy.stage_requirements}
        previous = None
        for row in rows:
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Damp-heat load exceeds selected range",
                row.sequence_no,
            )
            requirement = stage_policy.get(row.stage)
            if requirement is None:
                check(
                    False,
                    "STAGE",
                    "Unexpected damp-heat stage",
                    row.sequence_no,
                )
                continue
            check(
                _within(
                    row.temperature_c,
                    lower=requirement.temperature_min_c,
                    lower_operator=requirement.temperature_lower_operator,
                    upper=requirement.temperature_max_c,
                    upper_operator=requirement.temperature_upper_operator,
                ),
                "ENVIRONMENT",
                "Temperature outside verified stage bounds",
                row.sequence_no,
            )
            check(
                _within(
                    row.relative_humidity_percent,
                    lower=requirement.humidity_min_percent,
                    lower_operator=requirement.humidity_lower_operator,
                    upper=requirement.humidity_max_percent,
                    upper_operator=requirement.humidity_upper_operator,
                ),
                "ENVIRONMENT",
                "Humidity outside verified stage bounds",
                row.sequence_no,
            )
            check(
                row.stabilized and row.stage_elapsed_s >= requirement.minimum_stabilization_s,
                "STABILIZATION",
                "Verified stage stabilization not completed",
                row.sequence_no,
            )
            check(
                row.exposure_elapsed_s >= requirement.minimum_exposure_s,
                "TIMING",
                "Verified stage exposure duration not reached",
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
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations = []
        limits = []
        failures = []
        functional_limit = _limit(
            name="required_damp_heat_functional_behavior",
            value="1",
            operator="==",
            semantics="SIGNED",
            refs=refs,
            unit="1",
        )

        for row in observations.rows:
            prerounding = calculate_prerounding_indication(
                row.indication_g,
                selected.verification_interval_e_g,
                row.additional_load_g,
            )
            error = calculate_error(prerounding, row.load_g)
            corrected = calculate_corrected_error(
                error,
                row.zero_error_g,
            )
            mpe = calculate_mpe(
                load_g=row.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=DAMP_HEAT_MPE,
            )
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:{row.stage.lower()}:corrected_error"),
                    expression="E - E0",
                    value=corrected,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(mpe)
            if not compare(
                corrected,
                mpe.value,
                operator=mpe.operator,
                semantics=mpe.semantics,
            ):
                failures.append(
                    FailedCondition(
                        code="DAMP_HEAT_ERROR_LIMIT_EXCEEDED",
                        reason=(f"Observation {row.sequence_no} violates verified MPE"),
                        actual=corrected,
                        limit=mpe,
                    )
                )

            behavior = "1" if row.functions_operational else "0"
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.sequence_no}:{row.stage.lower()}:functional_behavior"),
                    expression="verified functional behavior",
                    value=behavior,
                    unit="1",
                    rule_references=refs,
                )
            )
            limits.append(functional_limit)
            if not row.functions_operational:
                failures.append(
                    FailedCondition(
                        code="DAMP_HEAT_FUNCTIONAL_BEHAVIOR_FAILED",
                        reason=(
                            f"Observation {row.sequence_no} violates verified functional behavior"
                        ),
                        actual=behavior,
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
            reasons=("Complete damp-heat procedure evaluated using pinned verified dependencies",),
        )


def damp_heat_registration():
    return EvaluatorRegistration(
        DAMP_HEAT,
        DampHeatEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(
                    DAMP_HEAT,
                    "STEADY_STATE",
                    "v1",
                    DampHeatContext,
                ),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    DAMP_HEAT,
                    "DAMP_HEAT_V1",
                    "v1",
                    DampHeatObservation,
                ),
            )
        ),
        implementation_version="section13-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "damp_heat_procedure_v1",
                DampHeatPolicy,
            ),
            RulePolicyRegistration(
                "mpe_profile_v1",
                MpeProfile,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Section 14 — span stability
# ---------------------------------------------------------------------------

SPAN_STABILITY = "SPAN_STABILITY"
SPAN_STABILITY_POLICY = "SECTION14_SPAN_STABILITY_PROCEDURE"
SPAN_STABILITY_MPE = "SECTION14_MPE"
SPAN_STABILITY_CLASSIFICATION = "SECTION14_CLASSIFICATION"
SPAN_STABILITY_CALIBRATION = "SECTION14_CALIBRATION"


class SpanStabilityContext(_EvidenceContext):
    test_code: Literal["SPAN_STABILITY"] = SPAN_STABILITY
    procedure_variant: Literal["LONG_DURATION"] = "LONG_DURATION"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["SPAN_STABILITY_V1"] = "SPAN_STABILITY_V1"
    test_load_g: Number = Field(ge=0)
    planned_duration_s: Number = Field(ge=0)
    same_reference_weights_confirmed: StrictBool
    extension_completed: StrictBool = False


class SpanStabilityObservation(Observation):
    test_code: Literal["SPAN_STABILITY"] = SPAN_STABILITY
    protocol: Literal["SPAN_STABILITY_V1"] = "SPAN_STABILITY_V1"
    observation_schema_version: Literal["v1"] = "v1"
    measurement_no: PositiveInt
    elapsed_s: Number = Field(ge=0)
    location: Text
    temperature_c: Number
    relative_humidity_percent: Number = Field(ge=0, le=100)
    barometric_pressure_hpa: Number = Field(gt=0)
    event_since_previous_measurement: str | None = None
    power_disconnection_event: StrictBool
    power_disconnection_duration_s: Number | None = Field(None, ge=0)
    temperature_test_event: StrictBool
    damp_heat_event: StrictBool
    extension_measurement: StrictBool = False
    load_g: Number = Field(ge=0)
    zero_indication_g: Number
    zero_additional_load_g: Number = Field(ge=0)
    loaded_indication_g: Number
    loaded_additional_load_g: Number = Field(ge=0)
    influence_correction_g: Number = "0"
    measured_at: MeasurementTime

    @model_validator(mode="after")
    def power_event(self):
        if self.power_disconnection_event:
            if self.power_disconnection_duration_s is None:
                raise ValueError("Power disconnection duration required for event")
        elif self.power_disconnection_duration_s is not None:
            raise ValueError("Power disconnection duration requires an event")
        return self


class SpanStabilityPolicy(CommonLongDurationPolicy):
    test_load_g: Number = Field(ge=0)
    minimum_duration_s: Number = Field(ge=0)
    duration_operator: Literal[">", ">="]
    minimum_interval_s: Number = Field(ge=0)
    minimum_interval_operator: Literal[">", ">="]
    maximum_interval_s: Number = Field(ge=0)
    maximum_interval_operator: Literal["<", "<="]
    require_same_reference_weights: StrictBool
    required_power_disconnections: int = Field(ge=0, strict=True)
    minimum_power_disconnection_s: Number = Field(ge=0)
    correction_mode: Literal["NONE", "ADD", "SUBTRACT"]
    variation_formula: Literal["MAX_E_AND_MPE_MULTIPLIERS"]
    e_multiplier: Number = Field(ge=0)
    mpe_multiplier: Number = Field(ge=0)
    variation_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    variation_semantics: Literal["SIGNED", "ABSOLUTE"]
    trend_extension_required: StrictBool
    trend_window_count: PositiveInt | None = None
    trend_limit_g: Number | None = Field(None, ge=0)
    trend_operator: Literal["<", "<=", ">", ">=", "==", "!="] | None = None
    minimum_extension_measurements: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def coherent_intervals_and_trend(self):
        if self.minimum_interval_s > self.maximum_interval_s:
            raise ValueError("Span-stability interval bounds are reversed")
        trend_fields = (
            self.trend_window_count,
            self.trend_limit_g,
            self.trend_operator,
        )
        if self.trend_extension_required:
            if any(value is None for value in trend_fields):
                raise ValueError("Trend extension requires complete verified trend policy")
            if self.minimum_extension_measurements <= 0:
                raise ValueError("Trend extension requires extension measurements")
        elif any(value is not None for value in trend_fields):
            raise ValueError("Trend parameters supplied while extension is disabled")
        return self


def _span_error(row, selected, correction_mode):
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
    loaded_error = calculate_error(loaded_p, row.load_g)
    corrected = calculate_corrected_error(
        loaded_error,
        zero_error,
    )
    if correction_mode == "ADD":
        corrected = exact(
            "add",
            corrected,
            row.influence_correction_g,
        )
    elif correction_mode == "SUBTRACT":
        corrected = exact(
            "subtract",
            corrected,
            row.influence_correction_g,
        )
    elif row.influence_correction_g != 0:
        raise ValueError("Influence correction supplied while correction mode is NONE")
    return corrected


def _trend_requires_extension(policy, values):
    if not policy.trend_extension_required:
        return False
    window = policy.trend_window_count
    if window is None or len(values) < window:
        return False
    sample = values[-window:]
    deltas = [
        exact("subtract", right, left) for left, right in zip(sample, sample[1:], strict=False)
    ]
    if not deltas:
        return False
    monotonic = all(value > 0 for value in deltas) or all(value < 0 for value in deltas)
    if not monotonic:
        return False
    change = exact(
        "subtract",
        sample[-1],
        sample[0],
    ).copy_abs()
    return compare(
        change,
        policy.trend_limit_g,
        operator=policy.trend_operator,
        semantics="SIGNED",
    )


@dataclass(frozen=True)
class SpanStabilityEvaluator:
    def required_rules(self, **kwargs):
        return (
            SPAN_STABILITY_POLICY,
            SPAN_STABILITY_MPE,
            SPAN_STABILITY_CLASSIFICATION,
            SPAN_STABILITY_CALIBRATION,
        )

    def applicability(
        self,
        *,
        instrument_snapshot,
        procedure_context,
        ruleset,
    ):
        return ApplicabilityEngine().determine(
            test_code=SPAN_STABILITY,
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
            SPAN_STABILITY_POLICY,
            "span_stability_procedure_v1",
            SpanStabilityPolicy,
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
            "Required span-stability measurements missing",
            missing=True,
        )
        check(
            procedure_context.test_load_g == policy.test_load_g,
            "LOAD_COVERAGE",
            "Span-stability load differs from verified procedure",
        )
        check(
            procedure_context.test_load_g <= selected.max_capacity_g,
            "RANGE",
            "Span-stability load exceeds selected range",
        )
        check(
            compare(
                procedure_context.planned_duration_s,
                policy.minimum_duration_s,
                operator=policy.duration_operator,
                semantics="SIGNED",
            ),
            "TIMING",
            "Planned span-stability duration is insufficient",
        )
        if policy.require_same_reference_weights:
            check(
                procedure_context.same_reference_weights_confirmed,
                "EQUIPMENT",
                "Verified procedure requires the same reference weights",
            )

        expected_numbers = tuple(range(1, len(rows) + 1))
        check(
            tuple(row.measurement_no for row in rows) == expected_numbers,
            "ORDER",
            "Measurement numbers must be contiguous and ordered",
        )

        previous_elapsed = None
        previous_time = None
        for row in rows:
            check(
                row.load_g == policy.test_load_g,
                "LOAD_COVERAGE",
                "Observation load differs from verified span load",
                row.sequence_no,
            )
            if policy.correction_mode == "NONE":
                check(
                    row.influence_correction_g == 0,
                    "ENVIRONMENT",
                    "Unverified influence correction supplied",
                    row.sequence_no,
                )
            if previous_elapsed is not None:
                interval = exact(
                    "subtract",
                    row.elapsed_s,
                    previous_elapsed,
                )
                check(
                    compare(
                        interval,
                        policy.minimum_interval_s,
                        operator=policy.minimum_interval_operator,
                        semantics="SIGNED",
                    ),
                    "TIMING",
                    "Measurement interval is below verified minimum",
                    row.sequence_no,
                )
                check(
                    compare(
                        interval,
                        policy.maximum_interval_s,
                        operator=policy.maximum_interval_operator,
                        semantics="SIGNED",
                    ),
                    "TIMING",
                    "Measurement interval exceeds verified maximum",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous_time is not None:
                check(
                    row.measured_at >= previous_time,
                    "TIMING",
                    "Measurement timestamp order invalid",
                    row.sequence_no,
                )
            previous_elapsed = row.elapsed_s
            previous_time = row.measured_at

        if rows:
            check(
                compare(
                    rows[-1].elapsed_s,
                    policy.minimum_duration_s,
                    operator=policy.duration_operator,
                    semantics="SIGNED",
                ),
                "TIMING",
                "Recorded span-stability duration is insufficient",
            )

        power_rows = [row for row in rows if row.power_disconnection_event]
        check(
            len(power_rows) >= policy.required_power_disconnections,
            "POWER",
            "Required power disconnection events missing",
            missing=True,
        )
        for row in power_rows:
            check(
                row.power_disconnection_duration_s is not None
                and row.power_disconnection_duration_s >= policy.minimum_power_disconnection_s,
                "POWER",
                "Power disconnection duration below verified minimum",
                row.sequence_no,
            )

        try:
            base_values = [
                _span_error(row, selected, policy.correction_mode)
                for row in rows
                if not row.extension_measurement
            ]
        except ValueError:
            base_values = []
            check(
                False,
                "ENVIRONMENT",
                "Span correction data incompatible with verified policy",
            )

        if _trend_requires_extension(policy, base_values):
            extension_count = sum(row.extension_measurement for row in rows)
            check(
                procedure_context.extension_completed
                and extension_count >= policy.minimum_extension_measurements,
                "TIMING",
                "Verified trend rule requires completed extension",
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
            SPAN_STABILITY_POLICY,
            "span_stability_procedure_v1",
            SpanStabilityPolicy,
        )
        refs = dependencies(
            ruleset,
            self.required_rules(),
        ).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        values = []
        calculations = []

        for row in observations.rows:
            value = _span_error(
                row,
                selected,
                policy.correction_mode,
            )
            values.append(value)
            calculations.append(
                CalculationTraceEntry(
                    name=(f"{row.measurement_no}:corrected_span_error"),
                    expression=(
                        "loaded_error - zero_error "
                        f"{policy.correction_mode.lower()} "
                        "influence_correction"
                    ),
                    value=value,
                    unit="g",
                    rule_references=refs,
                )
            )

        variation = exact(
            "subtract",
            max(values),
            min(values),
        )
        mpe = calculate_mpe(
            load_g=policy.test_load_g,
            selected_range=selected,
            accuracy_class=instrument_snapshot.accuracy_class,
            evaluation_context=procedure_context.evaluation_context,
            ruleset=ruleset,
            rule_id=SPAN_STABILITY_MPE,
        )
        e_component = exact(
            "multiply",
            selected.verification_interval_e_g,
            policy.e_multiplier,
        )
        mpe_component = exact(
            "multiply",
            mpe.value.copy_abs(),
            policy.mpe_multiplier,
        )
        limit_value = max(e_component, mpe_component)
        variation_limit = _limit(
            name="span_stability_variation",
            value=limit_value,
            operator=policy.variation_operator,
            semantics=policy.variation_semantics,
            refs=refs,
            unit="g",
        )
        calculations.append(
            CalculationTraceEntry(
                name="span_stability_variation",
                expression="max(corrected_span_error) - min(corrected_span_error)",
                value=variation,
                unit="g",
                rule_references=refs,
            )
        )
        failure = not compare(
            variation,
            variation_limit.value,
            operator=variation_limit.operator,
            semantics=variation_limit.semantics,
        )
        failures = (
            (
                FailedCondition(
                    code="SPAN_STABILITY_VARIATION_LIMIT_EXCEEDED",
                    reason=("Corrected span variation violates the verified acceptance limit"),
                    actual=variation,
                    limit=variation_limit,
                ),
            )
            if failure
            else ()
        )
        return EvaluationOutput(
            compliance_outcome=(
                ComplianceOutcome.NONCOMPLIANT if failure else ComplianceOutcome.COMPLIANT
            ),
            calculations=tuple(calculations),
            acceptance_limits=(variation_limit,),
            failed_conditions=failures,
            reasons=(
                "Complete span-stability procedure evaluated using pinned verified dependencies",
            ),
        )


def span_stability_registration():
    return EvaluatorRegistration(
        SPAN_STABILITY,
        SpanStabilityEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(
                    SPAN_STABILITY,
                    "LONG_DURATION",
                    "v1",
                    SpanStabilityContext,
                ),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    SPAN_STABILITY,
                    "SPAN_STABILITY_V1",
                    "v1",
                    SpanStabilityObservation,
                ),
            )
        ),
        implementation_version="section14-v1",
        policy_schemas=(
            RulePolicyRegistration(
                "applicability_policy_v1",
                ApplicabilityPolicy,
            ),
            RulePolicyRegistration(
                "span_stability_procedure_v1",
                SpanStabilityPolicy,
            ),
            RulePolicyRegistration(
                "mpe_profile_v1",
                MpeProfile,
            ),
        ),
    )
