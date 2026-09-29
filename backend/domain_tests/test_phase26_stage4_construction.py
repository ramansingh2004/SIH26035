from types import SimpleNamespace

from app.compliance.full_demo_construction import (
    EXPECTED_CATEGORIES,
    NOTICE,
    full_demo_construction_plan,
)
from app.compliance.full_demo_execution import load_full_demo_execution_ruleset
from app.schemas.construction import ConstructionRulePolicy
from app.services.construction import ConstructionEntry, summarize_construction


def test_stage4_v3_construction_plan_covers_all_eight_categories():
    ruleset = load_full_demo_execution_ruleset()
    plan = full_demo_construction_plan(ruleset)

    assert len(plan) == 8
    assert tuple(item.category for item in plan) == EXPECTED_CATEGORIES
    assert len({item.item_key for item in plan}) == 8
    assert all(item.evidence_required for item in plan)
    assert all(len(item.evidence_sha256) == 64 for item in plan)
    assert all(item.evidence_size > 0 for item in plan)
    assert all(NOTICE in item.remarks for item in plan)


def test_stage4_dataset_satisfies_existing_section16_completion_semantics():
    ruleset = load_full_demo_execution_ruleset()
    plan = {item.item_key: item for item in full_demo_construction_plan(ruleset)}
    entries = []

    for rule in ruleset.rules:
        if rule.section != 16 or rule.kind != "construction_item_v1":
            continue
        encoded = next(
            item.value for item in rule.parameters if item.name == "POLICY_JSON"
        )
        policy = ConstructionRulePolicy.model_validate_json(encoded)
        demo = plan[policy.item_key]
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

    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"
    assert summary["catalog_total"] == 8
    assert summary["required_total"] == 8
    assert summary["examined"] == 8
    assert summary["passed"] == 8
    assert summary["failed"] == 0
    assert summary["missing_item_keys"] == []
    assert summary["blockers"] == []
