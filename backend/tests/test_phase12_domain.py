"""Pure Phase 12 construction dossier semantics."""

import json
from types import SimpleNamespace

import pytest

from app.schemas.construction import ConstructionRulePolicy
from app.services.construction import (
    ConstructionEntry,
    construction_policy,
    summarize_construction,
)


def policy(**changes):
    payload = dict(
        schema_version="v1",
        category="GENERAL",
        item_key="GENERAL.IDENTITY",
        sort_order=10,
        required=True,
        evidence_required=False,
        allow_not_applicable=False,
        required_value_keys=("observed_value",),
    )
    payload.update(changes)
    return ConstructionRulePolicy.model_validate(payload)


def item(**changes):
    payload = dict(
        item_key="GENERAL.IDENTITY",
        value_json={},
        examination_state="NOT_EXAMINED",
        conformance_result="UNDETERMINED",
    )
    payload.update(changes)
    return SimpleNamespace(**payload)


def rule(**changes):
    payload = dict(
        id="rule-id",
        rule_key="SECTION16_GENERAL_IDENTITY",
        rule_type="construction_item_v1",
        validation_status="VERIFIED",
        configuration={
            "parameters": [
                {
                    "name": "POLICY_JSON",
                    "value": json.dumps(policy().model_dump(mode="json")),
                }
            ]
        },
    )
    payload.update(changes)
    return SimpleNamespace(**payload)


def entry(
    *,
    item_value=None,
    rule_value=None,
    policy_value=None,
    evidence=0,
):
    return ConstructionEntry(
        item=item_value or item(),
        rule=rule_value or rule(),
        policy=policy_value or policy(),
        evidence_count=evidence,
    )


def test_construction_policy_reads_single_versioned_policy():
    parsed = construction_policy(rule())
    assert parsed.item_key == "GENERAL.IDENTITY"
    assert parsed.required is True


@pytest.mark.parametrize(
    "parameters",
    [
        [],
        [{"name": "POLICY_JSON", "value": "{}"}],
        [
            {
                "name": "POLICY_JSON",
                "value": json.dumps(policy().model_dump(mode="json")),
            },
            {
                "name": "POLICY_JSON",
                "value": json.dumps(policy().model_dump(mode="json")),
            },
        ],
    ],
)
def test_invalid_construction_policy_is_rejected(parameters):
    with pytest.raises(ValueError):
        construction_policy(rule(configuration={"parameters": parameters}))


def test_missing_catalog_is_review_required_not_compliant():
    summary = summarize_construction(())
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert summary["compliance_outcome"] == "UNDETERMINED"
    assert summary["blockers"] == ["REG-15:NO_SECTION16_CONSTRUCTION_CATALOG"]


def test_unverified_rule_forces_review_required():
    summary = summarize_construction(
        [entry(rule_value=rule(validation_status="TODO_REGULATORY_VALIDATION"))]
    )
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert summary["compliance_outcome"] == "UNDETERMINED"


def test_untouched_verified_dossier_is_not_started():
    summary = summarize_construction([entry()])
    assert summary["evaluation_status"] == "NOT_STARTED"
    assert summary["compliance_outcome"] == "UNDETERMINED"


def test_partial_verified_dossier_is_in_progress():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    value_json={"observed_value": "captured"},
                    examination_state="EXAMINED",
                    conformance_result="PASS",
                )
            ),
            entry(
                item_value=item(item_key="GENERAL.SECOND"),
                policy_value=policy(
                    item_key="GENERAL.SECOND",
                    sort_order=20,
                ),
            ),
        ]
    )
    assert summary["evaluation_status"] == "IN_PROGRESS"
    assert summary["compliance_outcome"] == "UNDETERMINED"


def test_completion_request_with_missing_item_is_incomplete():
    summary = summarize_construction(
        [entry()],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "INCOMPLETE"
    assert summary["missing_item_keys"] == ["GENERAL.IDENTITY"]


def test_all_required_pass_is_complete_compliant():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    value_json={"observed_value": "captured"},
                    examination_state="EXAMINED",
                    conformance_result="PASS",
                )
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "COMPLIANT"


def test_fail_is_answered_and_complete_noncompliant():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    value_json={"observed_value": "captured"},
                    examination_state="EXAMINED",
                    conformance_result="FAIL",
                )
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "COMPLETE"
    assert summary["compliance_outcome"] == "NONCOMPLIANT"


def test_known_failure_remains_noncompliant_while_other_item_missing():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    value_json={"observed_value": "captured"},
                    examination_state="EXAMINED",
                    conformance_result="FAIL",
                )
            ),
            entry(
                item_value=item(item_key="GENERAL.SECOND"),
                policy_value=policy(
                    item_key="GENERAL.SECOND",
                    sort_order=20,
                ),
            ),
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "INCOMPLETE"
    assert summary["compliance_outcome"] == "NONCOMPLIANT"


def test_required_evidence_blocks_completion_until_present():
    required = policy(evidence_required=True)
    observed = item(
        value_json={"observed_value": "captured"},
        examination_state="EXAMINED",
        conformance_result="PASS",
    )
    missing = summarize_construction(
        [
            entry(
                item_value=observed,
                policy_value=required,
                evidence=0,
            )
        ],
        completion_requested=True,
    )
    assert missing["evaluation_status"] == "INCOMPLETE"

    complete = summarize_construction(
        [
            entry(
                item_value=observed,
                policy_value=required,
                evidence=1,
            )
        ],
        completion_requested=True,
    )
    assert complete["evaluation_status"] == "COMPLETE"


def test_required_value_key_blocks_completion():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    value_json={},
                    examination_state="EXAMINED",
                    conformance_result="PASS",
                )
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "INCOMPLETE"


def test_explicit_review_state_prevents_completion():
    summary = summarize_construction(
        [
            entry(
                item_value=item(
                    examination_state="REVIEW_REQUIRED",
                    conformance_result="UNDETERMINED",
                )
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"


def test_malformed_rule_is_review_required():
    summary = summarize_construction(
        (),
        malformed_rule_ids=("abc",),
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert summary["blockers"] == ["abc:INVALID_CONSTRUCTION_POLICY"]


def test_zero_required_items_cannot_be_completed_as_compliant():
    summary = summarize_construction(
        [
            entry(
                policy_value=policy(required=False),
                item_value=item(
                    value_json={"observed_value": "captured"},
                    examination_state="EXAMINED",
                    conformance_result="PASS",
                ),
            )
        ],
        completion_requested=True,
    )
    assert summary["evaluation_status"] == "REVIEW_REQUIRED"
    assert "REG-15:NO_REQUIRED_SECTION16_ITEMS" in summary["blockers"]
