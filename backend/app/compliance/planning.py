"""Immutable applicability/requirement plans; Phase 5 owns their persistence."""

from pydantic import Field, StrictBool, model_validator

from app.compliance.applicability import ApplicabilityEngine
from app.compliance.canonical import canonical_bytes
from app.compliance.domain import (
    Applicability,
    ApplicabilityDecision,
    Frozen,
    InstrumentSnapshot,
    PositiveInt,
    Text,
    ordered_unique,
)
from app.compliance.ruleset import RuleSet


class RequirementSlot(Frozen):
    section_number: int = Field(ge=1, le=17, strict=True)
    test_code: Text
    parent_test_code: str | None = None
    range_no: PositiveInt | None
    scenario: Text
    procedure_variant: Text
    decision: ApplicabilityDecision
    elected: StrictBool = False

    @model_validator(mode="after")
    def election(self):
        if self.elected and self.decision.applicability != Applicability.OPTIONAL:
            raise ValueError("Only optional slots can be elected")
        return self

    @property
    def slot_key(self) -> str:
        # Semantic key, not another evaluation-input hash or storage ID.
        return (
            "slot:v1:"
            + canonical_bytes(
                (
                    self.section_number,
                    self.test_code,
                    self.range_no,
                    self.procedure_variant,
                    self.scenario,
                )
            ).decode()
        )

    @property
    def required_for_completion(self) -> bool:
        return self.decision.applicability == Applicability.REQUIRED or (
            self.decision.applicability == Applicability.OPTIONAL and self.elected
        )


class RequirementPlan(Frozen):
    slots: tuple[RequirementSlot, ...]

    @model_validator(mode="after")
    def unique_slots(self):
        object.__setattr__(self, "slots", ordered_unique(self.slots, lambda s: s.slot_key))
        return self

    @property
    def applicability_confirmable(self):
        return bool(self.slots) and all(
            s.decision.applicability != Applicability.REQUIRES_REVIEW for s in self.slots
        )


class RequirementPlanner:
    def plan(
        self,
        *,
        instrument_snapshot: InstrumentSnapshot,
        ruleset: RuleSet,
        elected_slot_keys: tuple[str, ...] = (),
    ) -> RequirementPlan:
        engine, slots = ApplicabilityEngine(), []
        if len(set(elected_slot_keys)) != len(elected_slot_keys):
            raise ValueError("Duplicate election")
        for test in sorted(ruleset.tests, key=lambda t: (t.section, t.code)):
            policy, _ = engine.policy(ruleset=ruleset, test_code=test.code)
            if policy is None:
                identities = ((None, "UNRESOLVED", "UNRESOLVED"),)
            else:
                ranges = (
                    tuple(r.range_no for r in instrument_snapshot.ranges)
                    if (policy.scope == "EACH_RANGE")
                    else (None,)
                )
                identities = tuple(
                    (r, s.scenario, s.procedure_variant) for r in ranges for s in policy.scenarios
                )
            for range_no, scenario, variant in identities:
                decision = engine.determine(
                    test_code=test.code,
                    instrument_snapshot=instrument_snapshot,
                    ruleset=ruleset,
                    range_no=range_no,
                    scenario=None if policy is None else scenario,
                    procedure_variant=None if policy is None else variant,
                )
                slot = RequirementSlot(
                    section_number=test.section,
                    test_code=test.code,
                    parent_test_code=test.parent,
                    range_no=range_no,
                    scenario=scenario,
                    procedure_variant=variant,
                    decision=decision,
                )
                if slot.slot_key in elected_slot_keys:
                    slot = RequirementSlot(**(slot.model_dump() | {"elected": True}))
                slots.append(slot)
        if not set(elected_slot_keys) <= {s.slot_key for s in slots}:
            raise ValueError("Election references an unknown slot")
        return RequirementPlan(slots=tuple(slots))
