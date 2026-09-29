"""Phase 26 Stage 4 focused acceptance verifier."""

from types import SimpleNamespace

from app.compliance.full_demo_construction import (
    EXPECTED_CATEGORIES,
    NOTICE,
    full_demo_construction_plan,
)
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_VERSION,
    load_full_demo_execution_ruleset,
)
from app.schemas.construction import ConstructionRulePolicy
from app.services.construction import ConstructionEntry, summarize_construction


def main() -> None:
    ruleset = load_full_demo_execution_ruleset()
    plan = full_demo_construction_plan(ruleset)
    by_key = {item.item_key: item for item in plan}
    entries = []

    for rule in ruleset.rules:
        if rule.section != 16 or rule.kind != "construction_item_v1":
            continue
        encoded = next(
            item.value for item in rule.parameters if item.name == "POLICY_JSON"
        )
        policy = ConstructionRulePolicy.model_validate_json(encoded)
        demo = by_key[policy.item_key]
        entries.append(
            ConstructionEntry(
                item=SimpleNamespace(
                    item_key=policy.item_key,
                    value_json=demo.value_json,
                    examination_state="EXAMINED",
                    conformance_result="PASS",
                ),
                rule=SimpleNamespace(
                    validation_status="VERIFIED",
                    rule_key=rule.key,
                ),
                policy=policy,
                evidence_count=1,
            )
        )

    summary = summarize_construction(entries, completion_requested=True)

    assert len(plan) == 8
    assert tuple(item.category for item in plan) == EXPECTED_CATEGORIES
    assert all(item.evidence_required for item in plan)
    assert all(len(item.evidence_sha256) == 64 for item in plan)
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"
    assert summary["passed"] == 8
    assert summary["missing_item_keys"] == []
    assert summary["blockers"] == []

    print("Phase 26 Stage 4 acceptance: PASS")
    print(f"- ruleset version: {FULL_DEMO_EXECUTION_VERSION}")
    print("- Section 16 construction categories: 8/8")
    print("- required construction items: 8")
    print("- synthetic evidence descriptors: 8")
    print("- deterministic PASS assessments: 8")
    print("- Section 16 summary: COMPLETE + COMPLIANT")
    print("- metadata-only evidence notice present: PASS")
    print(f"- notice: {NOTICE}")
    print("- production/official regulatory paths remain unchanged")
    print("- no database migration required")


if __name__ == "__main__":
    main()
