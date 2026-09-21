"""SYNTHETIC TEST FIXTURE ONLY. Not OIML rules and not a Section 1 evaluator."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field

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
    InstrumentSnapshot,
    Number,
    Observation,
    ObservationBatch,
    ProcedureValidationIssue,
    RangeProcedureContext,
)
from app.compliance.engine import R76Engine
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
from app.compliance.procedure import ProcedureValidator
from app.compliance.registries import (
    ContextRegistration,
    ObservationRegistration,
    ObservationSchemaRegistry,
    ProcedureContextRegistry,
)
from app.compliance.regulatory import MpeProfile, calculate_mpe, dependencies, rule_policy
from app.compliance.ruleset import RuleSet

CODE = "WEIGHING_PERFORMANCE"
SOURCE = dict(
    part="SYNTHETIC",
    edition="TEST-v1",
    identity="SYNTHETIC TEST FIXTURE ONLY",
    clause="fixture-1",
    digest="a" * 64,
)
VERIFICATION = dict(
    status="VERIFIED",
    verified_by="TEST FIXTURE, NOT REGULATORY VERIFIER",
    verified_at="2000-01-01T00:00:00Z",
    evidence="SYNTHETIC TEST FIXTURE ONLY",
)


def ruleset(
    *,
    decision="REQUIRED",
    feature=None,
    scope="EACH_RANGE",
    operator="<=",
    unverified=None,
    missing_parameter=False,
):
    when = (
        {"kind": "always"}
        if feature is None
        else {"kind": "boolean", "feature": feature, "expected": True}
    )
    app = dict(
        schema_version="v1",
        scope=scope,
        scenarios=[dict(procedure_variant="SYNTHETIC", scenario="fixture")],
        cases=[
            dict(when=when, decision=decision, reason="Synthetic verified branch"),
            dict(
                when={"kind": "always"},
                decision="NOT_APPLICABLE",
                reason="Synthetic explicit false branch",
            ),
        ],
    )
    mpe = dict(
        schema_version="v1",
        accuracy_class="III",
        evaluation_context="SYNTHETIC",
        operator=operator,
        semantics="ABSOLUTE",
        bands=[
            dict(
                lower_e="0",
                upper_e="1000",
                lower_operator=">=",
                upper_operator="<=",
                multiplier_e="1",
            ),
            dict(
                lower_e="1000",
                upper_e=None,
                lower_operator=">",
                upper_operator="<=",
                multiplier_e="2",
            ),
        ],
    )
    procedure = dict(
        schema_version="v1",
        minimum_count=2,
        stages=["ZERO", "LOAD"],
        minimum_elapsed_s="1",
        equipment_required=True,
        evidence_required=True,
    )
    definitions = []
    for key, kind, policy in (
        ("APP", "applicability_policy_v1", app),
        ("MPE", "mpe_profile_v1", mpe),
        ("PROCEDURE", "procedure_v1", procedure),
        ("BASE", "dependency_v1", None),
    ):
        definitions.append(
            dict(
                key=key,
                kind=kind,
                description="SYNTHETIC TEST FIXTURE ONLY",
                source=SOURCE,
                verification={} if unverified == key else VERIFICATION,
                dependencies=["BASE"] if key != "BASE" else [],
                parameters=[]
                if policy is None
                else [
                    dict(
                        name="POLICY_JSON", value=None if missing_parameter else json.dumps(policy)
                    )
                ],
            )
        )
    return RuleSet.model_validate(
        dict(
            metadata=dict(
                schema_version=1,
                standard_code="OIML_R76",
                standard_name="SYNTHETIC",
                edition="TEST-v1",
                version="SYNTHETIC_TEST_V1",
                standard_parts=[SOURCE],
                supported_test_codes=[CODE],
                source_reference="SYNTHETIC TEST FIXTURE ONLY",
            ),
            rules=definitions,
            tests=[
                dict(
                    code=CODE,
                    section=1,
                    name="SYNTHETIC TEST FIXTURE",
                    source=SOURCE,
                    dependencies=["APP", "MPE", "PROCEDURE"],
                    verification=VERIFICATION,
                )
            ],
            checklist=[],
        )
    )


def instrument(**changes):
    capacity = dict(
        min_capacity_g="0",
        max_capacity_g="20000",
        scale_interval_d_g="10",
        verification_interval_e_g="10",
        verification_intervals_n="2000",
    )
    return InstrumentSnapshot.model_validate(
        dict(
            **capacity,
            accuracy_class="III",
            range_type="SINGLE",
            is_electronic=True,
            ranges=[dict(**capacity, range_no=1)],
        )
        | changes
    )


class FixtureContext(RangeProcedureContext):
    test_code: Literal["WEIGHING_PERFORMANCE"] = CODE
    procedure_variant: Literal["SYNTHETIC"] = "SYNTHETIC"
    procedure_schema_version: Literal["v1"] = "v1"
    evaluation_context: Literal["SYNTHETIC"] = "SYNTHETIC"
    protocol: Literal["SYNTHETIC"] = "SYNTHETIC"
    range_no: int = 1
    scenario: str = "fixture"
    stages: tuple[str, ...]
    environment: EnvironmentSnapshot
    equipment: tuple[EquipmentCalibrationSnapshot, ...]
    evidence_hashes: tuple[Digest, ...]
    protocol_note: str = "SYNTHETIC TEST FIXTURE ONLY"
    zero_error_g: Number = "0"


class FixtureContextV2(FixtureContext):
    procedure_schema_version: Literal["v2"] = "v2"


class FixtureObservation(Observation):
    test_code: Literal["WEIGHING_PERFORMANCE"] = CODE
    protocol: Literal["SYNTHETIC"] = "SYNTHETIC"
    observation_schema_version: Literal["v1"] = "v1"
    stage: Literal["ZERO", "LOAD"]
    indication_g: Number
    delta_load_g: Number
    load_g: Number
    elapsed_s: Number = Field(ge=0)
    measured_at: AwareDatetime


class FixtureObservationV2(FixtureObservation):
    observation_schema_version: Literal["v2"] = "v2"


def context(**changes):
    data = (
        dict(
            stages=("ZERO", "LOAD"),
            environment=dict(measured_at="2000-01-01T00:00:00Z", temperature_c="20"),
            equipment=[
                dict(
                    reference="FIXTURE-WEIGHT",
                    category="SYNTHETIC",
                    calibration_certificate_no="SYNTHETIC",
                )
            ],
            evidence_hashes=("b" * 64,),
        )
        | changes
    )
    return FixtureContext.model_validate(data)


def observations(*, error="20", rows=None):
    if rows is None:
        from app.compliance.numbers import exact

        rows = (
            FixtureObservation(
                sequence_no=1,
                stage="ZERO",
                indication_g="0",
                delta_load_g="5",
                load_g="0",
                elapsed_s="1",
                measured_at=datetime(2000, 1, 1, tzinfo=UTC),
            ),
            FixtureObservation(
                sequence_no=2,
                stage="LOAD",
                indication_g=exact("add", "10000", error),
                delta_load_g="5",
                load_g="10000",
                elapsed_s="2",
                measured_at=datetime(2000, 1, 1, 0, 0, 2, tzinfo=UTC),
            ),
        )
    return ObservationBatch(
        test_code=CODE, protocol="SYNTHETIC", observation_schema_version="v1", rows=rows
    )


class FixtureProcedurePolicy(Frozen):
    schema_version: Literal["v1"]
    minimum_count: int = Field(gt=0, strict=True)
    stages: tuple[str, ...]
    minimum_elapsed_s: Number
    equipment_required: bool
    evidence_required: bool


def shape_complete(*, instrument_snapshot, procedure_context, observations, ruleset):
    policy = rule_policy(ruleset, "PROCEDURE", "procedure_v1", FixtureProcedurePolicy)
    refs = dependencies(ruleset, ("PROCEDURE",)).rule_references
    issues = []
    if len(observations.rows) < policy.minimum_count:
        issues.append(
            ProcedureValidationIssue(
                code="MISSING_REQUIRED_OBSERVATIONS",
                category="COUNT",
                reason="Synthetic count incomplete",
                rule_references=refs,
            )
        )
    if (
        procedure_context.stages != policy.stages
        or tuple(r.stage for r in observations.rows) != policy.stages
    ):
        issues.append(
            ProcedureValidationIssue(
                code="EVALUATION_NOT_POSSIBLE",
                category="STAGE",
                reason="Synthetic stage/order mismatch",
                rule_references=refs,
            )
        )
    return tuple(issues)


def prerequisites(*, instrument_snapshot, procedure_context, observations, ruleset):
    policy = rule_policy(ruleset, "PROCEDURE", "procedure_v1", FixtureProcedurePolicy)
    issues = []
    for missing, category in (
        (policy.equipment_required and not procedure_context.equipment, "EQUIPMENT"),
        (policy.evidence_required and not procedure_context.evidence_hashes, "EVIDENCE"),
        (any(r.elapsed_s < policy.minimum_elapsed_s for r in observations.rows), "TIMING"),
    ):
        if missing:
            issues.append(
                ProcedureValidationIssue(
                    code="EVALUATION_NOT_POSSIBLE",
                    category=category,
                    reason="Synthetic prerequisite missing",
                )
            )
    return tuple(issues)


@dataclass(frozen=True)
class SyntheticEvaluator:
    extra_dependency: str | None = None
    repeating_division: bool = False

    def required_rules(self, **kwargs):
        return ("APP", "MPE", "PROCEDURE") + (
            (self.extra_dependency,) if self.extra_dependency else ()
        )

    def applicability(self, *, instrument_snapshot, procedure_context, ruleset):
        return ApplicabilityEngine().determine(
            test_code=CODE,
            instrument_snapshot=instrument_snapshot,
            ruleset=ruleset,
            range_no=procedure_context.range_no,
            scenario=procedure_context.scenario,
        )

    def validate_procedure(self, **kwargs):
        return ProcedureValidator((shape_complete, prerequisites)).validate(**kwargs)

    def evaluate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        if self.repeating_division:
            from app.compliance.numbers import exact

            exact("divide", "1", "3")
        selected_range = instrument_snapshot.select_range(procedure_context.range_no)
        calculations, limits, failures = [], [], []
        for row in observations.rows:
            p = calculate_prerounding_indication(
                row.indication_g, selected_range.verification_interval_e_g, row.delta_load_g
            )
            e = calculate_error(p, row.load_g)
            ec = calculate_corrected_error(e, procedure_context.zero_error_g)
            for name, value, expression in (
                ("P", p, "I + 0.5e - delta_load"),
                ("E", e, "P - L"),
                ("Ec", ec, "E - E0"),
            ):
                calculations.append(
                    CalculationTraceEntry(
                        name=f"{row.sequence_no}:{name}",
                        expression=expression,
                        value=value,
                        unit="g",
                    )
                )
            limit = calculate_mpe(
                load_g=row.load_g,
                selected_range=selected_range,
                accuracy_class=instrument_snapshot.accuracy_class,
                evaluation_context=procedure_context.evaluation_context,
                ruleset=ruleset,
                rule_id="MPE",
            )
            limits.append(limit)
            if not compare(ec, limit.value, operator=limit.operator, semantics=limit.semantics):
                failures.append(
                    FailedCondition(
                        code="SYNTHETIC_LIMIT", reason="Synthetic boundary", actual=ec, limit=limit
                    )
                )
        return EvaluationOutput(
            compliance_outcome=ComplianceOutcome.NONCOMPLIANT
            if failures
            else ComplianceOutcome.COMPLIANT,
            calculations=tuple(calculations),
            acceptance_limits=tuple(limits),
            failed_conditions=tuple(failures),
            reasons=("SYNTHETIC TEST FIXTURE ONLY; no regulatory authority",),
        )


def registration(**evaluator_options):
    return EvaluatorRegistration(
        CODE,
        SyntheticEvaluator(**evaluator_options),
        ProcedureContextRegistry(
            (
                ContextRegistration(CODE, "SYNTHETIC", "v1", FixtureContext),
                ContextRegistration(CODE, "SYNTHETIC", "v2", FixtureContextV2),
            )
        ),
        ObservationSchemaRegistry(
            (
                ObservationRegistration(CODE, "SYNTHETIC", "v1", FixtureObservation),
                ObservationRegistration(CODE, "SYNTHETIC", "v2", FixtureObservationV2),
            )
        ),
        synthetic_fixture=True,
        implementation_version="synthetic-v1"
        + (
            "-" + str(evaluator_options["extra_dependency"])
            if evaluator_options.get("extra_dependency")
            else ""
        )
        + ("-repeating" if evaluator_options.get("repeating_division") else ""),
        policy_schemas=(
            RulePolicyRegistration("applicability_policy_v1", ApplicabilityPolicy),
            RulePolicyRegistration("mpe_profile_v1", MpeProfile),
            RulePolicyRegistration("procedure_v1", FixtureProcedurePolicy),
        ),
    )


def engine(**options):
    return R76Engine(EvaluatorRegistry((registration(**options),)))


def evaluate(**changes):
    arguments = (
        dict(
            test_code=CODE,
            instrument_snapshot=instrument(),
            procedure_context=context(),
            observations=observations(),
            ruleset=ruleset(),
        )
        | changes
    )
    return engine().evaluate(**arguments)
