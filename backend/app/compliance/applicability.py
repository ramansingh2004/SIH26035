"""Three-valued typed predicates; regulatory policy is supplied by verified RuleSet data."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StrictBool, ValidationError, model_validator

from app.compliance.domain import (
    Applicability,
    ApplicabilityDecision,
    Frozen,
    InstrumentSnapshot,
    Number,
    Text,
    ordered_unique,
)
from app.compliance.numbers import Operator, compare
from app.compliance.regulatory import (
    DependencyResolution,
    dependencies,
    reference,
    rule_policy,
    verified,
)
from app.compliance.ruleset import RuleSet


class Always(Frozen):
    kind: Literal["always"]


class BooleanFact(Frozen):
    kind: Literal["boolean"]
    feature: Literal[
        "is_self_indicating",
        "is_electronic",
        "is_software_controlled",
        "is_portable",
        "is_mobile",
        "zero_tracking_available",
        "level_indicator_available",
        "automatic_tilt_sensor",
        "is_direct_sales",
        "is_price_computing",
        "is_labeling",
        "data_storage_device_present",
        "battery_charging_during_operation",
        "vehicle_powered",
    ]
    expected: StrictBool


class ChoiceFact(Frozen):
    kind: Literal["choice"]
    feature: Literal[
        "accuracy_class",
        "range_type",
        "indication_type",
        "power_supply_type",
        "tare_type",
        "zero_setting_type",
        "load_receptor_type",
    ]
    expected: Text


class NumericFact(Frozen):
    kind: Literal["number"]
    feature: Literal[
        "max_capacity_g",
        "min_capacity_g",
        "verification_interval_e_g",
        "scale_interval_d_g",
        "verification_intervals_n",
        "maximum_tare_g",
        "nominal_voltage",
        "min_voltage",
        "max_voltage",
        "declared_temp_min_c",
        "declared_temp_max_c",
    ]
    scope: Literal["INSTRUMENT", "RANGE"]
    operator: Operator
    value: Number


class AllFacts(Frozen):
    kind: Literal["all"]
    conditions: tuple["Predicate", ...] = Field(min_length=1)


class AnyFact(Frozen):
    kind: Literal["any"]
    conditions: tuple["Predicate", ...] = Field(min_length=1)


class NotFact(Frozen):
    kind: Literal["not"]
    condition: "Predicate"


Predicate = Annotated[
    Always | BooleanFact | ChoiceFact | NumericFact | AllFacts | AnyFact | NotFact,
    Field(discriminator="kind"),
]
AllFacts.model_rebuild()
AnyFact.model_rebuild()
NotFact.model_rebuild()


def predicate_value(
    predicate: Predicate, instrument: InstrumentSnapshot, range_no: int | None = None
) -> bool | None:
    if isinstance(predicate, Always):
        return True
    if isinstance(predicate, (BooleanFact, ChoiceFact)):
        value = getattr(instrument, predicate.feature)
        return None if value is None else value == predicate.expected
    if isinstance(predicate, NumericFact):
        source = instrument
        if predicate.scope == "RANGE":
            if range_no is None:
                raise ValueError("Range predicate requires explicit range selection")
            source = instrument.select_range(range_no)
        if predicate.feature not in type(source).model_fields:
            raise ValueError("Feature is not defined for selected range scope")
        value = getattr(source, predicate.feature)
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise ValueError("Numeric predicate requires a metrological fact")
        return compare(value, predicate.value, operator=predicate.operator, semantics="SIGNED")
    if isinstance(predicate, NotFact):
        value = predicate_value(predicate.condition, instrument, range_no)
        return None if value is None else not value
    values = [predicate_value(p, instrument, range_no) for p in predicate.conditions]
    if isinstance(predicate, AllFacts):
        return False if False in values else None if None in values else True
    return True if True in values else None if None in values else False


class ApplicabilityCase(Frozen):
    when: Predicate
    decision: Literal[Applicability.REQUIRED, Applicability.OPTIONAL, Applicability.NOT_APPLICABLE]
    reason: Text


class Scenario(Frozen):
    procedure_variant: Text
    scenario: Text


class ApplicabilityPolicy(Frozen):
    schema_version: Literal["v1"]
    scope: Literal["INSTRUMENT", "EACH_RANGE"]
    scenarios: tuple[Scenario, ...] = Field(min_length=1)
    cases: tuple[ApplicabilityCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_scenarios(self):
        object.__setattr__(
            self,
            "scenarios",
            ordered_unique(self.scenarios, lambda s: (s.procedure_variant, s.scenario)),
        )
        return self


def blocked(reason, resolution, *, range_no=None, scenario=None):
    return ApplicabilityDecision(
        applicability=Applicability.REQUIRES_REVIEW,
        reason=reason,
        unresolved_rule_ids=resolution.unresolved_rule_ids,
        rule_references=resolution.rule_references,
        range_no=range_no,
        scenario=scenario,
    )


class ApplicabilityEngine:
    def policy(self, *, ruleset: RuleSet, test_code: str):
        test = next((t for t in ruleset.tests if t.code == test_code), None)
        if test is None:
            raise ValueError("Unknown catalog test")
        # Session applicability is independent of later acceptance/evaluator
        # readiness. Only explicitly declared applicability roots (and their
        # transitive dependencies) decide this gate. No guessed fallback policy.
        roots = tuple(
            r.key
            for r in ruleset.rules
            if r.key in test.dependencies and r.kind == "applicability_policy_v1"
        )
        resolution = dependencies(ruleset, roots if roots else test.dependencies)
        resolution = DependencyResolution(
            unresolved_rule_ids=resolution.unresolved_rule_ids,
            rule_references=dependencies(ruleset, test.dependencies).rule_references,
        )
        if not verified(test):
            resolution = DependencyResolution(
                unresolved_rule_ids=tuple(
                    sorted(set(resolution.unresolved_rule_ids) | {test_code})
                ),
                rule_references=(*resolution.rule_references, reference(test, test_code)),
            )
        if not resolution.verified:
            return None, resolution
        keys = {r.rule_id for r in resolution.rule_references}
        candidates = [
            r for r in ruleset.rules if r.key in keys and r.kind == "applicability_policy_v1"
        ]
        if len(candidates) != 1:
            return None, DependencyResolution(
                unresolved_rule_ids=(test_code + ":APPLICABILITY_POLICY",),
                rule_references=resolution.rule_references,
            )
        try:
            return rule_policy(
                ruleset, candidates[0].key, "applicability_policy_v1", ApplicabilityPolicy
            ), resolution
        except (ValueError, ValidationError):
            return None, DependencyResolution(
                unresolved_rule_ids=(candidates[0].key,), rule_references=resolution.rule_references
            )

    def determine(
        self,
        *,
        test_code: str,
        instrument_snapshot: InstrumentSnapshot,
        ruleset: RuleSet,
        range_no: int | None = None,
        scenario: str | None = None,
        procedure_variant: str | None = None,
    ) -> ApplicabilityDecision:
        if range_no is not None:
            instrument_snapshot.select_range(range_no)
        policy, resolution = self.policy(ruleset=ruleset, test_code=test_code)
        if policy is None:
            return blocked(
                "TODO_REGULATORY_VALIDATION: applicability dependencies unresolved",
                resolution,
                range_no=range_no,
                scenario=scenario,
            )
        if policy.scope == "EACH_RANGE" and range_no is None:
            raise ValueError("Applicability policy requires a range")
        if scenario is not None and scenario not in {s.scenario for s in policy.scenarios}:
            raise ValueError("Unknown applicability scenario")
        if procedure_variant is not None and not any(
            s.procedure_variant == procedure_variant
            and (scenario is None or s.scenario == scenario)
            for s in policy.scenarios
        ):
            raise ValueError("Unknown applicability procedure variant/scenario")
        for case in policy.cases:
            decision = predicate_value(case.when, instrument_snapshot, range_no)
            if decision is None:
                return ApplicabilityDecision(
                    applicability=Applicability.REQUIRES_REVIEW,
                    reason="Required instrument feature is unknown",
                    rule_references=resolution.rule_references,
                    range_no=range_no,
                    scenario=scenario,
                    feature=getattr(case.when, "feature", None),
                )
            if decision:
                return ApplicabilityDecision(
                    applicability=case.decision,
                    reason=case.reason,
                    rule_references=resolution.rule_references,
                    range_no=range_no,
                    scenario=scenario,
                )
        return ApplicabilityDecision(
            applicability=Applicability.REQUIRES_REVIEW,
            reason="No verified applicability case covers these facts",
            unresolved_rule_ids=(test_code + ":APPLICABILITY_COVERAGE",),
            rule_references=resolution.rule_references,
            range_no=range_no,
            scenario=scenario,
        )
