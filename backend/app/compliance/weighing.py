"""Section 1 mechanics. All acceptance/procedure policy comes from verified rules.

No default regulatory policy is supplied. Candidate data cannot reach calculation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BeforeValidator, Field, StrictBool, model_validator

from app.compliance.applicability import ApplicabilityEngine, ApplicabilityPolicy
from app.compliance.domain import (
    CalculationTraceEntry,
    ComplianceOutcome,
    Digest,
    EnvironmentSnapshot,
    EquipmentCalibrationSnapshot,
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
from app.compliance.evaluators import (
    EvaluatorRegistration,
    EvaluatorRegistry,
    RulePolicyRegistration,
)
from app.compliance.numbers import (
    calculate_corrected_error,
    calculate_error,
    calculate_prerounding_indication,
    compare,
    exact,
)
from app.compliance.parameterized import (
    MpeProfileSetV2,
    PolicyResolutionError,
    WeighingPolicyV2,
    resolve_policy_case,
    resolve_static_temperature_stages,
)
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import (
    DependencyResolution,
    MpeProfile,
    RegulatoryBlocked,
    calculate_mpe_compatible,
    compatible_mpe_profile,
    dependencies,
    rule_policy_variant,
)

CODE = "WEIGHING_PERFORMANCE"
POLICY = "SECTION1_PROCEDURE"
MPE = "SECTION1_MPE"
CLASSIFICATION = "SECTION1_CLASSIFICATION"
CALIBRATION = "SECTION1_CALIBRATION"


def measurement_time(value):
    if not isinstance(value, (str, datetime)) or isinstance(value, str) and "T" not in value:
        raise ValueError("Measurement time requires an aware datetime or ISO timestamp string")
    return value


MeasurementTime = Annotated[AwareDatetime, BeforeValidator(measurement_time)]


class WeighingEquipment(EquipmentCalibrationSnapshot):
    nominal_mass_g: Number | None = Field(None, gt=0)
    certificate_content_hash: Digest | None = None


class WeighingEnvironment(EnvironmentSnapshot):
    measured_at: MeasurementTime
    phase: str | None = None


class WeighingContext(RangeProcedureContext):
    test_code: Literal["WEIGHING_PERFORMANCE"] = CODE
    procedure_variant: Literal["DIGITAL_PRE_ROUNDING"] = "DIGITAL_PRE_ROUNDING"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["WEIGHING_V1"] = "WEIGHING_V1"
    stages: tuple[Literal["UP", "DOWN"], ...]
    preloaded: StrictBool | None = None
    warmed_up_seconds: Number | None = Field(None, ge=0)
    stabilized: StrictBool | None = None
    zero_condition: str | None = None
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def semantic_order(self):
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda x: x.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class WeighingObservation(Observation):
    test_code: Literal["WEIGHING_PERFORMANCE"] = CODE
    protocol: Literal["WEIGHING_V1"] = "WEIGHING_V1"
    observation_schema_version: Literal["v1"] = "v1"
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    direction: Literal["UP", "DOWN"]
    measured_at: MeasurementTime


class WeighingContextV2(WeighingContext):
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["WEIGHING_V2"] = "WEIGHING_V2"


class StaticTemperatureStageRecord(Frozen):
    stage_code: Text
    target_temperature_c: Number
    temperature_stability_reached_at: MeasurementTime
    weighing_started_at: MeasurementTime
    weighing_completed_at: MeasurementTime
    preloaded: StrictBool | None = None
    weighing_stabilized: StrictBool | None = None
    free_air_conditions: StrictBool | None = None
    absolute_humidity_g_m3: Number | None = Field(None, ge=0)
    barometric_pressure_accounted: StrictBool | None = None

    @model_validator(mode="after")
    def chronology(self):
        if not (
            self.temperature_stability_reached_at
            <= self.weighing_started_at
            <= self.weighing_completed_at
        ):
            raise ValueError("Static-temperature stage timestamps are out of order")
        return self


class StaticTemperatureWeighingContext(WeighingContextV2):
    procedure_variant: Literal["STATIC_TEMPERATURE"] = "STATIC_TEMPERATURE"
    protocol: Literal["WEIGHING_STATIC_TEMPERATURE_V2"] = (
        "WEIGHING_STATIC_TEMPERATURE_V2"
    )
    temperature_stages: tuple[StaticTemperatureStageRecord, ...] = ()


class WeighingObservationV2(WeighingObservation):
    protocol: Literal["WEIGHING_V2"] = "WEIGHING_V2"
    observation_schema_version: Literal["v2"] = "v2"


class StaticTemperatureWeighingObservation(WeighingObservationV2):
    protocol: Literal["WEIGHING_STATIC_TEMPERATURE_V2"] = (
        "WEIGHING_STATIC_TEMPERATURE_V2"
    )
    temperature_stage: Text


def initial_weighing_context(
    *,
    range_no: int,
    scenario: str,
    evaluation_context: str,
    procedure_variant: str,
    procedure_schema_version: str,
):
    common = dict(
        range_no=range_no,
        scenario=scenario,
        evaluation_context=evaluation_context,
        stages=(),
    )
    if procedure_schema_version == "v1" and procedure_variant == "DIGITAL_PRE_ROUNDING":
        return WeighingContext(**common)
    if procedure_schema_version == "v2" and procedure_variant == "DIGITAL_PRE_ROUNDING":
        return WeighingContextV2(**common)
    if procedure_schema_version == "v2" and procedure_variant == "STATIC_TEMPERATURE":
        return StaticTemperatureWeighingContext(**common)
    raise ValueError("Unsupported Section 1 procedure variant/schema selection")


class CoveragePoint(Frozen):
    direction: Literal["UP", "DOWN"]
    load_g: Number = Field(ge=0)


class WeighingPolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    indication_type: Text
    range_type: Text
    interval_basis: Literal["e"]
    minimum_count: PositiveInt
    stages: tuple[Literal["UP", "DOWN"], ...] = Field(min_length=1)
    required_loads: tuple[CoveragePoint, ...]
    transition_loads: tuple[CoveragePoint, ...]
    require_min: StrictBool
    require_max: StrictBool
    require_preload: StrictBool
    require_stabilization: StrictBool
    minimum_warmup_seconds: Number = Field(ge=0)
    zero_condition: Text
    require_environment: StrictBool
    temperature_min_c: Number | None
    temperature_max_c: Number | None
    humidity_min_percent: Number | None = Field(ge=0, le=100)
    humidity_max_percent: Number | None = Field(ge=0, le=100)
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def bounds(self):
        for lower, upper in (
            (self.temperature_min_c, self.temperature_max_c),
            (self.humidity_min_percent, self.humidity_max_percent),
        ):
            if (lower is None) != (upper is None) or (lower is not None and lower > upper):
                raise ValueError("Policy bounds must be explicit paired ordered bounds")
        return self


class WeighingPoint(CalculationTraceEntry):
    sequence_no: PositiveInt
    range_no: PositiveInt
    direction: Literal["UP", "DOWN"]
    load_g: Number
    indication_g: Number
    additional_load_g: Number
    prerounding_indication_g: Number
    error_g: Number
    zero_error_g: Number
    corrected_error_g: Number
    mpe_g: Number
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]
    compliance_outcome: Literal[ComplianceOutcome.COMPLIANT, ComplianceOutcome.NONCOMPLIANT]


def _weighing_policy(*, instrument_snapshot, procedure_context, ruleset):
    kind, policy = rule_policy_variant(
        ruleset,
        POLICY,
        (
            ("weighing_procedure_v1", WeighingPolicy),
            ("weighing_procedure_v2", WeighingPolicyV2),
        ),
    )
    if kind == "weighing_procedure_v1":
        return policy

    from app.compliance.policy_adapters import adapt_weighing_policy

    try:
        return adapt_weighing_policy(
            policy,
            instrument=instrument_snapshot,
            evaluation_context=procedure_context.evaluation_context,
            range_no=procedure_context.range_no,
        )
    except PolicyResolutionError as exc:
        raise RegulatoryBlocked(
            DependencyResolution(
                unresolved_rule_ids=(POLICY,),
                rule_references=dependencies(ruleset, (POLICY,)).rule_references,
            )
        ) from exc


def _static_temperature_policy(*, instrument_snapshot, procedure_context, ruleset):
    kind, policy = rule_policy_variant(
        ruleset,
        POLICY,
        (
            ("weighing_procedure_v1", WeighingPolicy),
            ("weighing_procedure_v2", WeighingPolicyV2),
        ),
    )
    if kind != "weighing_procedure_v2":
        raise RegulatoryBlocked(
            DependencyResolution(
                unresolved_rule_ids=(POLICY,),
                rule_references=dependencies(ruleset, (POLICY,)).rule_references,
            )
        )
    try:
        case = resolve_policy_case(
            policy.cases,
            instrument_snapshot,
            procedure_context.evaluation_context,
        )
        if case.static_temperature is None:
            raise PolicyResolutionError(
                "Verified Section 1 policy does not define static-temperature coverage"
            )
        if (
            instrument_snapshot.declared_temp_min_c is None
            or instrument_snapshot.declared_temp_max_c is None
        ):
            raise PolicyResolutionError(
                "Declared temperature bounds are required for static-temperature coverage"
            )
        return (
            case.static_temperature,
            resolve_static_temperature_stages(
                case.static_temperature,
                instrument_snapshot,
            ),
        )
    except PolicyResolutionError as exc:
        raise RegulatoryBlocked(
            DependencyResolution(
                unresolved_rule_ids=(POLICY,),
                rule_references=dependencies(ruleset, (POLICY,)).rule_references,
            )
        ) from exc


def _elapsed_seconds(later: datetime, earlier: datetime):
    delta = later - earlier
    microseconds = (
        (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    )
    return exact("multiply", str(microseconds), "0.000001")


def _rate_within(
    *,
    earlier_temperature,
    later_temperature,
    elapsed_seconds,
    limit,
    seconds_per_limit_unit,
):
    if elapsed_seconds <= 0:
        return False
    delta = exact("subtract", later_temperature, earlier_temperature).copy_abs()
    return exact("multiply", delta, seconds_per_limit_unit) <= exact(
        "multiply", limit, elapsed_seconds
    )


@dataclass(frozen=True)
class WeighingEvaluator:
    def required_rules(self, **kwargs):
        return POLICY, MPE, CLASSIFICATION, CALIBRATION

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=CODE,
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
        policy = _weighing_policy(
            instrument_snapshot=instrument_snapshot,
            procedure_context=procedure_context,
            ruleset=ruleset,
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        ctx, rows = procedure_context, observations.rows
        selected = instrument_snapshot.select_range(ctx.range_no)
        compatible_mpe_profile(
            accuracy_class=instrument_snapshot.accuracy_class,
            evaluation_context=ctx.evaluation_context,
            ruleset=ruleset,
            rule_id=MPE,
        )
        issues = []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(
                    ProcedureValidationIssue(
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
                )

        def validate_load_cycle(cycle_rows, *, label):
            check(
                len(cycle_rows) >= policy.minimum_count,
                "COUNT",
                f"Required observation count missing for {label}",
                missing=True,
            )
            observed_stages = tuple(
                row.direction
                for index, row in enumerate(cycle_rows)
                if index == 0 or cycle_rows[index - 1].direction != row.direction
            )
            check(
                observed_stages == policy.stages,
                "ORDER",
                f"Loading/unloading stage order incomplete for {label}",
            )
            coverage = {(row.direction, row.load_g) for row in cycle_rows}
            for point in policy.required_loads + policy.transition_loads:
                check(
                    (point.direction, point.load_g) in coverage,
                    "LOAD_COVERAGE",
                    f"Required load/transition missing for {label}",
                    missing=True,
                )
            for direction in policy.stages:
                if policy.require_max:
                    check(
                        (direction, selected.max_capacity_g) in coverage,
                        "LOAD_COVERAGE",
                        f"Max coverage missing for {label}",
                        missing=True,
                    )
                if policy.require_min:
                    check(
                        selected.min_capacity_g is not None
                        and (direction, selected.min_capacity_g) in coverage,
                        "LOAD_COVERAGE",
                        f"Min coverage missing for {label}",
                        missing=True,
                    )
            for previous, row in zip(cycle_rows, cycle_rows[1:], strict=False):
                if previous.direction == row.direction:
                    check(
                        (
                            row.load_g >= previous.load_g
                            if row.direction == "UP"
                            else row.load_g <= previous.load_g
                        ),
                        "ORDER",
                        f"Load order invalid for {label}",
                        row.sequence_no,
                    )
                if policy.require_monotonic_timestamps:
                    check(
                        row.measured_at >= previous.measured_at,
                        "TIMING",
                        f"Measurement time order invalid for {label}",
                        row.sequence_no,
                    )
            for row in cycle_rows:
                check(
                    row.load_g <= selected.max_capacity_g,
                    "RANGE",
                    "Load exceeds selected range",
                    row.sequence_no,
                )

        check(
            ctx.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        check(
            instrument_snapshot.indication_type == policy.indication_type
            and instrument_snapshot.range_type == policy.range_type,
            "RANGE",
            "Indication/range classification not covered",
        )
        check(
            ctx.stages == policy.stages,
            "STAGE",
            "Declared stages differ from verified procedure",
        )
        check(
            ctx.warmed_up_seconds is not None
            and ctx.warmed_up_seconds >= policy.minimum_warmup_seconds,
            "TIMING",
            "Warm-up requirement not met",
        )
        check(ctx.zero_condition == policy.zero_condition, "STAGE", "Zero condition incompatible")
        check(
            not policy.require_environment or bool(ctx.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        for environment in ctx.environment:
            for value, lower, upper in (
                (
                    environment.temperature_c,
                    policy.temperature_min_c,
                    policy.temperature_max_c,
                ),
                (
                    environment.relative_humidity_percent,
                    policy.humidity_min_percent,
                    policy.humidity_max_percent,
                ),
            ):
                if lower is not None:
                    check(
                        value is not None and lower <= value <= upper,
                        "ENVIRONMENT",
                        "Environment outside verified bounds",
                    )
        check(
            not policy.require_equipment or bool(ctx.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(ctx.equipment)
                and all(
                    item.calibration_certificate_no and item.certificate_content_hash
                    for item in ctx.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(ctx.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )

        if isinstance(ctx, StaticTemperatureWeighingContext):
            static_policy, resolved_stages = _static_temperature_policy(
                instrument_snapshot=instrument_snapshot,
                procedure_context=ctx,
                ruleset=ruleset,
            )
            expected_codes = tuple(item.stage_code for item in resolved_stages)
            stage_records = {item.stage_code: item for item in ctx.temperature_stages}
            check(
                tuple(item.stage_code for item in ctx.temperature_stages) == expected_codes,
                "STAGE",
                "Static-temperature stage sequence incomplete or out of order",
                missing=True,
            )
            observed_codes = tuple(
                row.temperature_stage
                for index, row in enumerate(rows)
                if index == 0
                or rows[index - 1].temperature_stage != row.temperature_stage
            )
            check(
                observed_codes == expected_codes,
                "ORDER",
                "Static-temperature observation sequence incomplete or out of order",
                missing=True,
            )

            if policy.require_monotonic_timestamps:
                for previous, row in zip(rows, rows[1:], strict=False):
                    check(
                        row.measured_at >= previous.measured_at,
                        "TIMING",
                        "Measurement time order invalid across temperature stages",
                        row.sequence_no,
                    )

            declared_span = exact(
                "subtract",
                instrument_snapshot.declared_temp_max_c,
                instrument_snapshot.declared_temp_min_c,
            )
            steady_span_limit = min(
                exact(
                    "multiply",
                    declared_span,
                    static_policy.steady_temperature_span_fraction,
                ),
                static_policy.steady_temperature_span_cap_c,
            )

            resolved_by_code = {item.stage_code: item for item in resolved_stages}
            for code in expected_codes:
                record = stage_records.get(code)
                stage_rows = tuple(row for row in rows if row.temperature_stage == code)
                check(
                    bool(stage_rows),
                    "COUNT",
                    f"No weighing observations for {code}",
                    missing=True,
                )
                if stage_rows:
                    validate_load_cycle(stage_rows, label=code)
                if record is None:
                    continue
                check(
                    record.target_temperature_c == resolved_by_code[code].temperature_c,
                    "ENVIRONMENT",
                    f"Target temperature does not match verified policy for {code}",
                )
                check(
                    _elapsed_seconds(
                        record.weighing_started_at,
                        record.temperature_stability_reached_at,
                    )
                    >= static_policy.minimum_exposure_after_stability_seconds,
                    "TIMING",
                    f"Required post-stability exposure not met for {code}",
                )
                check(
                    not policy.require_preload or record.preloaded is True,
                    "STAGE",
                    f"Preloading not confirmed for {code}",
                )
                check(
                    not policy.require_stabilization or record.weighing_stabilized is True,
                    "STABILIZATION",
                    f"Weighing stabilization not confirmed for {code}",
                )
                check(
                    not static_policy.require_free_air_conditions
                    or record.free_air_conditions is True,
                    "ENVIRONMENT",
                    f"Free-air conditions not confirmed for {code}",
                )
                if code == static_policy.high_temperature_stage_code:
                    check(
                        record.absolute_humidity_g_m3 is not None
                        and record.absolute_humidity_g_m3
                        <= static_policy.maximum_high_temperature_absolute_humidity_g_m3,
                        "ENVIRONMENT",
                        "High-temperature absolute humidity exceeds verified limit",
                    )
                if (
                    static_policy.require_class_i_barometric_pressure_accounting
                    and instrument_snapshot.accuracy_class == "I"
                ):
                    check(
                        record.barometric_pressure_accounted is True,
                        "ENVIRONMENT",
                        f"Barometric-pressure accounting not confirmed for {code}",
                    )

                for row in stage_rows:
                    check(
                        record.weighing_started_at
                        <= row.measured_at
                        <= record.weighing_completed_at,
                        "TIMING",
                        f"Observation lies outside the declared weighing window for {code}",
                        row.sequence_no,
                    )

                stage_environment = tuple(
                    sorted(
                        (
                            item
                            for item in ctx.environment
                            if item.phase == code
                            and item.temperature_c is not None
                            and record.temperature_stability_reached_at
                            <= item.measured_at
                            <= record.weighing_completed_at
                        ),
                        key=lambda item: item.measured_at,
                    )
                )
                if policy.require_environment:
                    check(
                        len(stage_environment) >= 2,
                        "ENVIRONMENT",
                        f"At least two traceable temperature readings are required for {code}",
                        missing=True,
                    )
                if stage_environment:
                    temperatures = [item.temperature_c for item in stage_environment]
                    check(
                        exact("subtract", max(temperatures), min(temperatures))
                        <= steady_span_limit,
                        "ENVIRONMENT",
                        f"Temperature was not steady for {code}",
                    )
                    for previous, current in zip(
                        stage_environment, stage_environment[1:], strict=False
                    ):
                        seconds = _elapsed_seconds(current.measured_at, previous.measured_at)
                        check(
                            _rate_within(
                                earlier_temperature=previous.temperature_c,
                                later_temperature=current.temperature_c,
                                elapsed_seconds=seconds,
                                limit=static_policy.steady_temperature_max_rate_c_per_hour,
                                seconds_per_limit_unit="3600",
                            ),
                            "ENVIRONMENT",
                            f"Steady-temperature rate exceeded for {code}",
                        )
                    if (
                        static_policy.require_class_i_barometric_pressure_accounting
                        and instrument_snapshot.accuracy_class == "I"
                    ):
                        check(
                            all(item.pressure_hpa is not None for item in stage_environment),
                            "ENVIRONMENT",
                            f"Barometric-pressure readings missing for {code}",
                            missing=True,
                        )

            records = list(ctx.temperature_stages)
            for previous, current in zip(records, records[1:], strict=False):
                check(
                    previous.weighing_completed_at
                    <= current.temperature_stability_reached_at,
                    "TIMING",
                    "Static-temperature stage chronology overlaps",
                )

            temperature_environment = sorted(
                (item for item in ctx.environment if item.temperature_c is not None),
                key=lambda item: item.measured_at,
            )
            for previous, current in zip(
                temperature_environment, temperature_environment[1:], strict=False
            ):
                seconds = _elapsed_seconds(current.measured_at, previous.measured_at)
                check(
                    _rate_within(
                        earlier_temperature=previous.temperature_c,
                        later_temperature=current.temperature_c,
                        elapsed_seconds=seconds,
                        limit=static_policy.maximum_transition_rate_c_per_minute,
                        seconds_per_limit_unit="60",
                    ),
                    "ENVIRONMENT",
                    "Temperature transition rate exceeded verified policy",
                )
        else:
            validate_load_cycle(rows, label="weighing procedure")
            check(
                not policy.require_preload or ctx.preloaded is True,
                "STAGE",
                "Preloading not confirmed",
            )
            check(
                not policy.require_stabilization or ctx.stabilized is True,
                "STABILIZATION",
                "Stabilization not confirmed",
            )

        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            p = calculate_prerounding_indication(
                row.indication_g, selected.verification_interval_e_g, row.additional_load_g
            )
            error = calculate_error(p, row.load_g)
            corrected = calculate_corrected_error(error, row.zero_error_g)
            limit = calculate_mpe_compatible(
                load_g=row.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=MPE,
            )
            conforming = compare(
                corrected, limit.value, operator=limit.operator, semantics=limit.semantics
            )
            outcome = ComplianceOutcome.COMPLIANT if conforming else ComplianceOutcome.NONCOMPLIANT
            calculations.append(
                WeighingPoint(
                    name=f"{row.sequence_no}:Ec",
                    expression="P=I+0.5e-deltaL; E=P-L; Ec=E-E0",
                    value=corrected,
                    unit="g",
                    rule_references=limit.rule_references,
                    sequence_no=row.sequence_no,
                    range_no=selected.range_no,
                    direction=row.direction,
                    load_g=row.load_g,
                    indication_g=row.indication_g,
                    additional_load_g=row.additional_load_g,
                    prerounding_indication_g=p,
                    error_g=error,
                    zero_error_g=row.zero_error_g,
                    corrected_error_g=corrected,
                    mpe_g=limit.value,
                    operator=limit.operator,
                    semantics=limit.semantics,
                    compliance_outcome=outcome,
                )
            )
            limits.append(limit)
            if not conforming:
                failures.append(
                    FailedCondition(
                        code="WEIGHING_LIMIT_EXCEEDED",
                        reason=f"Observation {row.sequence_no} violates the verified comparison",
                        actual=corrected,
                        limit=limit,
                    )
                )
        return EvaluationOutput(
            compliance_outcome=ComplianceOutcome.NONCOMPLIANT
            if failures
            else ComplianceOutcome.COMPLIANT,
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=("Complete procedure evaluated using pinned verified dependencies",),
        )


def section1_registration():
    return EvaluatorRegistration(
        CODE,
        WeighingEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(CODE, "DIGITAL_PRE_ROUNDING", "v1", WeighingContext),
                ContextRegistration(CODE, "DIGITAL_PRE_ROUNDING", "v2", WeighingContextV2),
                ContextRegistration(
                    CODE,
                    "STATIC_TEMPERATURE",
                    "v2",
                    StaticTemperatureWeighingContext,
                ),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(CODE, "WEIGHING_V1", "v1", WeighingObservation),
                ObservationRegistration(CODE, "WEIGHING_V2", "v2", WeighingObservationV2),
                ObservationRegistration(
                    CODE,
                    "WEIGHING_STATIC_TEMPERATURE_V2",
                    "v2",
                    StaticTemperatureWeighingObservation,
                ),
            )
        ),
        implementation_version="section1-v2",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
            RulePolicyRegistration("mpe_profile_set_v2", MpeProfileSetV2),
            RulePolicyRegistration("weighing_procedure_v1", WeighingPolicy),
            RulePolicyRegistration("weighing_procedure_v2", WeighingPolicyV2),
        ),
    )


def section1_registry():
    return EvaluatorRegistry((section1_registration(),))
