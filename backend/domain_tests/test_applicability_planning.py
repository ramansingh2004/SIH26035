import json

import pytest

from app.compliance.applicability import (
    AllFacts,
    AnyFact,
    ApplicabilityEngine,
    BooleanFact,
    ChoiceFact,
    NotFact,
    NumericFact,
    predicate_value,
)
from app.compliance.domain import Applicability
from app.compliance.planning import RequirementPlan, RequirementPlanner
from app.compliance.ruleset import RuleSet, load_ruleset
from domain_tests.fixtures.synthetic import CODE, instrument, ruleset


@pytest.mark.parametrize("decision", ["REQUIRED", "OPTIONAL", "NOT_APPLICABLE"])
def test_verified_synthetic_branches(decision):
    result = ApplicabilityEngine().determine(
        test_code=CODE,
        instrument_snapshot=instrument(),
        ruleset=ruleset(decision=decision),
        range_no=1,
        scenario="fixture",
    )
    assert result.applicability == decision and result.rule_references
    assert result.unresolved_rule_ids == ()


@pytest.mark.parametrize(
    "value,expected", [(True, "REQUIRED"), (False, "NOT_APPLICABLE"), (None, "REQUIRES_REVIEW")]
)
def test_unknown_not_false(value, expected):
    result = ApplicabilityEngine().determine(
        test_code=CODE,
        instrument_snapshot=instrument(is_electronic=value),
        ruleset=ruleset(feature="is_electronic"),
        range_no=1,
    )
    assert result.applicability == expected


def test_real_candidate_complete_17_section_28_definition_plan():
    candidate = load_ruleset()
    plan = RequirementPlanner().plan(instrument_snapshot=instrument(), ruleset=candidate)
    assert len(plan.slots) == 28
    assert {s.section_number for s in plan.slots} == set(range(1, 18))
    assert {s.test_code for s in plan.slots} == {t.code for t in candidate.tests}
    assert all(s.decision.applicability == Applicability.REQUIRES_REVIEW for s in plan.slots)
    assert all(s.decision.unresolved_rule_ids and s.decision.rule_references for s in plan.slots)
    assert all(not s.required_for_completion for s in plan.slots)
    assert not plan.applicability_confirmable
    assert {f"REG-{n:02}" for n in range(1, 18)} <= {
        key for slot in plan.slots for key in slot.decision.unresolved_rule_ids
    }


@pytest.mark.parametrize(
    "decision,elect,required",
    [
        ("REQUIRED", False, True),
        ("OPTIONAL", False, False),
        ("OPTIONAL", True, True),
        ("NOT_APPLICABLE", False, False),
    ],
)
def test_slot_election_semantics(decision, elect, required):
    rs, planner = ruleset(decision=decision), RequirementPlanner()
    plan = planner.plan(instrument_snapshot=instrument(), ruleset=rs)
    if elect:
        plan = planner.plan(
            instrument_snapshot=instrument(),
            ruleset=rs,
            elected_slot_keys=(plan.slots[0].slot_key,),
        )
    slot = plan.slots[0]
    assert slot.required_for_completion is required
    assert slot.elected is elect and slot.range_no == 1
    assert slot.scenario == "fixture" and slot.procedure_variant == "SYNTHETIC"
    assert plan.applicability_confirmable


def test_stable_slot_identity_and_invalid_elections():
    planner, rs = RequirementPlanner(), ruleset(decision="OPTIONAL")
    before = planner.plan(instrument_snapshot=instrument(), ruleset=rs)
    elected = planner.plan(
        instrument_snapshot=instrument(), ruleset=rs, elected_slot_keys=(before.slots[0].slot_key,)
    )
    assert before.slots[0].slot_key == elected.slots[0].slot_key
    for keys in (("unknown",), (before.slots[0].slot_key,) * 2):
        with pytest.raises(ValueError):
            planner.plan(instrument_snapshot=instrument(), ruleset=rs, elected_slot_keys=keys)
    with pytest.raises(ValueError, match="Only optional"):
        planner.plan(
            instrument_snapshot=instrument(),
            ruleset=ruleset(),
            elected_slot_keys=(before.slots[0].slot_key,),
        )
    with pytest.raises(ValueError, match="Duplicate"):
        RequirementPlan(slots=before.slots * 2)


