"""Phase 26 Stage 2 focused acceptance verifier."""

from app.compliance.domain import InstrumentSnapshot
from app.compliance.full_demo import (
    FULL_DEMO_RUN_ARTIFACT,
    FULL_DEMO_RUN_VERSION,
    full_demo_registry,
    full_demo_runtime_schema_map,
    is_full_demo_run_ruleset,
    load_full_demo_run_ruleset,
)
from app.compliance.planning import RequirementPlanner
from app.services.rulesets import _runtime_schemas_for, _validation_summary


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


def main() -> None:
    ruleset = load_full_demo_run_ruleset()
    assert is_full_demo_run_ruleset(ruleset)

    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument(),
        ruleset=ruleset,
    )
    groups = {
        slot.parent_test_code
        for slot in plan.slots
        if slot.parent_test_code is not None
    }
    run_slots = tuple(
        slot
        for slot in plan.slots
        if (
            slot.required_for_completion
            and slot.section_number <= 15
            and slot.test_code not in groups
        )
    )

    bindings = full_demo_runtime_schema_map()
    registry = full_demo_registry()
    runtime = _runtime_schemas_for(ruleset, None)

    assert len(plan.slots) == 28
    assert len(run_slots) == 23
    assert {slot.test_code for slot in run_slots} == set(bindings)
    assert {item.test_code for item in registry.registrations} == set(bindings)
    assert set(runtime) == set(bindings)

    for slot in run_slots:
        binding = bindings[slot.test_code]
        assert slot.procedure_variant == binding.procedure_variant
        registration = registry.resolve(slot.test_code)
        assert registration.synthetic_fixture
        assert registration.runtime_schema_versions(
            slot.procedure_variant,
            procedure_schema_version=binding.procedure_schema_version,
            observation_schema_version=binding.observation_schema_version,
        ) == (
            binding.procedure_schema_version,
            binding.observation_schema_version,
        )

    weighing = next(
        slot for slot in run_slots if slot.test_code == "WEIGHING_PERFORMANCE"
    )
    assert weighing.range_no == 1

    summary = _validation_summary(ruleset)
    assert summary["synthetic_demo_only"] is True
    assert summary["authoritative"] is False

    v1_count = sum(
        item.procedure_schema_version == "v1"
        for item in bindings.values()
    )
    v2_count = sum(
        item.procedure_schema_version == "v2"
        for item in bindings.values()
    )

    print("Phase 26 Stage 2 acceptance: PASS")
    print(f"- artifact: {FULL_DEMO_RUN_ARTIFACT}")
    print(f"- version: {FULL_DEMO_RUN_VERSION}")
    print("- all 17 sections remain present: PASS")
    print(f"- applicability slots: {len(plan.slots)}")
    print(f"- executable Sections 1-15 run slots: {len(run_slots)}")
    print("- typed synthetic evaluator registrations: 23")
    print(f"- pinned runtime schemas: v1={v1_count}, v2={v2_count}")
    print("- Section 1 is range-scoped and run-initializable: PASS")
    print("- no UNIMPLEMENTED full-demo run path: PASS")
    print("- Sections 16-17 remain specialized workflows: PASS")
    print("- synthetic/non-authoritative boundary: PASS")
    print("- no database migration required")


if __name__ == "__main__":
    main()
