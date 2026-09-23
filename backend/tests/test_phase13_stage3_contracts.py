"""Phase 13 Stage 3 artifact-policy contract tests."""

from app.compliance.checklist import ChecklistApplicabilityPolicy
from app.compliance.ruleset import ChecklistDefinition
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION


def test_phase13_ruleset_accepts_versioned_verified_checklist_policy():
    item = ChecklistDefinition.model_validate(
        {
            "key": "SYNTHETIC_POLICY",
            "group": "GENERAL",
            "text": "SYNTHETIC TEST FIXTURE ONLY",
            "source": SOURCE,
            "verification": VERIFICATION,
            "applicability": {
                "schema_version": "v1",
                "mode": "ALL",
                "conditions": [],
                "when_match": "REQUIRED",
                "when_not_match": "NOT_APPLICABLE",
                "match_reason": "Synthetic match",
                "no_match_reason": "Synthetic exclusion",
            },
            "evidence_required": False,
        }
    )
    assert isinstance(item.applicability, ChecklistApplicabilityPolicy)
    assert item.verification.status == "VERIFIED"


def test_phase13_ruleset_still_accepts_candidate_todo_marker():
    item = ChecklistDefinition.model_validate(
        {
            "key": "CANDIDATE_POLICY",
            "group": "GENERAL",
            "text": "Candidate only",
            "source": SOURCE,
        }
    )
    assert item.applicability == "TODO_REGULATORY_VALIDATION"
    assert item.evidence_required is None
