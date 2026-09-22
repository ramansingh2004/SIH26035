"""Phase 7 functional/time evaluator mechanics.

REG-07, REG-09, REG-10 and REG-16 remain regulatory gates.  This module
contains typed procedure/observation contracts and deterministic mechanics,
but no hard-coded OIML thresholds.  Acceptance values are supplied only by a
verified/synthetic pinned RuleSet policy.
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
from app.compliance.numbers import compare, exact
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import dependencies, rule_policy
from app.compliance.weighing import MeasurementTime, WeighingEnvironment, WeighingEquipment


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code="MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE",
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
    stabilized: StrictBool | None = None
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_evidence(self):
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda e: e.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class CommonProcedurePolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    minimum_count: PositiveInt
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


# ---------------------------------------------------------------------------
# Section 4.1 — discrimination
# ---------------------------------------------------------------------------

DISCRIMINATION = "DISCRIMINATION"
DISCRIMINATION_POLICY = "SECTION4_DISCRIMINATION_PROCEDURE"
DISCRIMINATION_CLASSIFICATION = "SECTION4_CLASSIFICATION"
DISCRIMINATION_CALIBRATION = "SECTION4_CALIBRATION"


class DiscriminationContext(_EvidenceContext):
    test_code: Literal["DISCRIMINATION"] = DISCRIMINATION
    procedure_variant: Literal["DIGITAL", "ANALOG"]
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["DISCRIMINATION_V1"] = "DISCRIMINATION_V1"
    indication_mode: Literal["DIGITAL", "ANALOG"]


class DiscriminationObservation(Observation):
    test_code: Literal["DISCRIMINATION"] = DISCRIMINATION
    protocol: Literal["DISCRIMINATION_V1"] = "DISCRIMINATION_V1"
    observation_schema_version: Literal["v1"] = "v1"
    load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    indication_before_g: Number
    indication_after_g: Number
    displacement_mm: Number | None = Field(None, ge=0)
    measured_at: MeasurementTime


class DiscriminationPolicy(CommonProcedurePolicy):
    indication_mode: Literal["DIGITAL", "ANALOG"]
    test_load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    minimum_indication_change_g: Number | None = Field(None, ge=0)
    minimum_displacement_mm: Number | None = Field(None, ge=0)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]

    @model_validator(mode="after")
    def mode_limit(self):
        if self.indication_mode == "DIGITAL" and self.minimum_indication_change_g is None:
            raise ValueError("Digital discrimination policy requires indication-change threshold")
        if self.indication_mode == "ANALOG" and self.minimum_displacement_mm is None:
            raise ValueError("Analog discrimination policy requires displacement threshold")
        return self


@dataclass(frozen=True)
class DiscriminationEvaluator:
    def required_rules(self, **kwargs):
        return (
            DISCRIMINATION_POLICY,
            DISCRIMINATION_CLASSIFICATION,
            DISCRIMINATION_CALIBRATION,
        )

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=DISCRIMINATION,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset,
            DISCRIMINATION_POLICY,
            "discrimination_procedure_v1",
            DiscriminationPolicy,
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows = observations.rows
        issues = []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

        selected = instrument_snapshot.select_range(procedure_context.range_no)
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required discrimination trials missing",
            missing=True,
        )
        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        check(
            procedure_context.indication_mode == policy.indication_mode
            and procedure_context.procedure_variant == policy.indication_mode,
            "STAGE",
            "Indication mode differs from verified discrimination procedure",
        )
        check(
            instrument_snapshot.indication_type is None
            or instrument_snapshot.indication_type == policy.indication_mode,
            "STAGE",
            "Instrument indication type differs from verified discrimination procedure",
        )
        previous = None
        for row in rows:
            check(
                row.load_g == policy.test_load_g,
                "LOAD_COVERAGE",
                "Discrimination test load differs from verified policy",
                row.sequence_no,
            )
            check(
                row.extra_load_g == policy.extra_load_g,
                "LOAD_COVERAGE",
                "Discrimination extra load differs from verified policy",
                row.sequence_no,
            )
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Load exceeds selected range",
                row.sequence_no,
            )
            if policy.indication_mode == "ANALOG":
                check(
                    row.displacement_mm is not None,
                    "FUNCTIONAL",
                    "Analog discrimination requires displacement observation",
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
            not policy.require_stabilization or procedure_context.stabilized is True,
            "STABILIZATION",
            "Verified procedure requires stabilization",
        )
        check(
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset,
            DISCRIMINATION_POLICY,
            "discrimination_procedure_v1",
            DiscriminationPolicy,
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            if policy.indication_mode == "DIGITAL":
                value = exact("subtract", row.indication_after_g, row.indication_before_g)
                limit = _functional_limit(
                    name="minimum_indication_change",
                    value=policy.minimum_indication_change_g,
                    operator=policy.operator,
                    semantics=policy.semantics,
                    refs=refs,
                    unit="g",
                )
                expression = "indication_after - indication_before"
                unit = "g"
            else:
                value = row.displacement_mm
                limit = _functional_limit(
                    name="minimum_displacement",
                    value=policy.minimum_displacement_mm,
                    operator=policy.operator,
                    semantics=policy.semantics,
                    refs=refs,
                    unit="mm",
                )
                expression = "observed permanent displacement"
                unit = "mm"
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:discrimination_response",
                    expression=expression,
                    value=value,
                    unit=unit,
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(value, limit.value, operator=limit.operator, semantics=limit.semantics):
                failures.append(
                    FailedCondition(
                        code="DISCRIMINATION_RESPONSE_INSUFFICIENT",
                        reason=(
                            f"Observation {row.sequence_no} violates verified "
                            "discrimination response"
                        ),
                        actual=value,
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
            reasons=(
                "Complete discrimination procedure evaluated using pinned verified dependencies",
            ),
        )


def discrimination_registration():
    return EvaluatorRegistration(
        DISCRIMINATION,
        DiscriminationEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(DISCRIMINATION, "DIGITAL", "v1", DiscriminationContext),
                ContextRegistration(DISCRIMINATION, "ANALOG", "v1", DiscriminationContext),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    DISCRIMINATION, "DISCRIMINATION_V1", "v1", DiscriminationObservation
                ),
            )
        ),
        implementation_version="section4-discrimination-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("discrimination_procedure_v1", DiscriminationPolicy),
        ),
    )


# ---------------------------------------------------------------------------
# Section 4.2 — sensitivity
# ---------------------------------------------------------------------------

SENSITIVITY = "SENSITIVITY"
SENSITIVITY_POLICY = "SECTION4_SENSITIVITY_PROCEDURE"
SENSITIVITY_CLASSIFICATION = "SECTION4_CLASSIFICATION"
SENSITIVITY_CALIBRATION = "SECTION4_CALIBRATION"


class SensitivityContext(_EvidenceContext):
    test_code: Literal["SENSITIVITY"] = SENSITIVITY
    procedure_variant: Literal["NON_SELF_INDICATING"] = "NON_SELF_INDICATING"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["SENSITIVITY_V1"] = "SENSITIVITY_V1"


class SensitivityObservation(Observation):
    test_code: Literal["SENSITIVITY"] = SENSITIVITY
    protocol: Literal["SENSITIVITY_V1"] = "SENSITIVITY_V1"
    observation_schema_version: Literal["v1"] = "v1"
    load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    permanent_displacement_mm: Number = Field(ge=0)
    measured_at: MeasurementTime


class SensitivityPolicy(CommonProcedurePolicy):
    test_load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    minimum_displacement_mm: Number = Field(ge=0)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]


@dataclass(frozen=True)
class SensitivityEvaluator:
    def required_rules(self, **kwargs):
        return SENSITIVITY_POLICY, SENSITIVITY_CLASSIFICATION, SENSITIVITY_CALIBRATION

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=SENSITIVITY,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, SENSITIVITY_POLICY, "sensitivity_procedure_v1", SensitivityPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows, issues = observations.rows, []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

        selected = instrument_snapshot.select_range(procedure_context.range_no)
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required sensitivity trials missing",
            missing=True,
        )
        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        if instrument_snapshot.is_self_indicating is True:
            check(
                False, "FUNCTIONAL", "Sensitivity evaluator is for non-self-indicating instruments"
            )
        previous = None
        for row in rows:
            check(
                row.load_g == policy.test_load_g,
                "LOAD_COVERAGE",
                "Sensitivity test load differs from verified policy",
                row.sequence_no,
            )
            check(
                row.extra_load_g == policy.extra_load_g,
                "LOAD_COVERAGE",
                "Sensitivity extra load differs from verified policy",
                row.sequence_no,
            )
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Load exceeds selected range",
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
            not policy.require_stabilization or procedure_context.stabilized is True,
            "STABILIZATION",
            "Verified procedure requires stabilization",
        )
        check(
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, SENSITIVITY_POLICY, "sensitivity_procedure_v1", SensitivityPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        limit = _functional_limit(
            name="minimum_displacement",
            value=policy.minimum_displacement_mm,
            operator=policy.operator,
            semantics=policy.semantics,
            refs=refs,
            unit="mm",
        )
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            value = row.permanent_displacement_mm
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:sensitivity_displacement",
                    expression="observed permanent displacement",
                    value=value,
                    unit="mm",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(value, limit.value, operator=limit.operator, semantics=limit.semantics):
                failures.append(
                    FailedCondition(
                        code="SENSITIVITY_RESPONSE_INSUFFICIENT",
                        reason=(
                            f"Observation {row.sequence_no} violates verified sensitivity response"
                        ),
                        actual=value,
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
            reasons=(
                "Complete sensitivity procedure evaluated using pinned verified dependencies",
            ),
        )


def sensitivity_registration():
    return EvaluatorRegistration(
        SENSITIVITY,
        SensitivityEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(SENSITIVITY, "NON_SELF_INDICATING", "v1", SensitivityContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(SENSITIVITY, "SENSITIVITY_V1", "v1", SensitivityObservation),)
        ),
        implementation_version="section4-sensitivity-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("sensitivity_procedure_v1", SensitivityPolicy),
        ),
    )


# ---------------------------------------------------------------------------
# Section 6.1 — zero return
# ---------------------------------------------------------------------------

ZERO_RETURN = "ZERO_RETURN"
ZERO_RETURN_POLICY = "SECTION6_ZERO_RETURN_PROCEDURE"
ZERO_RETURN_CALIBRATION = "SECTION6_CALIBRATION"


class ZeroReturnContext(_EvidenceContext):
    test_code: Literal["ZERO_RETURN"] = ZERO_RETURN
    procedure_variant: Literal["ZERO_RETURN"] = "ZERO_RETURN"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["ZERO_RETURN_V1"] = "ZERO_RETURN_V1"
    test_load_g: Number = Field(ge=0)
    hold_seconds: Number = Field(ge=0)


class ZeroReturnObservation(Observation):
    test_code: Literal["ZERO_RETURN"] = ZERO_RETURN
    protocol: Literal["ZERO_RETURN_V1"] = "ZERO_RETURN_V1"
    observation_schema_version: Literal["v1"] = "v1"
    zero_before_g: Number
    zero_after_g: Number
    measured_at: MeasurementTime


class ZeroReturnPolicy(CommonProcedurePolicy):
    test_load_g: Number = Field(ge=0)
    minimum_hold_seconds: Number = Field(ge=0)
    limit_g: Number = Field(ge=0)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]


@dataclass(frozen=True)
class ZeroReturnEvaluator:
    def required_rules(self, **kwargs):
        return ZERO_RETURN_POLICY, ZERO_RETURN_CALIBRATION

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=ZERO_RETURN,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, ZERO_RETURN_POLICY, "zero_return_procedure_v1", ZeroReturnPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows, issues = observations.rows, []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

        selected = instrument_snapshot.select_range(procedure_context.range_no)
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required zero-return trials missing",
            missing=True,
        )
        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        check(
            procedure_context.test_load_g == policy.test_load_g,
            "LOAD_COVERAGE",
            "Zero-return load differs from verified policy",
        )
        check(
            procedure_context.test_load_g <= selected.max_capacity_g,
            "RANGE",
            "Zero-return load exceeds selected range",
        )
        check(
            procedure_context.hold_seconds >= policy.minimum_hold_seconds,
            "TIMING",
            "Required zero-return hold time not reached",
        )
        previous = None
        for row in rows:
            if policy.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous = row.measured_at
        check(
            not policy.require_stabilization or procedure_context.stabilized is True,
            "STABILIZATION",
            "Verified procedure requires stabilization",
        )
        check(
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, ZERO_RETURN_POLICY, "zero_return_procedure_v1", ZeroReturnPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        limit = _functional_limit(
            name="zero_return_change",
            value=policy.limit_g,
            operator=policy.operator,
            semantics=policy.semantics,
            refs=refs,
            unit="g",
        )
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            value = exact("subtract", row.zero_after_g, row.zero_before_g)
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:zero_return_change",
                    expression="zero_after - zero_before",
                    value=value,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(value, limit.value, operator=limit.operator, semantics=limit.semantics):
                failures.append(
                    FailedCondition(
                        code="ZERO_RETURN_LIMIT_EXCEEDED",
                        reason=f"Observation {row.sequence_no} violates verified zero-return limit",
                        actual=value,
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
            reasons=(
                "Complete zero-return procedure evaluated using pinned verified dependencies",
            ),
        )


def zero_return_registration():
    return EvaluatorRegistration(
        ZERO_RETURN,
        ZeroReturnEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(ZERO_RETURN, "ZERO_RETURN", "v1", ZeroReturnContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(ZERO_RETURN, "ZERO_RETURN_V1", "v1", ZeroReturnObservation),)
        ),
        implementation_version="section6-zero-return-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("zero_return_procedure_v1", ZeroReturnPolicy),
        ),
    )


# ---------------------------------------------------------------------------
# Section 6.2 — creep
# ---------------------------------------------------------------------------

CREEP = "CREEP"
CREEP_POLICY = "SECTION6_CREEP_PROCEDURE"
CREEP_CALIBRATION = "SECTION6_CALIBRATION"


class CreepContext(_EvidenceContext):
    test_code: Literal["CREEP"] = CREEP
    procedure_variant: Literal["SHORT", "EXTENDED"]
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["CREEP_V1"] = "CREEP_V1"
    test_load_g: Number = Field(ge=0)
    planned_duration_s: Number = Field(ge=0)


class CreepObservation(Observation):
    test_code: Literal["CREEP"] = CREEP
    protocol: Literal["CREEP_V1"] = "CREEP_V1"
    observation_schema_version: Literal["v1"] = "v1"
    elapsed_s: Number = Field(ge=0)
    indication_g: Number
    measured_at: MeasurementTime


class CreepPolicy(CommonProcedurePolicy):
    duration_kind: Literal["SHORT", "EXTENDED"]
    test_load_g: Number = Field(ge=0)
    minimum_duration_s: Number = Field(ge=0)
    required_checkpoints_s: tuple[Number, ...] = Field(min_length=2)
    limit_g: Number = Field(ge=0)
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    semantics: Literal["SIGNED", "ABSOLUTE"]

    @model_validator(mode="after")
    def checkpoints(self):
        ordered = tuple(sorted(set(self.required_checkpoints_s)))
        if len(ordered) != len(self.required_checkpoints_s):
            raise ValueError("Duplicate creep checkpoint")
        if ordered[0] != 0:
            raise ValueError("Creep checkpoints must include zero-time reference")
        object.__setattr__(self, "required_checkpoints_s", ordered)
        return self


@dataclass(frozen=True)
class CreepEvaluator:
    def required_rules(self, **kwargs):
        return CREEP_POLICY, CREEP_CALIBRATION

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=CREEP,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(ruleset, CREEP_POLICY, "creep_procedure_v1", CreepPolicy)
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows, issues = observations.rows, []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

        selected = instrument_snapshot.select_range(procedure_context.range_no)
        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required creep checkpoints missing",
            missing=True,
        )
        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        check(
            procedure_context.procedure_variant == policy.duration_kind,
            "STAGE",
            "Creep duration mode differs from verified policy",
        )
        check(
            procedure_context.test_load_g == policy.test_load_g,
            "LOAD_COVERAGE",
            "Creep load differs from verified policy",
        )
        check(
            procedure_context.test_load_g <= selected.max_capacity_g,
            "RANGE",
            "Creep load exceeds selected range",
        )
        check(
            procedure_context.planned_duration_s >= policy.minimum_duration_s,
            "TIMING",
            "Required creep duration not reached",
        )
        elapsed = {row.elapsed_s for row in rows}
        for checkpoint in policy.required_checkpoints_s:
            check(
                checkpoint in elapsed,
                "TIMING",
                f"Required creep checkpoint {checkpoint} s missing",
                missing=True,
            )
        previous_time = None
        previous_elapsed = None
        for row in rows:
            if previous_elapsed is not None:
                check(
                    row.elapsed_s > previous_elapsed,
                    "ORDER",
                    "Creep elapsed times must increase",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous_time is not None:
                check(
                    row.measured_at >= previous_time,
                    "TIMING",
                    "Measurement time order invalid",
                    row.sequence_no,
                )
            previous_elapsed, previous_time = row.elapsed_s, row.measured_at
        check(
            not policy.require_stabilization or procedure_context.stabilized is True,
            "STABILIZATION",
            "Verified procedure requires stabilization",
        )
        check(
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(ruleset, CREEP_POLICY, "creep_procedure_v1", CreepPolicy)
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows = observations.rows
        baseline = rows[0].indication_g
        limit = _functional_limit(
            name="creep_change",
            value=policy.limit_g,
            operator=policy.operator,
            semantics=policy.semantics,
            refs=refs,
            unit="g",
        )
        calculations, limits, failures = [], [], []
        for row in rows[1:]:
            value = exact("subtract", row.indication_g, baseline)
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:creep_change",
                    expression="indication_at_checkpoint - initial_indication",
                    value=value,
                    unit="g",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not compare(value, limit.value, operator=limit.operator, semantics=limit.semantics):
                failures.append(
                    FailedCondition(
                        code="CREEP_LIMIT_EXCEEDED",
                        reason=f"Observation {row.sequence_no} violates verified creep limit",
                        actual=value,
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
            reasons=("Complete creep procedure evaluated using pinned verified dependencies",),
        )


def creep_registration():
    return EvaluatorRegistration(
        CREEP,
        CreepEvaluator(),
        ProcedureContextRegistry(
            (
                ContextRegistration(CREEP, "SHORT", "v1", CreepContext),
                ContextRegistration(CREEP, "EXTENDED", "v1", CreepContext),
            )
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(CREEP, "CREEP_V1", "v1", CreepObservation),)
        ),
        implementation_version="section6-creep-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("creep_procedure_v1", CreepPolicy),
        ),
    )


# ---------------------------------------------------------------------------
# Section 7 — stability of equilibrium
# ---------------------------------------------------------------------------

STABILITY_EQUILIBRIUM = "STABILITY_EQUILIBRIUM"
STABILITY_POLICY = "SECTION7_PROCEDURE"


class StabilityContext(_EvidenceContext):
    test_code: Literal["STABILITY_EQUILIBRIUM"] = STABILITY_EQUILIBRIUM
    procedure_variant: Literal["FUNCTIONAL"] = "FUNCTIONAL"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["STABILITY_EQUILIBRIUM_V1"] = "STABILITY_EQUILIBRIUM_V1"
    functions_under_test: tuple[Literal["PRINTING", "STORAGE", "ZERO", "TARE"], ...] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def unique_functions(self):
        object.__setattr__(
            self, "functions_under_test", tuple(sorted(set(self.functions_under_test)))
        )
        return self


class StabilityObservation(Observation):
    test_code: Literal["STABILITY_EQUILIBRIUM"] = STABILITY_EQUILIBRIUM
    protocol: Literal["STABILITY_EQUILIBRIUM_V1"] = "STABILITY_EQUILIBRIUM_V1"
    observation_schema_version: Literal["v1"] = "v1"
    function: Literal["PRINTING", "STORAGE", "ZERO", "TARE"]
    trial_no: PositiveInt
    equilibrium_stable: StrictBool
    operation_performed: StrictBool
    adjacent_values_consistent: StrictBool | None = None
    measured_at: MeasurementTime


class StabilityPolicy(CommonProcedurePolicy):
    required_functions: tuple[Literal["PRINTING", "STORAGE", "ZERO", "TARE"], ...] = Field(
        min_length=1
    )
    minimum_trials_per_function: PositiveInt
    inhibit_when_unstable: StrictBool
    permit_when_stable: StrictBool
    require_adjacent_value_check_for: tuple[Literal["PRINTING", "STORAGE"], ...] = ()

    @model_validator(mode="after")
    def canonical_functions(self):
        object.__setattr__(self, "required_functions", tuple(sorted(set(self.required_functions))))
        object.__setattr__(
            self,
            "require_adjacent_value_check_for",
            tuple(sorted(set(self.require_adjacent_value_check_for))),
        )
        return self


@dataclass(frozen=True)
class StabilityEvaluator:
    def required_rules(self, **kwargs):
        return (STABILITY_POLICY,)

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=STABILITY_EQUILIBRIUM,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, STABILITY_POLICY, "stability_equilibrium_procedure_v1", StabilityPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        rows, issues = observations.rows, []

        def check(condition, category, reason, sequence=None, missing=False):
            if not condition:
                issues.append(_issue(refs, category, reason, sequence=sequence, missing=missing))

        check(
            len(rows) >= policy.minimum_count,
            "COUNT",
            "Required equilibrium trials missing",
            missing=True,
        )
        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible",
        )
        for function in policy.required_functions:
            check(
                function in procedure_context.functions_under_test,
                "FUNCTIONAL",
                f"Required function {function} absent from procedure context",
                missing=True,
            )
            function_rows = [row for row in rows if row.function == function]
            check(
                len(function_rows) >= policy.minimum_trials_per_function,
                "COUNT",
                f"Required {function} trials missing",
                missing=True,
            )
        previous = None
        for row in rows:
            check(
                row.function in procedure_context.functions_under_test,
                "FUNCTIONAL",
                "Observation function not declared in procedure context",
                row.sequence_no,
            )
            if row.function in policy.require_adjacent_value_check_for:
                check(
                    row.adjacent_values_consistent is not None,
                    "FUNCTIONAL",
                    "Adjacent-value behavior not recorded",
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
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Environment missing",
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Equipment missing",
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    e.calibration_certificate_no and e.certificate_content_hash
                    for e in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Calibration evidence missing",
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Evidence missing",
        )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(
            ruleset, STABILITY_POLICY, "stability_equilibrium_procedure_v1", StabilityPolicy
        )
        refs = dependencies(ruleset, self.required_rules()).rule_references
        limit = _functional_limit(
            name="required_functional_behavior",
            value="1",
            operator="==",
            semantics="SIGNED",
            refs=refs,
            unit="1",
        )
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            behavior_ok = True
            if not row.equilibrium_stable and policy.inhibit_when_unstable:
                behavior_ok = not row.operation_performed
            if row.equilibrium_stable and policy.permit_when_stable:
                behavior_ok = behavior_ok and row.operation_performed
            if (
                row.function in policy.require_adjacent_value_check_for
                and row.adjacent_values_consistent is not True
            ):
                behavior_ok = False
            value = "1" if behavior_ok else "0"
            calculations.append(
                CalculationTraceEntry(
                    name=f"{row.sequence_no}:{row.function.lower()}_equilibrium_behavior",
                    expression="verified equilibrium functional behavior",
                    value=value,
                    unit="1",
                    rule_references=refs,
                )
            )
            limits.append(limit)
            if not behavior_ok:
                failures.append(
                    FailedCondition(
                        code="STABILITY_EQUILIBRIUM_FUNCTION_FAILED",
                        reason=(
                            f"Observation {row.sequence_no} violates verified "
                            f"{row.function} behavior"
                        ),
                        actual=value,
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
            reasons=(
                "Complete stability-of-equilibrium procedure evaluated "
                "using pinned verified dependencies",
            ),
        )


def stability_registration():
    return EvaluatorRegistration(
        STABILITY_EQUILIBRIUM,
        StabilityEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(STABILITY_EQUILIBRIUM, "FUNCTIONAL", "v1", StabilityContext),)
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(
                    STABILITY_EQUILIBRIUM,
                    "STABILITY_EQUILIBRIUM_V1",
                    "v1",
                    StabilityObservation,
                ),
            )
        ),
        implementation_version="section7-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("stability_equilibrium_procedure_v1", StabilityPolicy),
        ),
    )
