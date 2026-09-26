"""Section 3 eccentricity mechanics driven only by verified rule configuration.

REG-06/REG-16 remain regulatory gates.  This module contains no default
positions, test loads, support-count rules, tolerances or acceptance thresholds.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.applicability import ApplicabilityEngine, ApplicabilityPolicy
from app.compliance.domain import (
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
)
from app.compliance.parameterized import (
    EccentricityPolicyV2,
    MpeProfileSetV2,
    PolicyResolutionError,
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

CODE = "ECCENTRICITY"
POLICY = "SECTION3_PROCEDURE"
MPE = "SECTION3_MPE"
CLASSIFICATION = "SECTION3_CLASSIFICATION"
CALIBRATION = "SECTION3_CALIBRATION"
GEOMETRY = "SECTION3_GEOMETRY"


class EccentricityPosition(Frozen):
    position_code: Text
    x_mm: Number | None = None
    y_mm: Number | None = None
    description: str | None = None


class EccentricityContext(RangeProcedureContext):
    test_code: Literal["ECCENTRICITY"] = CODE
    procedure_variant: Literal["WEIGHTS", "ROLLING_LOAD"]
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["ECCENTRICITY_V1"] = "ECCENTRICITY_V1"
    load_receptor_type: Text
    support_count: PositiveInt | None = None
    display_location: str | None = None
    positions: tuple[EccentricityPosition, ...] = Field(min_length=1)
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_sets(self):
        object.__setattr__(
            self, "positions", ordered_unique(self.positions, lambda p: p.position_code)
        )
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda e: e.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class EccentricityObservation(Observation):
    test_code: Literal["ECCENTRICITY"] = CODE
    protocol: Literal["ECCENTRICITY_V1"] = "ECCENTRICITY_V1"
    observation_schema_version: Literal["v1"] = "v1"
    position_code: Text
    rolling_direction: Literal["FORWARD", "REVERSE"] | None = None
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    measured_at: MeasurementTime


class PositionRequirement(Frozen):
    position_code: Text
    rolling_direction: Literal["FORWARD", "REVERSE"] | None = None


class EccentricityPolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    indication_type: Text
    range_type: Text
    procedure_variant: Literal["WEIGHTS", "ROLLING_LOAD"]
    test_load_g: Number = Field(ge=0)
    minimum_count: PositiveInt
    required_positions: tuple[PositionRequirement, ...] = Field(min_length=1)
    allowed_receptor_types: tuple[Text, ...] = Field(min_length=1)
    required_support_count: PositiveInt | None = None
    require_position_coordinates: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def unique_requirements(self):
        object.__setattr__(
            self,
            "required_positions",
            ordered_unique(
                self.required_positions,
                lambda p: p.position_code + "|" + (p.rolling_direction or ""),
            ),
        )
        if self.procedure_variant == "WEIGHTS" and any(
            item.rolling_direction is not None for item in self.required_positions
        ):
            raise ValueError("Weights policy cannot require a rolling direction")
        if self.procedure_variant == "ROLLING_LOAD" and any(
            item.rolling_direction is None for item in self.required_positions
        ):
            raise ValueError("Rolling-load policy must identify direction for every position")
        return self


class EccentricityPoint(CalculationTraceEntry):
    sequence_no: PositiveInt
    range_no: PositiveInt
    position_code: Text
    rolling_direction: Literal["FORWARD", "REVERSE"] | None
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


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code="MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE",
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


def _eccentricity_policy(*, instrument_snapshot, procedure_context, ruleset):
    kind, policy = rule_policy_variant(
        ruleset,
        POLICY,
        (
            ("eccentricity_procedure_v1", EccentricityPolicy),
            ("eccentricity_procedure_v2", EccentricityPolicyV2),
        ),
    )
    if kind == "eccentricity_procedure_v1":
        return policy

    from app.compliance.policy_adapters import adapt_eccentricity_policy

    try:
        return adapt_eccentricity_policy(
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
class EccentricityEvaluator:
    def required_rules(self, **kwargs):
        return POLICY, MPE, CLASSIFICATION, CALIBRATION, GEOMETRY

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
        policy = _eccentricity_policy(
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
                    _issue(refs, category, reason, sequence=sequence, missing=missing)
                )

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required position count missing",
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
            ctx.procedure_variant == policy.procedure_variant,
            "STAGE",
            "Eccentricity procedure variant differs from verified policy",
        )
        check(
            ctx.load_receptor_type in policy.allowed_receptor_types,
            "GEOMETRY",
            "Load receptor type not covered by verified policy",
        )
        if policy.required_support_count is not None:
            check(
                ctx.support_count == policy.required_support_count,
                "GEOMETRY",
                "Support-point count differs from verified policy",
            )
        if instrument_snapshot.load_receptor_type is not None:
            check(
                ctx.load_receptor_type == instrument_snapshot.load_receptor_type,
                "GEOMETRY",
                "Procedure receptor type differs from instrument snapshot",
            )
        if instrument_snapshot.support_point_count is not None:
            check(
                ctx.support_count == instrument_snapshot.support_point_count,
                "GEOMETRY",
                "Procedure support count differs from instrument snapshot",
            )
        positions = {p.position_code: p for p in ctx.positions}
        observed = {(r.position_code, r.rolling_direction) for r in rows}
        for requirement in policy.required_positions:
            check(
                (requirement.position_code, requirement.rolling_direction) in observed,
                "GEOMETRY",
                "Required eccentricity position/direction missing",
                missing=True,
            )
            check(
                requirement.position_code in positions,
                "GEOMETRY",
                "Required position is absent from the geometry snapshot",
                missing=True,
            )
        if policy.require_position_coordinates:
            for position in ctx.positions:
                check(
                    position.x_mm is not None and position.y_mm is not None,
                    "GEOMETRY",
                    "Verified procedure requires position coordinates",
                )
        previous_time = None
        for row in rows:
            check(
                row.position_code in positions,
                "GEOMETRY",
                "Observation uses undeclared position",
                row.sequence_no,
            )
            check(
                row.load_g == policy.test_load_g,
                "LOAD_COVERAGE",
                "Observation load differs from verified eccentricity load",
                row.sequence_no,
            )
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Load exceeds selected range",
                row.sequence_no,
            )
            if ctx.procedure_variant == "WEIGHTS":
                check(
                    row.rolling_direction is None,
                    "STAGE",
                    "Weights observation cannot declare rolling direction",
                    row.sequence_no,
                )
            else:
                check(
                    row.rolling_direction is not None,
                    "STAGE",
                    "Rolling-load observation requires direction",
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
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            prerounding = calculate_prerounding_indication(
                row.indication_g, selected.verification_interval_e_g, row.additional_load_g
            )
            error = calculate_error(prerounding, row.load_g)
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
                EccentricityPoint(
                    name=f"{row.sequence_no}:Ec",
                    expression="P=I+0.5e-deltaL; E=P-L; Ec=E-E0",
                    value=corrected,
                    unit="g",
                    rule_references=limit.rule_references,
                    sequence_no=row.sequence_no,
                    range_no=selected.range_no,
                    position_code=row.position_code,
                    rolling_direction=row.rolling_direction,
                    load_g=row.load_g,
                    indication_g=row.indication_g,
                    additional_load_g=row.additional_load_g,
                    prerounding_indication_g=prerounding,
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
                        code="ECCENTRICITY_LIMIT_EXCEEDED",
                        reason=f"Observation {row.sequence_no} violates the verified comparison",
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
                "Complete eccentricity procedure evaluated using pinned verified dependencies",
            ),
        )


def section3_registration():
    return EvaluatorRegistration(
        CODE,
        EccentricityEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(CODE, "WEIGHTS", "v1", EccentricityContext),
                ContextRegistration(CODE, "ROLLING_LOAD", "v1", EccentricityContext),
            )
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(CODE, "ECCENTRICITY_V1", "v1", EccentricityObservation),)
        ),
        implementation_version="section3-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
            RulePolicyRegistration("mpe_profile_set_v2", MpeProfileSetV2),
            RulePolicyRegistration("eccentricity_procedure_v1", EccentricityPolicy),
            RulePolicyRegistration("eccentricity_procedure_v2", EccentricityPolicyV2),
        ),
    )
