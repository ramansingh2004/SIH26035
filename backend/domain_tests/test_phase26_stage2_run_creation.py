from app.compliance.domain import InstrumentSnapshot
from app.compliance.full_demo import (
    FULL_DEMO_RUN_ARTIFACT,
    full_demo_registry,
    full_demo_runtime_schema_map,
    is_full_demo_run_ruleset,
    load_full_demo_run_ruleset,
)
from app.compliance.planning import RequirementPlanner


def instrument() -> InstrumentSnapshot:
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


def executable_slots(plan):
    parent_groups = {
        slot.parent_test_code
        for slot in plan.slots
        if slot.parent_test_code is not None
    }
    return tuple(
        slot
        for slot in plan.slots
        if (
            slot.required_for_completion
            and slot.section_number <= 15
            and slot.test_code not in parent_groups
        )
    )


def test_stage2_run_ready_artifact_keeps_all_17_sections_and_28_slots():
    ruleset = load_full_demo_run_ruleset()
    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument(),
        ruleset=ruleset,
    )

    assert FULL_DEMO_RUN_ARTIFACT == "sih26035_full_flow_demo_v2"
    assert is_full_demo_run_ruleset(ruleset)
    assert plan.applicability_confirmable
    assert len(plan.slots) == 28
    assert {slot.section_number for slot in plan.slots} == set(range(1, 18))
    assert all(slot.decision.applicability == "REQUIRED" for slot in plan.slots)


def test_stage2_has_exactly_23_typed_executable_run_slots():
    ruleset = load_full_demo_run_ruleset()
    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument(),
        ruleset=ruleset,
    )
    slots = executable_slots(plan)
    bindings = full_demo_runtime_schema_map()
    registry = full_demo_registry()

    assert len(slots) == 23
    assert {slot.test_code for slot in slots} == set(bindings)
    assert len(registry.registrations) == 23
    assert all(registration.synthetic_fixture for registration in registry.registrations)

    for slot in slots:
        binding = bindings[slot.test_code]
        assert slot.procedure_variant == binding.procedure_variant

        registration = registry.resolve(slot.test_code)
        versions = registration.runtime_schema_versions(
            slot.procedure_variant,
            procedure_schema_version=binding.procedure_schema_version,
            observation_schema_version=binding.observation_schema_version,
        )
        assert versions == (
            binding.procedure_schema_version,
            binding.observation_schema_version,
        )
        assert "UNIMPLEMENTED" not in versions

    weighing = next(
        slot for slot in slots if slot.test_code == "WEIGHING_PERFORMANCE"
    )
    assert weighing.range_no == 1
    assert weighing.procedure_variant == "DIGITAL_PRE_ROUNDING"


def test_stage2_runtime_schema_pins_are_complete_and_explicit():
    bindings = full_demo_runtime_schema_map()

    assert len(bindings) == 23
    assert sum(
        item.procedure_schema_version == "v1"
        for item in bindings.values()
    ) == 5
    assert sum(
        item.procedure_schema_version == "v2"
        for item in bindings.values()
    ) == 18
    assert all(
        item.procedure_schema_version == item.observation_schema_version
        for item in bindings.values()
    )