def test_predicate_composition_uses_three_valued_logic():
    unknown = BooleanFact(kind="boolean", feature="is_mobile", expected=True)
    yes = BooleanFact(kind="boolean", feature="is_electronic", expected=True)
    no = BooleanFact(kind="boolean", feature="is_electronic", expected=False)
    inst = instrument()
    assert predicate_value(unknown, inst) is None
    assert predicate_value(NotFact(kind="not", condition=unknown), inst) is None
    assert predicate_value(AllFacts(kind="all", conditions=(unknown, no)), inst) is False
    assert predicate_value(AllFacts(kind="all", conditions=(unknown, yes)), inst) is None
    assert predicate_value(AnyFact(kind="any", conditions=(unknown, yes)), inst) is True
    assert predicate_value(AnyFact(kind="any", conditions=(unknown, no)), inst) is None
    assert predicate_value(
        ChoiceFact(kind="choice", feature="accuracy_class", expected="III"), inst
    )
    predicate = NumericFact(
        kind="number", feature="verification_interval_e_g", scope="RANGE", operator="==", value="10"
    )
    assert predicate_value(predicate, inst, 1)
    with pytest.raises(ValueError, match="requires explicit"):
        predicate_value(predicate, inst)


def test_range_scoped_planning_and_structural_vs_unverified_classification():
    one = instrument()
    low = one.ranges[0].model_dump() | dict(
        range_no=1,
        max_capacity_g="1000",
        verification_interval_e_g="1",
        scale_interval_d_g="1",
        verification_intervals_n="1000",
    )
    high = one.ranges[0].model_dump() | {"range_no": 2}
    a = instrument(range_type="MULTI_INTERVAL", ranges=[high, low])
    b = instrument(range_type="MULTI_INTERVAL", ranges=[low, high])
    planner = RequirementPlanner()
    assert planner.plan(instrument_snapshot=a, ruleset=ruleset()) == planner.plan(
        instrument_snapshot=b, ruleset=ruleset()
    )
    assert {s.range_no for s in planner.plan(instrument_snapshot=a, ruleset=ruleset()).slots} == {
        1,
        2,
    }
    # Valid structural description does not verify the real regulatory classification.
    candidate = planner.plan(instrument_snapshot=a, ruleset=load_ruleset())
    assert all("REG-02" in s.decision.unresolved_rule_ids for s in candidate.slots)


def test_no_applicability_policy_invalid_schema_or_unmatched_case():
    value = ruleset().model_dump()
    rules = list(value["rules"])
    rules[0]["kind"] = "dependency_v1"
    no_policy = RuleSet.model_validate(value | {"rules": rules})
    assert (
        not RequirementPlanner()
        .plan(instrument_snapshot=instrument(), ruleset=no_policy)
        .applicability_confirmable
    )
    for policy in (
        {"schema_version": "unknown"},
        {
            "schema_version": "v1",
            "scope": "EACH_RANGE",
            "scenarios": [{"procedure_variant": "SYNTHETIC", "scenario": "fixture"}],
            "cases": [
                {
                    "when": {"kind": "boolean", "feature": "is_electronic", "expected": False},
                    "decision": "REQUIRED",
                    "reason": "Synthetic",
                }
            ],
        },
    ):
        data = ruleset().model_dump()
        data["rules"][0]["parameters"][0]["value"] = json.dumps(policy)
        result = ApplicabilityEngine().determine(
            test_code=CODE,
            instrument_snapshot=instrument(),
            ruleset=RuleSet.model_validate(data),
            range_no=1,
        )
        assert result.applicability == Applicability.REQUIRES_REVIEW and result.unresolved_rule_ids
