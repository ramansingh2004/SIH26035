"""Pure Phase 13 rules-driven checklist engine."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import (
    Applicability,
    ApplicabilityDecision,
    Frozen,
    InstrumentSnapshot,
    Text,
)

CHECKLIST_FEATURES = (
    "is_direct_sales",
    "is_price_computing",
    "is_labeling",
    "is_electronic",
    "is_software_controlled",
    "data_storage_device_present",
    "printing_device_present",
    "extended_indication_available",
    "embedded_software_present",
    "loadable_software_present",
    "battery_charging_during_operation",
    "vehicle_powered",
)


class ChecklistCondition(Frozen):
    feature: Literal[
        "is_direct_sales",
        "is_price_computing",
        "is_labeling",
        "is_electronic",
        "is_software_controlled",
        "data_storage_device_present",
        "printing_device_present",
        "extended_indication_available",
        "embedded_software_present",
        "loadable_software_present",
        "battery_charging_during_operation",
        "vehicle_powered",
    ]
    equals: StrictBool


class ChecklistApplicabilityPolicy(Frozen):
    schema_version: Literal["v1"]
    mode: Literal["ALL", "ANY"] = "ALL"
    conditions: tuple[ChecklistCondition, ...] = ()
    when_match: Literal["REQUIRED", "NOT_APPLICABLE"]
    when_not_match: Literal["REQUIRED", "NOT_APPLICABLE"]
    match_reason: Text
    no_match_reason: Text

    @model_validator(mode="after")
    def coherent(self):
        features = [condition.feature for condition in self.conditions]
        if len(features) != len(set(features)):
            raise ValueError("Duplicate checklist applicability feature")
        return self


class ChecklistAlways(Frozen):
    kind: Literal["always"]


class ChecklistBooleanFact(Frozen):
    kind: Literal["boolean"]
    feature: Literal[
        "is_self_indicating",
        "is_electronic",
        "is_software_controlled",
        "zero_tracking_available",
        "is_direct_sales",
        "is_price_computing",
        "is_labeling",
        "data_storage_device_present",
        "printing_device_present",
        "extended_indication_available",
        "embedded_software_present",
        "loadable_software_present",
        "battery_charging_during_operation",
        "vehicle_powered",
    ]
    expected: StrictBool


class ChecklistChoiceFact(Frozen):
    kind: Literal["choice"]
    feature: Literal[
        "range_type",
        "indication_type",
        "power_supply_type",
        "tare_type",
        "zero_setting_type",
    ]
    expected: Text


class ChecklistPresenceFact(Frozen):
    kind: Literal["present"]
    feature: Literal[
        "tare_type",
        "zero_setting_type",
        "software_identifier",
        "interfaces",
        "peripherals",
        "components",
    ]
    expected: StrictBool = True


class ChecklistInterfaceChoiceFact(Frozen):
    kind: Literal["interface_choice"]
    attribute: Literal["name", "interface_type", "purpose"]
    expected: Text


class ChecklistInterfaceBooleanFact(Frozen):
    kind: Literal["interface_boolean"]
    attribute: Literal["externally_accessible"]
    expected: StrictBool


class ChecklistPeripheralFact(Frozen):
    kind: Literal["peripheral"]
    expected: Text


class ChecklistAllFacts(Frozen):
    kind: Literal["all"]
    conditions: tuple["ChecklistPredicate", ...] = Field(min_length=1)


class ChecklistAnyFact(Frozen):
    kind: Literal["any"]
    conditions: tuple["ChecklistPredicate", ...] = Field(min_length=1)


class ChecklistNotFact(Frozen):
    kind: Literal["not"]
    condition: "ChecklistPredicate"


ChecklistPredicate = Annotated[
    ChecklistAlways
    | ChecklistBooleanFact
    | ChecklistChoiceFact
    | ChecklistPresenceFact
    | ChecklistInterfaceChoiceFact
    | ChecklistInterfaceBooleanFact
    | ChecklistPeripheralFact
    | ChecklistAllFacts
    | ChecklistAnyFact
    | ChecklistNotFact,
    Field(discriminator="kind"),
]
ChecklistAllFacts.model_rebuild()
ChecklistAnyFact.model_rebuild()
ChecklistNotFact.model_rebuild()


def checklist_predicate_value(
    predicate: ChecklistPredicate, instrument: InstrumentSnapshot
) -> bool | None:
    if isinstance(predicate, ChecklistAlways):
        return True
    if isinstance(predicate, (ChecklistBooleanFact, ChecklistChoiceFact)):
        value = getattr(instrument, predicate.feature)
        return None if value is None else value == predicate.expected
    if isinstance(predicate, ChecklistPresenceFact):
        value = getattr(instrument, predicate.feature)
        return None if value is None else bool(value) is predicate.expected
    if isinstance(
        predicate, (ChecklistInterfaceChoiceFact, ChecklistInterfaceBooleanFact)
    ):
        interfaces = instrument.interfaces
        if interfaces is None:
            return None
        states = []
        for item in interfaces:
            value = getattr(item, predicate.attribute)
            states.append(None if value is None else value == predicate.expected)
        if True in states:
            return True
        if None in states:
            return None
        return False
    if isinstance(predicate, ChecklistPeripheralFact):
        peripherals = instrument.peripherals
        return None if peripherals is None else predicate.expected in peripherals
    if isinstance(predicate, ChecklistNotFact):
        value = checklist_predicate_value(predicate.condition, instrument)
        return None if value is None else not value
    values = [checklist_predicate_value(item, instrument) for item in predicate.conditions]
    if isinstance(predicate, ChecklistAllFacts):
        return False if False in values else None if None in values else True
    return True if True in values else None if None in values else False


class ChecklistApplicabilityCaseV2(Frozen):
    when: ChecklistPredicate
    decision: Literal["REQUIRED", "NOT_APPLICABLE"]
    reason: Text


class ChecklistApplicabilityPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[ChecklistApplicabilityCaseV2, ...] = Field(min_length=1)


class ChecklistRuleInput(Frozen):
    rule_key: Text
    group_code: Literal[
        "GENERAL",
        "DIRECT_SALES",
        "ELECTRONIC",
        "SOFTWARE_CONTROLLED",
    ]
    validation_status: Literal[
        "TODO_REGULATORY_VALIDATION",
        "VERIFIED",
    ]
    applicability_expression: dict
    evidence_required: StrictBool | None


@dataclass(frozen=True)
class ChecklistAssessment:
    rule_key: str
    decision: ApplicabilityDecision
    validation_status: str
    evidence_required: bool | None
    response_result: str
    evidence_count: int = 0


class ChecklistEngine:
    """Evaluate versioned checklist applicability and completion."""

    @staticmethod
    def applicability(
        instrument: InstrumentSnapshot,
        rule: ChecklistRuleInput,
    ) -> ApplicabilityDecision:
        if rule.validation_status != "VERIFIED":
            return ApplicabilityDecision(
                applicability=Applicability.REQUIRES_REVIEW,
                reason="Checklist wording/provenance is not verified",
                unresolved_rule_ids=(rule.rule_key,),
            )
        if rule.evidence_required is None:
            return ApplicabilityDecision(
                applicability=Applicability.REQUIRES_REVIEW,
                reason="Checklist evidence requirement is not verified",
                unresolved_rule_ids=(rule.rule_key,),
            )

        expression = rule.applicability_expression
        if expression.get("status") == "TODO_REGULATORY_VALIDATION":
            return ApplicabilityDecision(
                applicability=Applicability.REQUIRES_REVIEW,
                reason="Checklist applicability is not verified",
                unresolved_rule_ids=(rule.rule_key,),
            )
        version = expression.get("schema_version")
        if version == "v1":
            try:
                policy = ChecklistApplicabilityPolicy.model_validate(expression)
            except Exception:
                return ApplicabilityDecision(
                    applicability=Applicability.REQUIRES_REVIEW,
                    reason="Checklist applicability policy is invalid",
                    unresolved_rule_ids=(rule.rule_key,),
                )

            values = []
            unknown = []
            for condition in policy.conditions:
                value = getattr(instrument, condition.feature)
                if value is None:
                    unknown.append(condition.feature)
                else:
                    values.append(value is condition.equals)
            if unknown:
                return ApplicabilityDecision(
                    applicability=Applicability.REQUIRES_REVIEW,
                    reason=(
                        "Checklist applicability requires unknown instrument facts: "
                        + ", ".join(sorted(unknown))
                    ),
                    unresolved_rule_ids=(rule.rule_key,),
                    feature=",".join(sorted(unknown)),
                )

            matched = all(values) if policy.mode == "ALL" else any(values)
            if not policy.conditions:
                matched = True

            applicability = policy.when_match if matched else policy.when_not_match
            return ApplicabilityDecision(
                applicability=Applicability(applicability),
                reason=(policy.match_reason if matched else policy.no_match_reason),
            )

        if version == "v2":
            try:
                policy = ChecklistApplicabilityPolicyV2.model_validate(expression)
            except Exception:
                return ApplicabilityDecision(
                    applicability=Applicability.REQUIRES_REVIEW,
                    reason="Checklist applicability policy is invalid",
                    unresolved_rule_ids=(rule.rule_key,),
                )

            for case in policy.cases:
                matched = checklist_predicate_value(case.when, instrument)
                if matched is None:
                    return ApplicabilityDecision(
                        applicability=Applicability.REQUIRES_REVIEW,
                        reason="Checklist applicability requires unknown instrument facts",
                        unresolved_rule_ids=(rule.rule_key,),
                    )
                if matched:
                    return ApplicabilityDecision(
                        applicability=Applicability(case.decision),
                        reason=case.reason,
                    )
            return ApplicabilityDecision(
                applicability=Applicability.REQUIRES_REVIEW,
                reason="No verified checklist applicability case covers these facts",
                unresolved_rule_ids=(rule.rule_key,),
            )

        return ApplicabilityDecision(
            applicability=Applicability.REQUIRES_REVIEW,
            reason="Checklist applicability policy is invalid",
            unresolved_rule_ids=(rule.rule_key,),
        )

    @staticmethod
    def summarize(
        assessments,
        *,
        completion_requested=False,
    ):
        assessments = tuple(assessments)
        if not assessments:
            return {
                "schema_version": 1,
                "catalog_total": 0,
                "applicable": 0,
                "passed": 0,
                "failed": 0,
                "not_examined": 0,
                "not_applicable": 0,
                "review_required": 0,
                "evaluation_status": "REVIEW_REQUIRED",
                "compliance_outcome": "UNDETERMINED",
                "missing_rule_keys": [],
                "blockers": ["REG-15:NO_SECTION17_CHECKLIST_CATALOG"],
            }

        applicable = 0
        passed = 0
        failed = 0
        not_examined = 0
        not_applicable = 0
        review_required = 0
        missing = []
        blockers = []
        known_failure = False
        progress = False

        for assessment in assessments:
            decision = assessment.decision.applicability

            if (
                assessment.validation_status != "VERIFIED"
                or assessment.evidence_required is None
                or decision == Applicability.REQUIRES_REVIEW
            ):
                review_required += 1
                blockers.append(f"{assessment.rule_key}:TODO_REGULATORY_VALIDATION")
                continue

            if decision == Applicability.NOT_APPLICABLE:
                not_applicable += 1
                if assessment.response_result != "NOT_APPLICABLE":
                    blockers.append(f"{assessment.rule_key}:INVALID_EXCLUDED_RESPONSE")
                continue

            if decision != Applicability.REQUIRED:
                blockers.append(f"{assessment.rule_key}:UNSUPPORTED_APPLICABILITY")
                continue

            applicable += 1
            result = assessment.response_result
            if result == "PASS":
                passed += 1
                progress = True
            elif result == "FAIL":
                failed += 1
                known_failure = True
                progress = True
            elif result == "NOT_EXAMINED":
                not_examined += 1
                missing.append(assessment.rule_key)
            elif result == "NOT_APPLICABLE":
                blockers.append(f"{assessment.rule_key}:N_A_REQUIRES_VERIFIED_JUSTIFICATION")
                continue
            else:
                blockers.append(f"{assessment.rule_key}:INVALID_RESPONSE")
                continue

            if (
                assessment.evidence_required
                and result in {"PASS", "FAIL"}
                and assessment.evidence_count < 1
            ):
                missing.append(assessment.rule_key)

        if blockers:
            status = "REVIEW_REQUIRED"
            outcome = "UNDETERMINED"
        elif missing:
            status = (
                "INCOMPLETE"
                if completion_requested
                else "IN_PROGRESS"
                if progress
                else "NOT_STARTED"
            )
            outcome = "NONCOMPLIANT" if known_failure else "UNDETERMINED"
        elif completion_requested:
            status = "COMPLETE"
            if applicable == 0 and not_applicable > 0:
                outcome = "NOT_APPLICABLE"
            else:
                outcome = "NONCOMPLIANT" if known_failure else "COMPLIANT"
        else:
            status = "IN_PROGRESS" if applicable else "COMPLETE"
            outcome = "UNDETERMINED" if applicable else "NOT_APPLICABLE"

        return {
            "schema_version": 1,
            "catalog_total": len(assessments),
            "applicable": applicable,
            "passed": passed,
            "failed": failed,
            "not_examined": not_examined,
            "not_applicable": not_applicable,
            "review_required": review_required,
            "evaluation_status": status,
            "compliance_outcome": outcome,
            "missing_rule_keys": sorted(set(missing)),
            "blockers": sorted(set(blockers)),
        }
