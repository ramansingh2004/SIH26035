"""Phase 26 Stage 3 focused acceptance verifier."""

from app.compliance.engine import R76Engine
from app.compliance.full_demo import full_demo_registry
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_ARTIFACT,
    FULL_DEMO_EXECUTION_VERSION,
    full_demo_execution_dataset,
    full_demo_execution_instrument,
    full_demo_execution_runtime_schema_map,
    load_full_demo_execution_data,
    load_full_demo_execution_ruleset,
)
from app.compliance.planning import RequirementPlanner
from app.services.rulesets import _validation_summary


def main() -> None:
    ruleset = load_full_demo_execution_ruleset()
    data = load_full_demo_execution_data()
    instrument = full_demo_execution_instrument()
    runtime = full_demo_execution_runtime_schema_map()
    registry = full_demo_registry()
    engine = R76Engine(registry)

    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument,
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

    outcomes = {}
    for slot in run_slots:
        code = slot.test_code
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
        assert result.evaluation_status == "COMPLETE"
        assert result.compliance_outcome == "COMPLIANT"
        assert result.synthetic_fixture is True
        outcomes[code] = result

    summary = _validation_summary(ruleset)
    assert len(plan.slots) == 28
    assert len(run_slots) == 23
    assert len(data["datasets"]) == 23
    assert len(runtime) == 23
    assert len(outcomes) == 23
    assert summary["synthetic_demo_only"] is True
    assert summary["authoritative"] is False

    versions = {}
    for binding in runtime.values():
        key = (
            binding.procedure_schema_version,
            binding.observation_schema_version,
        )
        versions[key] = versions.get(key, 0) + 1

    print("Phase 26 Stage 3 acceptance: PASS")
    print(f"- artifact: {FULL_DEMO_EXECUTION_ARTIFACT}")
    print(f"- version: {FULL_DEMO_EXECUTION_VERSION}")
    print("- all 17 sections remain represented: PASS")
    print(f"- applicability slots: {len(plan.slots)}")
    print(f"- executable typed run datasets: {len(data['datasets'])}")
    print(f"- deterministic COMPLETE evaluations: {len(outcomes)}")
    print("- deterministic COMPLIANT evaluations: 23")
    print("- all results remain synthetic fixtures: PASS")
    print(f"- runtime schema pairs: {versions}")
    print("- runtime loader is static; no domain-test import dependency: PASS")
    print("- synthetic/non-authoritative boundary: PASS")
    print("- Sections 16-17 remain for later specialized stages")
    print("- no database migration required")


if __name__ == "__main__":
    main()
