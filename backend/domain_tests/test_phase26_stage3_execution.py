from app.compliance.engine import R76Engine
from app.compliance.full_demo import full_demo_registry
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_ARTIFACT,
    full_demo_execution_dataset,
    full_demo_execution_instrument,
    full_demo_execution_runtime_schema_map,
    is_full_demo_execution_ruleset,
    load_full_demo_execution_data,
    load_full_demo_execution_ruleset,
)
from app.compliance.planning import RequirementPlanner


def executable_slots(plan):
    groups = {
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
            and slot.test_code not in groups
        )
    )


def test_stage3_static_artifact_covers_all_execution_slots():
    ruleset = load_full_demo_execution_ruleset()
    data = load_full_demo_execution_data()
    instrument = full_demo_execution_instrument()
    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument,
        ruleset=ruleset,
    )
    slots = executable_slots(plan)

    assert FULL_DEMO_EXECUTION_ARTIFACT == "sih26035_full_flow_demo_v3"
    assert is_full_demo_execution_ruleset(ruleset)
    assert len(plan.slots) == 28
    assert len(slots) == 23
    assert len(data["datasets"]) == 23
    assert {slot.section_number for slot in plan.slots} == set(range(1, 18))
    assert {slot.test_code for slot in slots} == {
        item["test_code"] for item in data["datasets"]
    }


def test_stage3_every_dataset_matches_its_pinned_slot_and_schema():
    ruleset = load_full_demo_execution_ruleset()
    instrument = full_demo_execution_instrument()
    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument,
        ruleset=ruleset,
    )
    slots = {slot.test_code: slot for slot in executable_slots(plan)}
    runtime = full_demo_execution_runtime_schema_map()
    registry = full_demo_registry()

    assert set(runtime) == set(slots)

    for code, slot in slots.items():
        dataset = full_demo_execution_dataset(code)
        context_payload = dataset["procedure_context"]
        batch_payload = dataset["observation_batch"]
        binding = runtime[code]

        assert context_payload["procedure_variant"] == slot.procedure_variant
        assert context_payload["scenario"] == slot.scenario
        assert context_payload["range_no"] == slot.range_no
        assert binding.procedure_variant == slot.procedure_variant

        registration = registry.resolve(code)
        context = registration.contexts.parse(context_payload)
        batch = registration.observations.parse(
            test_code=code,
            protocol=batch_payload["protocol"],
            version=batch_payload["observation_schema_version"],
            rows=batch_payload["rows"],
        )
        assert context.procedure_schema_version == (
            binding.procedure_schema_version
        )
        assert batch.observation_schema_version == (
            binding.observation_schema_version
        )


def test_stage3_all_23_real_evaluator_mechanics_complete_compliant():
    ruleset = load_full_demo_execution_ruleset()
    instrument = full_demo_execution_instrument()
    registry = full_demo_registry()
    engine = R76Engine(registry)

    results = {}
    for code in sorted(ruleset.metadata.supported_test_codes):
        dataset = full_demo_execution_dataset(code)
        registration = registry.resolve(code)
        context = registration.contexts.parse(dataset["procedure_context"])
        batch_payload = dataset["observation_batch"]
        observations = registration.observations.parse(
            test_code=code,
            protocol=batch_payload["protocol"],
            version=batch_payload["observation_schema_version"],
            rows=batch_payload["rows"],
        )
        result = engine.evaluate(
            test_code=code,
            instrument_snapshot=instrument,
            procedure_context=context,
            observations=observations,
            ruleset=ruleset,
        )
        results[code] = result

    assert len(results) == 23
    assert all(item.evaluation_status == "COMPLETE" for item in results.values())
    assert all(
        item.compliance_outcome == "COMPLIANT"
        for item in results.values()
    )
    assert all(item.synthetic_fixture is True for item in results.values())
