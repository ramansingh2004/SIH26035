"""F05 readiness and outcome aggregation, without workflow approval decisions."""

from pydantic import StrictBool, model_validator

from app.compliance.domain import Applicability, ComplianceOutcome, EvaluationStatus, Frozen, Text


class AggregationChild(Frozen):
    semantic_key: Text
    applicability: Applicability
    elected: StrictBool = False
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    current: StrictBool = True
    # Carries a current negative descendant through a section whose readiness is
    # STALE because a different descendant is stale. Historical run failures do
    # not set this flag; use from_aggregate for nested summaries.
    current_negative_descendant: StrictBool = False

    @model_validator(mode="after")
    def election(self):
        if self.elected and self.applicability != Applicability.OPTIONAL:
            raise ValueError("Only optional work can be elected")
        if (
            self.current_negative_descendant
            and self.compliance_outcome != ComplianceOutcome.NONCOMPLIANT
        ):
            raise ValueError("Negative descendant requires a negative outcome")
        return self

    @classmethod
    def from_aggregate(cls, *, semantic_key, applicability, result, elected=False):
        return cls(
            semantic_key=semantic_key,
            applicability=applicability,
            elected=elected,
            evaluation_status=result.evaluation_status,
            compliance_outcome=result.compliance_outcome,
            current_negative_descendant=result.has_current_failure,
        )


class AggregationInput(Frozen):
    children: tuple[AggregationChild, ...]
    missing_mandatory_stages: StrictBool = False
    unresolved_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def distinct(self):
        if len({c.semantic_key for c in self.children}) != len(self.children):
            raise ValueError("Duplicate aggregate child")
        return self


class AggregationResult(Frozen):
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    reasons: tuple[Text, ...]
    has_current_failure: StrictBool


def aggregate(value: AggregationInput) -> AggregationResult:
    children = tuple(
        c
        for c in value.children
        if c.applicability == Applicability.REQUIRED
        or c.applicability == Applicability.OPTIONAL
        and c.elected
    )
    unresolved = bool(value.unresolved_rule_ids) or any(
        c.applicability == Applicability.REQUIRES_REVIEW for c in value.children
    )
    statuses = {c.evaluation_status for c in children}
    stale = any(not c.current or c.evaluation_status == EvaluationStatus.STALE for c in children)
    if stale:
        status = EvaluationStatus.STALE
    elif unresolved or EvaluationStatus.REVIEW_REQUIRED in statuses:
        status = EvaluationStatus.REVIEW_REQUIRED
    elif value.missing_mandatory_stages or EvaluationStatus.INCOMPLETE in statuses:
        status = EvaluationStatus.INCOMPLETE
    elif EvaluationStatus.IN_PROGRESS in statuses or (
        EvaluationStatus.NOT_STARTED in statuses and EvaluationStatus.COMPLETE in statuses
    ):
        status = EvaluationStatus.IN_PROGRESS
    elif not children or statuses == {EvaluationStatus.NOT_STARTED}:
        status = EvaluationStatus.NOT_STARTED
    else:
        status = EvaluationStatus.COMPLETE
    current_failure = any(
        c.current
        and (
            c.current_negative_descendant
            or c.evaluation_status != EvaluationStatus.STALE
            and c.compliance_outcome == ComplianceOutcome.NONCOMPLIANT
        )
        for c in children
    )
    if current_failure:
        outcome = ComplianceOutcome.NONCOMPLIANT
    elif (
        status == EvaluationStatus.COMPLETE
        and children
        and all(c.compliance_outcome == ComplianceOutcome.COMPLIANT for c in children)
    ):
        outcome = ComplianceOutcome.COMPLIANT
    else:
        outcome = ComplianceOutcome.UNDETERMINED
    if (
        value.children
        and all(c.applicability == Applicability.NOT_APPLICABLE for c in value.children)
        and not unresolved
        and not value.missing_mandatory_stages
    ):
        status, outcome = EvaluationStatus.COMPLETE, ComplianceOutcome.NOT_APPLICABLE
    return AggregationResult(
        evaluation_status=status,
        compliance_outcome=outcome,
        has_current_failure=current_failure,
        reasons=("Required/elected assessment; workflow approval is separate",),
    )


class SectionResultAggregator:
    @staticmethod
    def aggregate(value: AggregationInput) -> AggregationResult:
        return aggregate(value)


class SessionComplianceAggregator:
    @staticmethod
    def aggregate(value: AggregationInput) -> AggregationResult:
        # N/A/empty session assessments confer no issuance authority.
        return aggregate(value)
