"""Evaluator protocol and immutable dispatch registry. No production evaluator yet."""

from dataclasses import dataclass, is_dataclass
from re import fullmatch
from typing import Protocol

from app.compliance.catalog import FAMILIES, SECTIONS
from app.compliance.domain import (
    ApplicabilityDecision,
    EvaluationOutput,
    Frozen,
    InstrumentSnapshot,
    ObservationBatch,
    ProcedureContext,
    ProcedureValidationIssue,
)
from app.compliance.registries import ObservationSchemaRegistry, ProcedureContextRegistry
from app.compliance.ruleset import RuleSet

KNOWN_TEST_CODES = tuple(SECTIONS) + tuple(code for family in FAMILIES.values() for code in family)


@dataclass(frozen=True)
class RulePolicyRegistration:
    kind: str
    schema: type[Frozen]

    def __post_init__(self):
        if not issubclass(self.schema, Frozen):
            raise ValueError("Policy schema must be immutable and closed")


class Evaluator(Protocol):
    def required_rules(
        self, *, instrument_snapshot: InstrumentSnapshot, procedure_context: ProcedureContext
    ) -> tuple[str, ...]: ...

    def applicability(
        self,
        *,
        instrument_snapshot: InstrumentSnapshot,
        procedure_context: ProcedureContext,
        ruleset: RuleSet,
    ) -> ApplicabilityDecision: ...

    def validate_procedure(
        self,
        *,
        instrument_snapshot: InstrumentSnapshot,
        procedure_context: ProcedureContext,
        observations: ObservationBatch,
        ruleset: RuleSet,
    ) -> tuple[ProcedureValidationIssue, ...]: ...

    def evaluate(
        self,
        *,
        instrument_snapshot: InstrumentSnapshot,
        procedure_context: ProcedureContext,
        observations: ObservationBatch,
        ruleset: RuleSet,
    ) -> EvaluationOutput: ...


@dataclass(frozen=True)
class EvaluatorRegistration:
    test_code: str
    evaluator: Evaluator
    contexts: ProcedureContextRegistry
    observations: ObservationSchemaRegistry
    implementation_version: str
    synthetic_fixture: bool = False
    policy_schemas: tuple[RulePolicyRegistration, ...] = ()

    def __post_init__(self):
        if not fullmatch(r"[A-Za-z0-9_.-]+", self.implementation_version):
            raise ValueError("Explicit deterministic evaluator implementation version required")
        object.__setattr__(self, "policy_schemas", tuple(self.policy_schemas))
        if len({p.kind for p in self.policy_schemas}) != len(self.policy_schemas):
            raise ValueError("Duplicate policy schema registration")
        if self.test_code not in KNOWN_TEST_CODES:
            raise ValueError("Unknown evaluator test code")
        if not is_dataclass(self.evaluator) or not self.evaluator.__dataclass_params__.frozen:
            raise ValueError("Evaluator implementation must be an immutable dataclass")
        for registry in (self.contexts, self.observations):
            if not registry.registrations or any(
                r.test_code != self.test_code for r in registry.registrations
            ):
                raise ValueError("Evaluator/schema test-code mismatch")


@dataclass(frozen=True)
class EvaluatorRegistry:
    registrations: tuple[EvaluatorRegistration, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "registrations", tuple(self.registrations))
        if len({r.test_code for r in self.registrations}) != len(self.registrations):
            raise ValueError("Duplicate evaluator registration")

    def find(self, test_code):
        if test_code not in KNOWN_TEST_CODES:
            raise ValueError("Unknown evaluator test code")
        return next((r for r in self.registrations if r.test_code == test_code), None)

    def resolve(self, test_code):
        result = self.find(test_code)
        if result is None:
            raise ValueError("No evaluator registered for test code")
        return result
