"""Pure Phase 13 rules-driven checklist engine."""

from dataclasses import dataclass
from typing import Literal

from pydantic import StrictBool, model_validator

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
