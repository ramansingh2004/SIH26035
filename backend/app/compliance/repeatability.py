"""Section 5 repeatability mechanics driven only by verified rule configuration.

REG-08/REG-16 remain regulatory gates.  Repetition counts, load series,
error basis and repeatability-range limits are never hard-coded here.
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
from app.compliance.parameterized import (
    MpeProfileSetV2,
    PolicyResolutionError,
    RepeatabilityPolicyV2,
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
from app.compliance.weighing import MeasurementTime, WeighingEnvironment, WeighingEquipment

CODE = "REPEATABILITY"
POLICY = "SECTION5_PROCEDURE"
MPE = "SECTION5_MPE"
CLASSIFICATION = "SECTION5_CLASSIFICATION"
CALIBRATION = "SECTION5_CALIBRATION"


class RepeatabilityContext(RangeProcedureContext):
    test_code: Literal["REPEATABILITY"] = CODE
    procedure_variant: Literal["DIGITAL_PRE_ROUNDING"] = "DIGITAL_PRE_ROUNDING"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["REPEATABILITY_V1"] = "REPEATABILITY_V1"
    stabilized: StrictBool | None = None
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_sets(self):
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda e: e.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class RepeatabilityObservation(Observation):
    test_code: Literal["REPEATABILITY"] = CODE
    protocol: Literal["REPEATABILITY_V1"] = "REPEATABILITY_V1"
    observation_schema_version: Literal["v1"] = "v1"
    series_code: Text
    repetition_no: PositiveInt
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    zero_reset_performed: StrictBool | None = None
    measured_at: MeasurementTime


class RepeatabilitySeriesPolicy(Frozen):
    series_code: Text
    load_g: Number = Field(ge=0)
    minimum_repetitions: PositiveInt
    range_limit_basis: Literal["MPE", "E"]
    range_limit_multiplier: Number = Field(ge=0)
    range_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    range_semantics: Literal["SIGNED", "ABSOLUTE"]


class RepeatabilityPolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    indication_type: Text
    range_type: Text
    error_basis: Literal["RAW", "CORRECTED"]
    series: tuple[RepeatabilitySeriesPolicy, ...] = Field(min_length=1)
    required_zero_reset: StrictBool | None = None
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def unique_series(self):
        object.__setattr__(self, "series", ordered_unique(self.series, lambda s: s.series_code))
        return self


class RepeatabilityPoint(CalculationTraceEntry):
    sequence_no: PositiveInt
    range_no: PositiveInt
    series_code: Text
    repetition_no: PositiveInt
    load_g: Number
    indication_g: Number
    additional_load_g: Number
    prerounding_indication_g: Number
    error_g: Number
    zero_error_g: Number
    corrected_error_g: Number
    selected_error_g: Number
    mpe_g: Number
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]
    compliance_outcome: Literal[ComplianceOutcome.COMPLIANT, ComplianceOutcome.NONCOMPLIANT]


class RepeatabilitySeriesResult(CalculationTraceEntry):
    series_code: Text
    repetition_count: PositiveInt
    minimum_error_g: Number
    maximum_error_g: Number
    repeatability_range_g: Number
    allowed_range_g: Number
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]
    compliance_outcome: Literal[ComplianceOutcome.COMPLIANT, ComplianceOutcome.NONCOMPLIANT]


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code="MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE",
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


def _repeatability_policy(*, instrument_snapshot, procedure_context, ruleset):
    kind, policy = rule_policy_variant(
        ruleset,
        POLICY,
        (
            ("repeatability_procedure_v1", RepeatabilityPolicy),
            ("repeatability_procedure_v2", RepeatabilityPolicyV2),
        ),
    )
    if kind == "repeatability_procedure_v1":
        return policy

    from app.compliance.policy_adapters import adapt_repeatability_policy

    try:
        return adapt_repeatability_policy(
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
class RepeatabilityEvaluator:
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
        policy = _repeatability_policy(
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
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

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
        policy_by_series = {s.series_code: s for s in policy.series}
        observed_series = {r.series_code for r in rows}
        check(
            observed_series <= policy_by_series.keys(),
            "STAGE",
            "Observation contains a series not present in verified policy",
        )
        previous_time = None
        for series in policy.series:
            group = [r for r in rows if r.series_code == series.series_code]
            check(
                len(group) >= series.minimum_repetitions,
                "COUNT",
                f"Repeatability series {series.series_code} has too few repetitions",
                missing=True,
            )
            numbers = [r.repetition_no for r in group]
            check(
                len(numbers) == len(set(numbers)),
                "COUNT",
                f"Repeatability series {series.series_code} repeats a repetition number",
            )
            for row in group:
                check(
                    row.load_g == series.load_g,
                    "LOAD_COVERAGE",
                    "Observation load differs from verified repeatability series load",
                    row.sequence_no,
                )
        for row in rows:
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Load exceeds selected range",
                row.sequence_no,
            )
            if policy.required_zero_reset is not None:
                check(
                    row.zero_reset_performed is policy.required_zero_reset,
                    "STAGE",
                    "Zero-reset behavior differs from verified procedure",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous_time is not None:
                check(
                    row.measured_at >= previous_time,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous_time = row.measured_at
        check(
            not policy.require_stabilization or ctx.stabilized is True,
            "STABILIZATION",
            "Stabilization not confirmed",
        )
        check(
            not policy.require_environment or bool(ctx.environment),
            "ENVIRONMENT",
            "Environment missing",
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
            not policy.require_evidence or bool(ctx.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = _repeatability_policy(
            instrument_snapshot=instrument_snapshot,
            procedure_context=procedure_context,
            ruleset=ruleset,
        )
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations, limits, failures = [], [], []
        values_by_series: dict[str, list] = {s.series_code: [] for s in policy.series}

        for row in observations.rows:
            prerounding = calculate_prerounding_indication(
                row.indication_g, selected.verification_interval_e_g, row.additional_load_g
            )
            error = calculate_error(prerounding, row.load_g)
            corrected = calculate_corrected_error(error, row.zero_error_g)
            selected_error = error if policy.error_basis == "RAW" else corrected
            limit = calculate_mpe_compatible(
                load_g=row.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=MPE,
            )
            conforming = compare(
                selected_error,
                limit.value,
                operator=limit.operator,
                semantics=limit.semantics,
            )
            outcome = ComplianceOutcome.COMPLIANT if conforming else ComplianceOutcome.NONCOMPLIANT
            calculations.append(
                RepeatabilityPoint(
                    name=f"{row.sequence_no}:repeatability_error",
                    expression="P=I+0.5e-deltaL; E=P-L; selected=E or Ec from verified policy",
                    value=selected_error,
                    unit="g",
                    rule_references=limit.rule_references,
                    sequence_no=row.sequence_no,
                    range_no=selected.range_no,
                    series_code=row.series_code,
                    repetition_no=row.repetition_no,
                    load_g=row.load_g,
                    indication_g=row.indication_g,
                    additional_load_g=row.additional_load_g,
                    prerounding_indication_g=prerounding,
                    error_g=error,
                    zero_error_g=row.zero_error_g,
                    corrected_error_g=corrected,
                    selected_error_g=selected_error,
                    mpe_g=limit.value,
                    operator=limit.operator,
                    semantics=limit.semantics,
                    compliance_outcome=outcome,
                )
            )
            limits.append(limit)
            values_by_series[row.series_code].append(selected_error)
            if not conforming:
                failures.append(
                    FailedCondition(
                        code="REPEATABILITY_INDIVIDUAL_LIMIT_EXCEEDED",
                        reason=(
                            f"Observation {row.sequence_no} violates the verified individual limit"
                        ),
                        actual=selected_error,
                        limit=limit,
                    )
                )

        policy_by_series = {s.series_code: s for s in policy.series}
        refs = dependencies(ruleset, (POLICY, MPE)).rule_references
        for series_code, values in values_by_series.items():
            series = policy_by_series[series_code]
            minimum, maximum = min(values), max(values)
            spread = exact("subtract", maximum, minimum)
            if series.range_limit_basis == "MPE":
                basis = calculate_mpe_compatible(
                    load_g=series.load_g,
                    selected_range=selected,
                    accuracy_class=instrument_snapshot.accuracy_class,
                    evaluation_context=procedure_context.evaluation_context,
                    ruleset=ruleset,
                    rule_id=MPE,
                ).value
            else:
                basis = selected.verification_interval_e_g
            allowed = exact("multiply", basis, series.range_limit_multiplier)
            range_limit = AcceptanceLimit(
                name=f"repeatability_range:{series_code}",
                value=allowed,
                unit="g",
                operator=series.range_operator,
                semantics=series.range_semantics,
                rule_references=refs,
            )
            conforming = compare(
                spread,
                allowed,
                operator=series.range_operator,
                semantics=series.range_semantics,
            )
            outcome = ComplianceOutcome.COMPLIANT if conforming else ComplianceOutcome.NONCOMPLIANT
            calculations.append(
                RepeatabilitySeriesResult(
                    name=f"series:{series_code}:range",
                    expression="max(selected_error)-min(selected_error)",
                    value=spread,
                    unit="g",
                    rule_references=refs,
                    series_code=series_code,
                    repetition_count=len(values),
                    minimum_error_g=minimum,
                    maximum_error_g=maximum,
                    repeatability_range_g=spread,
                    allowed_range_g=allowed,
                    operator=series.range_operator,
                    semantics=series.range_semantics,
                    compliance_outcome=outcome,
                )
            )
            limits.append(range_limit)
            if not conforming:
                failures.append(
                    FailedCondition(
                        code="REPEATABILITY_RANGE_LIMIT_EXCEEDED",
                        reason=f"Series {series_code} exceeds the verified repeatability range",
                        actual=spread,
                        limit=range_limit,
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
                "Complete repeatability procedure evaluated using pinned verified dependencies",
            ),
        )


def section5_registration():
    return EvaluatorRegistration(
        CODE,
        RepeatabilityEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(CODE, "DIGITAL_PRE_ROUNDING", "v1", RepeatabilityContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(CODE, "REPEATABILITY_V1", "v1", RepeatabilityObservation),)
        ),
        implementation_version="section5-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
            RulePolicyRegistration("mpe_profile_set_v2", MpeProfileSetV2),
            RulePolicyRegistration("repeatability_procedure_v1", RepeatabilityPolicy),
            RulePolicyRegistration("repeatability_procedure_v2", RepeatabilityPolicyV2),
        ),
    )
