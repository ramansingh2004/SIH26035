"""Phase 25 Fix 2 checklist policy/schema regression contracts."""

from app.compliance.checklist import ChecklistApplicabilityPolicy, ChecklistApplicabilityPolicyV2
from app.compliance.domain import InstrumentSnapshot
from app.compliance.ruleset import ChecklistDefinition, load_ruleset
from app.schemas.master_data import InstrumentMetadata
from domain_tests.fixtures.synthetic import SOURCE, VERIFICATION, instrument


def test_v1_checklist_policy_contract_remains_accepted():
    policy = ChecklistApplicabilityPolicy(schema_version="v1", conditions=(), 
                                          when_match="REQUIRED", 
                                          when_not_match="NOT_APPLICABLE",
                                            match_reason="SYNTHETIC TEST FIXTURE ONLY", 
                                            no_match_reason="SYNTHETIC TEST FIXTURE ONLY")
    assert policy.schema_version == "v1"


def test_ruleset_checklist_definition_accepts_v2_without_promoting_candidate():
    definition = ChecklistDefinition.model_validate({
        "key": "SYNTHETIC_V2",
        "group": "GENERAL",
        "text": "SYNTHETIC TEST FIXTURE ONLY",
        "source": SOURCE,
        "verification": VERIFICATION,
        "applicability": {
            "schema_version": "v2",
            "cases": [{"when": {"kind": "always"}, "decision": "REQUIRED", 
                       "reason": "SYNTHETIC TEST FIXTURE ONLY"}],
        },
        "evidence_required": False,
    })
    assert isinstance(definition.applicability, ChecklistApplicabilityPolicyV2)
    candidate = load_ruleset()
    assert candidate.metadata.version == "candidate-v1"
    assert candidate.metadata.supported_test_codes == ()
    assert all(item.verification.status == "TODO_REGULATORY_VALIDATION"
                for item in candidate.checklist)


def test_new_checklist_facts_are_optional_unknown_master_metadata():
    metadata = InstrumentMetadata()
    assert metadata.printing_device_present is None
    assert metadata.extended_indication_available is None
    assert metadata.embedded_software_present is None
    assert metadata.loadable_software_present is None
    snapshot = instrument()
    for name in ("printing_device_present", "extended_indication_available", 
                 "embedded_software_present", "loadable_software_present"):
        assert name in InstrumentSnapshot.model_fields
        assert getattr(snapshot, name) is None
