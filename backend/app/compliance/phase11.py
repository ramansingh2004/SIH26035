"""Phase 11 Section 15 endurance mechanics.

REG-14 and REG-16 remain regulatory gates. Candidate class/capacity cutoffs,
cycle counts, loads, timing and durability limits are not embedded here.
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
from app.compliance.regulatory import MpeProfile, calculate_mpe, dependencies, rule_policy
from app.compliance.weighing import MeasurementTime, WeighingEnvironment, WeighingEquipment

ENDURANCE = "ENDURANCE"
ENDURANCE_POLICY = "SECTION15_ENDURANCE_PROCEDURE"
ENDURANCE_MPE = "SECTION15_MPE"
ENDURANCE_CLASSIFICATION = "SECTION15_CLASSIFICATION"
ENDURANCE_CALIBRATION = "SECTION15_CALIBRATION"


def _issue(refs, category, reason, *, sequence=None, missing=False):
    return ProcedureValidationIssue(
        code="MISSING_REQUIRED_OBSERVATIONS" if missing else "EVALUATION_NOT_POSSIBLE",
        category=category,
        reason=reason,
        sequence_no=sequence,
        rule_references=refs,
    )


class EnduranceLoadPoint(Frozen):
    point_id: Text
    load_fraction_of_max: Number = Field(ge=0, le=1)
    load_tolerance_g: Number = Field(ge=0)


class EndurancePolicy(Frozen):
    schema_version: Literal["v1"]
    evaluation_context: Text
    required_cycles: PositiveInt
    completed_cycles_operator: Literal["==", ">="]
    cycling_load_fraction_of_max: Number = Field(gt=0, le=1)
    cycling_load_tolerance_g: Number = Field(ge=0)
    cycling_load_operator: Literal["<", "<="]
    require_cycle_timestamps: StrictBool
    minimum_cycle_duration_s: Number | None = Field(None, ge=0)
    cycle_duration_operator: Literal[">", ">="] | None = None
    required_load_points: tuple[EnduranceLoadPoint, ...] = Field(min_length=1)
    require_same_reference_weights: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool
    require_abnormal_events_resolved: StrictBool
    durability_formula: Literal["ABS_CORRECTED_ERROR_CHANGE"]
    durability_mpe_multiplier: Number = Field(ge=0)
    durability_operator: Literal["<", "<=", ">", ">=", "==", "!="]
    durability_semantics: Literal["SIGNED", "ABSOLUTE"]

    @model_validator(mode="after")
    def coherent_policy(self):
        ids = [x.point_id for x in self.required_load_points]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate endurance performance point")
        a, b = self.minimum_cycle_duration_s, self.cycle_duration_operator
        if (a is None) != (b is None):
            raise ValueError("Minimum cycle duration and operator must be supplied together")
        return self


class EnduranceContext(RangeProcedureContext):
    test_code: Literal["ENDURANCE"] = ENDURANCE
    procedure_variant: Literal["MECHANICAL_CYCLING"] = "MECHANICAL_CYCLING"
    procedure_schema_version: Literal["v1"] = "v1"
    protocol: Literal["ENDURANCE_V1"] = "ENDURANCE_V1"
    cycling_target_load_g: Number = Field(ge=0)
    planned_cycles: PositiveInt
    completed_cycles: int = Field(ge=0, strict=True)
    cycle_started_at: MeasurementTime | None = None
    cycle_ended_at: MeasurementTime | None = None
    same_reference_weights_confirmed: StrictBool
    abnormal_events: tuple[Text, ...] = ()
    abnormal_events_resolved: StrictBool = True
    environment: tuple[WeighingEnvironment, ...] = ()
    equipment: tuple[WeighingEquipment, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def coherent_context(self):
        if (self.cycle_started_at is None) != (self.cycle_ended_at is None):
            raise ValueError("Cycle start and end timestamps must be supplied together")
        if (
            self.cycle_started_at
            and self.cycle_ended_at
            and self.cycle_ended_at < self.cycle_started_at
        ):
            raise ValueError("Cycle end cannot precede cycle start")
        object.__setattr__(self, "equipment", ordered_unique(self.equipment, lambda x: x.reference))
        object.__setattr__(self, "evidence_hashes", tuple(sorted(set(self.evidence_hashes))))
        return self


class EnduranceObservation(Observation):
    test_code: Literal["ENDURANCE"] = ENDURANCE
    protocol: Literal["ENDURANCE_V1"] = "ENDURANCE_V1"
    observation_schema_version: Literal["v1"] = "v1"
    phase: Literal["INITIAL", "FINAL"]
    point_id: Text
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    measured_at: MeasurementTime


def _corrected(row, selected):
    p = calculate_prerounding_indication(
        row.indication_g, selected.verification_interval_e_g, row.additional_load_g
    )
    e = calculate_error(p, row.load_g)
    return p, e, calculate_corrected_error(e, row.zero_error_g)


@dataclass(frozen=True)
class EnduranceEvaluator:
    def required_rules(self, **kwargs):
        return (ENDURANCE_POLICY, ENDURANCE_MPE, ENDURANCE_CLASSIFICATION, ENDURANCE_CALIBRATION)

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=ENDURANCE,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
            procedure_variant=procedure_context.procedure_variant,
        )

    def validate_procedure(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(ruleset, ENDURANCE_POLICY, "endurance_procedure_v1", EndurancePolicy)
        refs = dependencies(ruleset, self.required_rules()).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        rows = observations.rows
        issues = []

        def check(ok, cat, reason, seq=None, missing=False):
            if not ok:
                issues.append(_issue(refs, cat, reason, sequence=seq, missing=missing))

        check(
            procedure_context.evaluation_context == policy.evaluation_context,
            "STAGE",
            "Evaluation context incompatible with verified endurance procedure",
        )
        check(
            procedure_context.planned_cycles == policy.required_cycles,
            "COUNT",
            "Planned endurance cycles differ from verified procedure",
        )
        completed_cycles_ok = (
            procedure_context.completed_cycles == policy.required_cycles
            if policy.completed_cycles_operator == "=="
            else procedure_context.completed_cycles >= policy.required_cycles
        )
        check(
            completed_cycles_ok,
            "COUNT",
            "Verified endurance cycle requirement is incomplete",
            missing=True,
        )
        expected_cycle = exact(
            "multiply", selected.max_capacity_g, policy.cycling_load_fraction_of_max
        )
        cycle_diff = exact(
            "subtract", procedure_context.cycling_target_load_g, expected_cycle
        ).copy_abs()
        check(
            compare(
                cycle_diff,
                policy.cycling_load_tolerance_g,
                operator=policy.cycling_load_operator,
                semantics="SIGNED",
            ),
            "LOAD_COVERAGE",
            "Cycling target load differs from verified endurance profile",
        )
        check(
            procedure_context.cycling_target_load_g <= selected.max_capacity_g,
            "RANGE",
            "Cycling target load exceeds selected range",
        )
        if policy.require_cycle_timestamps:
            check(
                procedure_context.cycle_started_at is not None
                and procedure_context.cycle_ended_at is not None,
                "TIMING",
                "Verified endurance procedure requires cycle start/end timestamps",
                missing=True,
            )
        if (
            procedure_context.cycle_started_at
            and procedure_context.cycle_ended_at
            and policy.minimum_cycle_duration_s is not None
        ):
            elapsed = procedure_context.cycle_ended_at - procedure_context.cycle_started_at
            duration_us = (
                elapsed.days * 86400 + elapsed.seconds
            ) * 1_000_000 + elapsed.microseconds
            duration_s = exact(
                "divide",
                str(duration_us),
                "1000000",
            )
            check(
                compare(
                    duration_s,
                    policy.minimum_cycle_duration_s,
                    operator=policy.cycle_duration_operator,
                    semantics="SIGNED",
                ),
                "TIMING",
                "Endurance cycling duration does not satisfy verified procedure",
            )
        check(
            not policy.require_same_reference_weights
            or procedure_context.same_reference_weights_confirmed,
            "EQUIPMENT",
            "Initial/final measurements require the same reference weights",
        )
        check(
            not policy.require_environment or bool(procedure_context.environment),
            "ENVIRONMENT",
            "Required endurance environment evidence missing",
            missing=True,
        )
        check(
            not policy.require_equipment or bool(procedure_context.equipment),
            "EQUIPMENT",
            "Required endurance equipment missing",
            missing=True,
        )
        if policy.require_certificate:
            check(
                bool(procedure_context.equipment)
                and all(
                    x.calibration_certificate_no and x.certificate_content_hash
                    for x in procedure_context.equipment
                ),
                "EQUIPMENT",
                "Required endurance calibration evidence missing",
                missing=True,
            )
        check(
            not policy.require_evidence or bool(procedure_context.evidence_hashes),
            "EVIDENCE",
            "Required endurance supporting evidence missing",
            missing=True,
        )
        check(
            not policy.require_abnormal_events_resolved
            or not procedure_context.abnormal_events
            or procedure_context.abnormal_events_resolved,
            "FUNCTIONAL",
            "Endurance cycling contains unresolved abnormal events",
        )
        expected = tuple(
            (phase, p.point_id)
            for phase in ("INITIAL", "FINAL")
            for p in policy.required_load_points
        )
        actual = tuple((r.phase, r.point_id) for r in rows)
        check(
            len(actual) == len(expected),
            "COUNT",
            "Required initial/final endurance measurements are incomplete",
            missing=len(actual) < len(expected),
        )
        check(
            actual == expected,
            "ORDER",
            "Endurance performance sequence is incomplete or out of order",
            missing=len(actual) < len(expected),
        )
        points = {p.point_id: p for p in policy.required_load_points}
        initial = {}
        previous = None
        for row in rows:
            point = points.get(row.point_id)
            check(
                point is not None,
                "LOAD_COVERAGE",
                "Unexpected endurance performance point",
                row.sequence_no,
            )
            if point:
                expected_load = exact(
                    "multiply", selected.max_capacity_g, point.load_fraction_of_max
                )
                diff = exact("subtract", row.load_g, expected_load).copy_abs()
                check(
                    compare(diff, point.load_tolerance_g, operator="<=", semantics="SIGNED"),
                    "LOAD_COVERAGE",
                    "Endurance performance load differs from verified point",
                    row.sequence_no,
                )
            check(
                row.load_g <= selected.max_capacity_g,
                "RANGE",
                "Endurance load exceeds selected range",
                row.sequence_no,
            )
            if row.phase == "INITIAL":
                initial[row.point_id] = row.load_g
            elif row.point_id in initial:
                check(
                    row.load_g == initial[row.point_id],
                    "LOAD_COVERAGE",
                    "Initial and final endurance loads do not match",
                    row.sequence_no,
                )
            if policy.require_monotonic_timestamps and previous is not None:
                check(
                    row.measured_at >= previous,
                    "TIMING",
                    "Endurance timestamps are not monotonic",
                    row.sequence_no,
                )
            previous = row.measured_at
        if procedure_context.cycle_started_at and procedure_context.cycle_ended_at:
            ini = [r for r in rows if r.phase == "INITIAL"]
            fin = [r for r in rows if r.phase == "FINAL"]
            if ini:
                check(
                    max(r.measured_at for r in ini) <= procedure_context.cycle_started_at,
                    "TIMING",
                    "Initial measurements must precede endurance cycling",
                )
            if fin:
                check(
                    min(r.measured_at for r in fin) >= procedure_context.cycle_ended_at,
                    "TIMING",
                    "Final measurements must follow endurance cycling",
                )
        return tuple(issues)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        policy = rule_policy(ruleset, ENDURANCE_POLICY, "endurance_procedure_v1", EndurancePolicy)
        refs = dependencies(ruleset, self.required_rules()).rule_references
        selected = instrument_snapshot.select_range(procedure_context.range_no)
        rows = {(r.phase, r.point_id): r for r in observations.rows}
        calculations = []
        limits = []
        failures = []
        for point in policy.required_load_points:
            initial = rows[("INITIAL", point.point_id)]
            final = rows[("FINAL", point.point_id)]
            ip, ie, iec = _corrected(initial, selected)
            fp, fe, fec = _corrected(final, selected)
            durability = exact("subtract", fec, iec).copy_abs()
            for phase, p, e, ec in (("INITIAL", ip, ie, iec), ("FINAL", fp, fe, fec)):
                calculations.extend(
                    (
                        CalculationTraceEntry(
                            name=f"{point.point_id}:{phase}:P",
                            expression="I + 0.5e - delta_load",
                            value=p,
                            unit="g",
                            rule_references=refs,
                        ),
                        CalculationTraceEntry(
                            name=f"{point.point_id}:{phase}:E",
                            expression="P - L",
                            value=e,
                            unit="g",
                            rule_references=refs,
                        ),
                        CalculationTraceEntry(
                            name=f"{point.point_id}:{phase}:Ec",
                            expression="E - E0",
                            value=ec,
                            unit="g",
                            rule_references=refs,
                        ),
                    )
                )
            calculations.append(
                CalculationTraceEntry(
                    name=f"{point.point_id}:durability_error",
                    expression="abs(Ec_final - Ec_initial)",
                    value=durability,
                    unit="g",
                    rule_references=refs,
                )
            )
            mpe = calculate_mpe(
                load_g=initial.load_g,
                selected_range=selected,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id=ENDURANCE_MPE,
            )
            limit = AcceptanceLimit(
                name=f"{point.point_id}:durability_limit",
                value=exact("multiply", mpe.value, policy.durability_mpe_multiplier),
                unit="g",
                operator=policy.durability_operator,
                semantics=policy.durability_semantics,
                rule_references=refs,
            )
            limits.append(limit)
            if not compare(
                durability, limit.value, operator=limit.operator, semantics=limit.semantics
            ):
                failures.append(
                    FailedCondition(
                        code="ENDURANCE_DURABILITY_LIMIT_EXCEEDED",
                        reason=f"Durability error at {point.point_id} exceeds the verified limit",
                        actual=durability,
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
            reasons=("Complete endurance procedure evaluated using pinned verified dependencies",),
        )


def endurance_registration():
    return EvaluatorRegistration(
        ENDURANCE,
        EnduranceEvaluator(),
        ProcedureContextRegistry(
            (ContextRegistration(ENDURANCE, "MECHANICAL_CYCLING", "v1", EnduranceContext),)
        ),
        ObservationSchemaRegistry(
            (ObservationRegistration(ENDURANCE, "ENDURANCE_V1", "v1", EnduranceObservation),)
        ),
        implementation_version="section15-v1",
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("endurance_procedure_v1", EndurancePolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
        ),
    )
