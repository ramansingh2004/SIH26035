from app.compliance.domain import InstrumentSnapshot
from app.compliance.engine import synthetic_artifact
from app.compliance.full_demo import (
    FULL_DEMO_ARTIFACT,
    is_full_demo_ruleset,
    load_full_demo_ruleset,
)
from app.compliance.planning import RequirementPlanner


def demo_instrument() -> InstrumentSnapshot:
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
            "range_type": "SINGLE",
            "indication_type": "DIGITAL",
            "is_self_indicating": True,
            "is_electronic": True,
            "is_software_controlled": True,
            "is_portable": False,
            "is_mobile": False,
            "load_receptor_type": "PLATFORM",
            "support_point_count": 4,
            "tare_type": "SUBTRACTIVE",
            "maximum_tare_g": "10000",
            "zero_setting_type": "AUTOMATIC_AND_SEMI_AUTOMATIC",
            "zero_tracking_available": True,
            "level_indicator_available": True,
            "automatic_tilt_sensor": False,
            "power_supply_type": "AC",
            "nominal_voltage": "230",
            "min_voltage": "207",
            "max_voltage": "253",
            "declared_temp_min_c": "-10",
            "declared_temp_max_c": "40",
            "software_identifier": "FULL-DEMO-1.0",
            "is_direct_sales": False,
            "is_price_computing": False,
            "is_labeling": False,
            "data_storage_device_present": True,
            "printing_device_present": True,
            "extended_indication_available": True,
            "embedded_software_present": True,
            "loadable_software_present": False,
            "interfaces": [],
            "peripherals": [],
            "components": [],
            "battery_charging_during_operation": False,
            "vehicle_powered": True,
            "conducted_rf_path_available": True,
            "vehicle_power_details": "Synthetic full-flow demo supply",
            "declared_operating_conditions": "Synthetic SIH full-flow demo only",
            "declared_installation": "Synthetic laboratory demonstration",
        }
    )


def test_full_demo_artifact_is_synthetic_and_immutable_in_identity():
    ruleset = load_full_demo_ruleset()

    assert FULL_DEMO_ARTIFACT == "sih26035_full_flow_demo_v1"
    assert synthetic_artifact(ruleset)
    assert is_full_demo_ruleset(ruleset)
    assert ruleset.metadata.version == "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V1"
    assert ruleset.metadata.source_reference == "SYNTHETIC TEST FIXTURE ONLY"
    assert {item.section for item in ruleset.tests} == set(range(1, 18))

    snapshot = ruleset.model_dump(mode="json")
    text = str(snapshot)
    assert "Dr. Y.G" not in text
    assert "NOT REGULATORY VERIFIER" in text


def test_full_demo_planner_makes_every_section_exercisable():
    ruleset = load_full_demo_ruleset()
    plan = RequirementPlanner().plan(
        instrument_snapshot=demo_instrument(),
        ruleset=ruleset,
    )

    assert plan.applicability_confirmable
    assert plan.slots
    assert {slot.section_number for slot in plan.slots} == set(range(1, 18))
    assert all(slot.decision.applicability == "REQUIRED" for slot in plan.slots)
    assert all(slot.required_for_completion for slot in plan.slots)

    assert "WEIGHING_PERFORMANCE" in ruleset.metadata.supported_test_codes
    assert "ENDURANCE" in ruleset.metadata.supported_test_codes
    assert "CONSTRUCTION_EXAMINATION" not in ruleset.metadata.supported_test_codes
    assert "CHECKLIST" not in ruleset.metadata.supported_test_codes


def test_full_demo_contains_specialized_section16_and_section17_catalogs():
    ruleset = load_full_demo_ruleset()

    construction = [
        rule
        for rule in ruleset.rules
        if rule.section == 16 and rule.kind == "construction_item_v1"
    ]
    assert construction
    assert ruleset.checklist
    assert all(item.verification.status == "VERIFIED" for item in ruleset.checklist)
    assert all(item.evidence_required is not None for item in ruleset.checklist)
