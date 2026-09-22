"""Section 9 tare-weighing mechanics driven only by verified rule configuration.

REG-12/REG-16 remain regulatory gates.  Tare modes, scenario coverage, load
steps and acceptance boundaries are supplied by verified rules, never defaults.
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
    exact,
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
    calculate_mpe,
    dependencies,
    rule_policy,
)
from app.compliance.weighing import MeasurementTime, WeighingEnvironment, WeighingEquipment

CODE = "TARE"
POLICY = "SECTION9_PROCEDURE"
MPE = "SECTION9_MPE"
CLASSIFICATION = "SECTION9_CLASSIFICATION"
CALIBRATION = "SECTION9_CALIBRATION"
TARE_RULE = "SECTION9_TARE_MODE"


class TareScenario(Frozen):
    scenario_code: Text
    tare_type: Text
    tare_value_g: Number = Field(ge=0)


class TareContext(RangeProcedureContext):
    test_code: Literal["TARE"] = CODE
    procedure_variant: Literal["DIGITAL_PRE_ROUNDING"] = "DIGITAL_PRE_ROUNDING"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["TARE_V1"] = "TARE_V1"
    stages: tuple[Literal["UP", "DOWN"], ...]
    tare_scenarios: tuple[TareScenario, ...] = Field(min_length=1)
    stabilized: StrictBool | None = None
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_sets(self):
        object.__setattr__(
            self,
            "tare_scenarios",
            ordered_unique(self.tare_scenarios, lambda s: s.scenario_code),
        )
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda e: e.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class TareObservation(Observation):
    test_code: Literal["TARE"] = CODE
    protocol: Literal["TARE_V1"] = "TARE_V1"
    observation_schema_version: Literal["v1"] = "v1"
    tare_scenario_code: Text
    tare_type: Text
    tare_value_g: Number = Field(ge=0)
    net_load_g: Number = Field(ge=0)
    gross_load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    direction: Literal["UP", "DOWN"]
    measured_at: MeasurementTime


class TareScenarioPolicy(Frozen):
    scenario_code: Text
    tare_type: Text
    tare_value_g: Number = Field(ge=0)
    minimum_count: PositiveInt
    stages: tuple[Literal["UP", "DOWN"], ...] = Field(min_length=1)
    required_net_loads_g: tuple[Number, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_loads(self):
        if len(self.required_net_loads_g) != len(set(self.required_net_loads_g)):
            raise ValueError("Duplicate required net load")
        return self


class TarePolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    indication_type: Text
    range_type: Text
    scenarios: tuple[TareScenarioPolicy, ...] = Field(min_length=1)
    enforce_gross_equals_tare_plus_net: StrictBool
    require_declared_tare_capacity: StrictBool
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def unique_scenarios(self):
        object.__setattr__(
            self, "scenarios", ordered_unique(self.scenarios, lambda s: s.scenario_code)
        )
        return self


class TarePoint(CalculationTraceEntry):
    sequence_no: PositiveInt
    range_no: PositiveInt
    tare_scenario_code: Text
    tare_type: Text
    tare_value_g: Number
    net_load_g: Number
    gross_load_g: Number
    direction: Literal["UP", "DOWN"]
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


@dataclass(frozen=True)
class TareEvaluator:
    def required_rules(self, **kwargs):
        return POLICY, MPE, CLASSIFICATION, CALIBRATION, TARE_RULE

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
        policy = rule_policy(ruleset, POLICY, "tare_procedure_v1", TarePolicy)
        refs = dependencies(ruleset, self.required_rules()).rule_references
        ctx, rows = procedure_context, observations.rows
        selected = instrument_snapshot.select_range(ctx.range_no)
        profile = rule_policy(ruleset, MPE, "mpe_profile_v1", MpeProfile)
        if (profile.accuracy_class, profile.evaluation_context) != (
            instrument_snapshot.accuracy_class,
            ctx.evaluation_context,
        ):
            raise RegulatoryBlocked(
                DependencyResolution(unresolved_rule_ids=(MPE,), rule_references=refs)
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
        if policy.require_declared_tare_capacity:
            check(
                instrument_snapshot.maximum_tare_g is not None,
                "RANGE",
                "Declared tare capacity is required",
            )
        declared = {s.scenario_code: s for s in ctx.tare_scenarios}
        policy_scenarios = {s.scenario_code: s for s in policy.scenarios}
        check(
            declared.keys() == policy_scenarios.keys(),
            "STAGE",
            "Tare scenarios differ from verified procedure",
            missing=True,
        )
        previous_time = None
        for code, scenario in policy_scenarios.items():
            ctx_scenario = declared.get(code)
            if ctx_scenario is not None:
                check(
                    ctx_scenario.tare_type == scenario.tare_type,
                    "STAGE",
                    "Tare type differs from verified policy",
                )
                check(
                    ctx_scenario.tare_value_g == scenario.tare_value_g,
                    "LOAD_COVERAGE",
                    "Tare value differs from verified policy",
                )
            group = [r for r in rows if r.tare_scenario_code == code]
            check(
                len(group) >= scenario.minimum_count,
                "COUNT",
                f"Tare scenario {code} has too few observations",
                missing=True,
            )
            observed_stages = tuple(
                r.direction
                for i, r in enumerate(group)
                if i == 0 or group[i - 1].direction != r.direction
            )
            check(
                observed_stages == scenario.stages,
                "ORDER",
                f"Tare scenario {code} stage order incomplete",
            )
            coverage = {(r.direction, r.net_load_g) for r in group}
            for direction in scenario.stages:
                for load in scenario.required_net_loads_g:
                    check(
                        (direction, load) in coverage,
                        "LOAD_COVERAGE",
                        f"Tare scenario {code} is missing a required net load",
                        missing=True,
                    )
            for row in group:
                check(
                    row.tare_type == scenario.tare_type,
                    "STAGE",
                    "Observation tare type differs from verified policy",
                    row.sequence_no,
                )
                check(
                    row.tare_value_g == scenario.tare_value_g,
                    "LOAD_COVERAGE",
                    "Observation tare value differs from verified policy",
                    row.sequence_no,
                )
                check(
                    row.net_load_g <= selected.max_capacity_g,
                    "RANGE",
                    "Net load exceeds selected range",
                    row.sequence_no,
                )
                if policy.enforce_gross_equals_tare_plus_net:
                    check(
                        row.gross_load_g == exact("add", row.tare_value_g, row.net_load_g),
                        "LOAD_COVERAGE",
                        "Gross load is inconsistent with tare plus net load",
                        row.sequence_no,
                    )
                if instrument_snapshot.maximum_tare_g is not None:
                    check(
                        row.tare_value_g <= instrument_snapshot.maximum_tare_g,
                        "RANGE",
                        "Tare value exceeds declared capacity",
                        row.sequence_no,
                    )
        check(
            {r.tare_scenario_code for r in rows} <= policy_scenarios.keys(),
            "STAGE",
            "Observation references unknown tare scenario",
        )
        for row in rows:
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
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            prerounding = calculate_prerounding_indication(
                row.indication_g, selected.verification_interval_e_g, row.additional_load_g
            )
            error = calculate_error(prerounding, row.net_load_g)
            corrected = calculate_corrected_error(error, row.zero_error_g)
            limit = calculate_mpe(
                load_g=row.net_load_g,
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
                TarePoint(
                    name=f"{row.sequence_no}:Ec",
                    expression="P=I+0.5e-deltaL; E=P-net_load; Ec=E-E0",
                    value=corrected,
                    unit="g",
                    rule_references=limit.rule_references,
                    sequence_no=row.sequence_no,
                    range_no=selected.range_no,
                    tare_scenario_code=row.tare_scenario_code,
                    tare_type=row.tare_type,
                    tare_value_g=row.tare_value_g,
                    net_load_g=row.net_load_g,
                    gross_load_g=row.gross_load_g,
                    direction=row.direction,
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
                        code="TARE_LIMIT_EXCEEDED",
                        reason=(
                            f"Observation {row.sequence_no} violates the verified tare comparison"
                        ),
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
            reasons=("Complete tare procedure evaluated using pinned verified dependencies",),
        )


def section9_registration():
    return EvaluatorRegistration(
        CODE,
        TareEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(CODE, "DIGITAL_PRE_ROUNDING", "v1", TareContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(CODE, "TARE_V1", "v1", TareObservation),)
        ),
        implementation_version="section9-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
            RulePolicyRegistration("tare_procedure_v1", TarePolicy),
        ),
    )
