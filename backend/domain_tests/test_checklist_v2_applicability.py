"""Phase 25 Fix 2: deterministic checklist applicability v2 contracts."""

from app.compliance.checklist import ChecklistEngine, ChecklistRuleInput
from domain_tests.fixtures.synthetic import instrument


def rule(expression):
    return ChecklistRuleInput(
        rule_key="SYNTHETIC_CHECKLIST_V2",
        group_code="GENERAL",
        validation_status="VERIFIED",
        applicability_expression=expression,
        evidence_required=False,
    )


def policy(when):
    return {
        "schema_version": "v2",
        "cases": [
            {
                "when": when,
                "decision": "REQUIRED",
                "reason": "SYNTHETIC TEST FIXTURE ONLY - matched",
            },
            {
                "when": {"kind": "always"},
                "decision": "NOT_APPLICABLE",
                "reason": "SYNTHETIC TEST FIXTURE ONLY - excluded",
            },
        ],
    }


def applicability(snapshot, when):
    return ChecklistEngine.applicability(snapshot, rule(policy(when)))


def test_v2_boolean_fact_preserves_unknown_false_and_true():
    when = {"kind": "boolean", "feature": "printing_device_present", "expected": True}
    assert applicability(instrument
                         (printing_device_present=None), when).applicability == "REQUIRES_REVIEW"
    assert applicability(instrument
                         (printing_device_present=False), when).applicability == "NOT_APPLICABLE"
    assert applicability(instrument(printing_device_present=True), when).applicability == "REQUIRED"


def test_v2_presence_fact_covers_tare_zero_and_software_identification():
    for feature, value in (("tare_type", "SUBTRACTIVE"), 
                           ("zero_setting_type", "SEMI_AUTOMATIC"),("software_identifier", "SW-1")):
        when = {"kind": "present", "feature": feature, "expected": True}
        assert applicability(instrument(**{feature: None}), when).applicability == "REQUIRES_REVIEW"
        assert applicability(instrument(**{feature: value}), when).applicability == "REQUIRED"


def test_v2_interface_predicate_is_three_valued_and_specific():
    when = {"kind": "interface_choice", "attribute": "interface_type", "expected": "RS232"}
    assert applicability(instrument(interfaces=None), when).applicability == "REQUIRES_REVIEW"
    assert applicability(instrument(interfaces=[]), when).applicability == "NOT_APPLICABLE"
    assert applicability(instrument(interfaces=[
        {"name": "PORT1", "interface_type": None}]), when).applicability == "REQUIRES_REVIEW"
    assert applicability(instrument(interfaces=[
        {"name": "PORT1", "interface_type": "USB"}]), when).applicability == "NOT_APPLICABLE"
    assert applicability(instrument(interfaces=[
        {"name": "PORT1", "interface_type": "RS232"}]), when).applicability == "REQUIRED"


def test_v2_interface_boolean_and_peripheral_predicates():
    external = {"kind": "interface_boolean", "attribute": "externally_accessible", "expected": True}
    assert applicability(instrument(interfaces=[
        {"name": "PORT1", "externally_accessible": True}]), external).applicability == "REQUIRED"
    printer = {"kind": "peripheral", "expected": "PRINTER"}
    assert applicability(instrument(peripherals=None), printer).applicability == "REQUIRES_REVIEW"
    assert applicability(instrument(peripherals=[]), printer).applicability == "NOT_APPLICABLE"
    assert applicability(instrument(peripherals=[
        "DISPLAY"]), printer).applicability == "NOT_APPLICABLE"
    assert applicability(instrument(peripherals=["PRINTER"]), printer).applicability == "REQUIRED"


def test_v2_nested_predicate_distinguishes_embedded_and_loadable_software():
    when = {
        "kind": "all",
        "conditions": [
            {"kind": "boolean", "feature": "is_software_controlled", "expected": True},
            {
                "kind": "any",
                "conditions": [
                    {"kind": "boolean", "feature": "embedded_software_present", "expected": True},
                    {"kind": "boolean", "feature": "loadable_software_present", "expected": True},
                ],
            },
        ],
    }
    assert applicability(instrument(is_software_controlled=True, 
                                    embedded_software_present=None, 
                                    loadable_software_present=False), 
                                    when).applicability == "REQUIRES_REVIEW"
    assert applicability(instrument(is_software_controlled=True, 
                                    embedded_software_present=False, 
                                    loadable_software_present=True), 
                                    when).applicability == "REQUIRED"
    assert applicability(instrument(is_software_controlled=False, 
                                    embedded_software_present=None, 
                                    loadable_software_present=None), 
                                    when).applicability == "NOT_APPLICABLE"
