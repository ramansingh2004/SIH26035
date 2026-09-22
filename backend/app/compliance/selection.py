"""Explicit verified retest-selection policy; no default policy or thresholds."""

from typing import Literal

from pydantic import Field, StrictBool

from app.compliance.domain import ComplianceOutcome, EvaluationStatus, Frozen


class SelectionPolicy(Frozen):
    schema_version: Literal["v1"]
    allowed_evaluation_statuses: tuple[EvaluationStatus, ...] = Field(min_length=1)
    allowed_compliance_outcomes: tuple[ComplianceOutcome, ...] = Field(min_length=1)
    require_current_result: StrictBool
    allow_replacing_known_failure: StrictBool

    def permits(self, status, outcome, *, current, replacing_negative):
        return (
            status in self.allowed_evaluation_statuses
            and outcome in self.allowed_compliance_outcomes
            and (current or not self.require_current_result)
            and (not replacing_negative or self.allow_replacing_known_failure)
        )
