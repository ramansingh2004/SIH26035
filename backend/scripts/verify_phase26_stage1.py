"""Phase 26 Stage 1 focused acceptance verifier."""

from app.compliance.domain import InstrumentSnapshot
from app.compliance.engine import synthetic_artifact
from app.compliance.full_demo import (
    FULL_DEMO_ARTIFACT,
    FULL_DEMO_VERSION,
    is_full_demo_ruleset,
    load_full_demo_ruleset,
)
from app.compliance.planning import RequirementPlanner
from app.services.rulesets import _trusted_artifact, _validation_summary


def instrument():
    return InstrumentSnapshot.model_validate(
        {
            "accuracy_class": "III",
            "min_capacity_g": "200",
            "max_capacity_g": "30000",
            "verification_interval_e_g": "10",
            "scale_interval_d_g": "10",
            "verification_intervals_n": "3000",
            "ranges": [
                {
                    "range_no": 1,
                    "min_capacity_g": "200",
                    "max_capacity_g": "30000",
                    "verification_interval_e_g": "10",
                    "scale_interval_d_g": "10",
                    "verification_intervals_n": "3000",
                }
            ],
        }
    )


def main():
    ruleset = load_full_demo_ruleset()
    assert ruleset.metadata.version == FULL_DEMO_VERSION
    assert synthetic_artifact(ruleset)
    assert is_full_demo_ruleset(ruleset)
    assert {test.section for test in ruleset.tests} == set(range(1, 18))

    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument(),
        ruleset=ruleset,
    )
    assert plan.applicability_confirmable
    assert {slot.section_number for slot in plan.slots} == set(range(1, 18))
    assert all(slot.decision.applicability == "REQUIRED" for slot in plan.slots)

    construction = [
        rule
        for rule in ruleset.rules
        if rule.section == 16 and rule.kind == "construction_item_v1"
    ]
    assert construction
    assert ruleset.checklist

    trusted, manifest = _trusted_artifact(FULL_DEMO_ARTIFACT)
    assert manifest is None
    assert trusted.configuration_hash == ruleset.configuration_hash

    summary = _validation_summary(ruleset)
    assert summary["synthetic_demo_only"] is True
    assert summary["authoritative"] is False
    assert summary["blockers"] == ["SYNTHETIC_DEMO_ONLY"]

    print("Phase 26 Stage 1 acceptance: PASS")
    print(f"- artifact: {FULL_DEMO_ARTIFACT}")
    print(f"- version: {FULL_DEMO_VERSION}")
    print("- synthetic/demo-only boundary: PASS")
    print("- trusted server artifact registration: PASS")
    print("- all 17 sections present: PASS")
    print(f"- applicability slots: {len(plan.slots)}")
    print("- every planned slot is REQUIRED for the full-flow demo: PASS")
    print(f"- Section 16 construction items: {len(construction)}")
    print(f"- Section 17 checklist rows: {len(ruleset.checklist)}")
    print("- official/authoritative status remains forbidden: PASS")
    print("- no database migration required")


if __name__ == "__main__":
    main()
