"""Procedure completeness is distinct from shape and from metrological acceptance."""

from dataclasses import dataclass
from typing import Protocol

from app.compliance.domain import (
    InstrumentSnapshot,
    ObservationBatch,
    ProcedureContext,
    ProcedureValidationIssue,
)
from app.compliance.ruleset import RuleSet


class ProcedureCheck(Protocol):
    def __call__(
        self,
        *,
        instrument_snapshot: InstrumentSnapshot,
        procedure_context: ProcedureContext,
        observations: ObservationBatch,
        ruleset: RuleSet,
    ) -> tuple[ProcedureValidationIssue, ...]: ...


@dataclass(frozen=True)
class ProcedureValidator:
    checks: tuple[ProcedureCheck, ...]

    def __post_init__(self):
        object.__setattr__(self, "checks", tuple(self.checks))
        if not self.checks:
            raise ValueError("Procedure validator requires explicit checks")

    def validate(self, *, instrument_snapshot, procedure_context, observations, ruleset):
        return tuple(
            issue
            for check in self.checks
            for issue in check(
                instrument_snapshot=instrument_snapshot,
                procedure_context=procedure_context,
                observations=observations,
                ruleset=ruleset,
            )
        )
