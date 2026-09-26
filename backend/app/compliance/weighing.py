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
)
from app.compliance.parameterized import (
    MpeProfileSetV2,
    PolicyResolutionError,
    WeighingPolicyV2,
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

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
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
                        code="MISSING_REQUIRED_OBSERVATIONS"
                        if missing
                        else "EVALUATION_NOT_POSSIBLE",
                        category=category,
                        reason=reason,
                        sequence_no=sequence,
                        rule_references=refs,
                    )
                )

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required observation count missing",
            missing=True,
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
            ctx.stages == policy.stages, "STAGE", "Declared stages differ from verified procedure"
        )
        observed_stages = tuple(
            r.direction
            for i, r in enumerate(rows)
            if i == 0 or rows[i - 1].direction != r.direction
        )
        check(observed_stages == policy.stages, "ORDER", "Loading/unloading stage order incomplete")
        coverage = {(r.direction, r.load_g) for r in rows}
        for point in policy.required_loads + policy.transition_loads:
            check(
                (point.direction, point.load_g) in coverage,
                "LOAD_COVERAGE",
                "Required load/transition missing",
                missing=True,
            )
        for direction in policy.stages:
            if policy.require_max:
                check(
                    (direction, selected.max_capacity_g) in coverage,
                    "LOAD_COVERAGE",
                    "Max coverage missing",
                    missing=True,
                )
            if policy.require_min:
                check(
                    selected.min_capacity_g is not None
                    and (direction, selected.min_capacity_g) in coverage,
                    "LOAD_COVERAGE",
                    "Min coverage missing",
                    missing=True,
                )
        for previous, row in zip(rows, rows[1:], strict=False):
            if previous.direction == row.direction:
                check(
                    row.load_g >= previous.load_g
                    if row.direction == "UP"
                    else row.load_g <= previous.load_g,
                    "ORDER",
                    "Load order invalid",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps:
                check(
                    row.measured_at >= previous.measured_at,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
        for row in rows:
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Load exceeds selected range",
                row.sequence_no,
            )
        check(
            not policy.require_preload or ctx.preloaded is True, "STAGE", "Preloading not confirmed"
        )
        check(
            not policy.require_stabilization or ctx.stabilized is True,
            "STABILIZATION",
            "Stabilization not confirmed",
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
                (environment.temperature_c, policy.temperature_min_c, policy.temperature_max_c),
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
        check(not policy.require_equipment or bool(ctx.equipment), "EQUIPMENT", "Equipment missing")
        if policy.require_certificate:
            check(
                bool(ctx.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in ctx.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(ctx.evidence_hashes), "EVIDENCE", "Evidence missing"
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
            (ContextRegistration(CODE, "DIGITAL_PRE_ROUNDING", "v1", WeighingContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(CODE, "WEIGHING_V1", "v1", WeighingObservation),)
        ),
        implementation_version="section1-v1",
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
