"""Phase 26 Stage 6 persisted full-session demo seed plan.

The plan adapts the immutable V3 execution matrix to the persisted testing
model. Client-owned procedure context deliberately excludes server-owned
equipment, environment and evidence associations; Stage 6 materializes those
as dedicated synthetic persistence records before invoking the normal
evaluation engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.compliance.full_demo_execution import load_full_demo_execution_data


@dataclass(frozen=True)
class FullDemoRunSeed:
    test_code: str
    procedure_context: dict
    client_procedure_context: dict
    observation_batch: dict
    environment: tuple[dict, ...]
    equipment: tuple[dict, ...]
    evidence_hashes: tuple[str, ...]


def full_demo_run_seeds() -> tuple[FullDemoRunSeed, ...]:
    data = load_full_demo_execution_data()
    seeds = []
    for dataset in data["datasets"]:
        context = dict(dataset["procedure_context"])
        client = dict(context)
        client["equipment"] = []
        client["environment"] = []
        client["evidence_hashes"] = []
        seeds.append(
            FullDemoRunSeed(
                test_code=dataset["test_code"],
                procedure_context=context,
                client_procedure_context=client,
                observation_batch=dataset["observation_batch"],
                environment=tuple(context.get("environment", ())),
                equipment=tuple(context.get("equipment", ())),
                evidence_hashes=tuple(context.get("evidence_hashes", ())),
            )
        )

    seeds.sort(key=lambda item: item.test_code)
    if len(seeds) != 23 or len({item.test_code for item in seeds}) != 23:
        raise ValueError("Stage 6 requires exactly 23 unique V3 run seeds")

    counts = full_demo_traceability_counts(seeds)
    expected = {
        "runs": 23,
        "observations": 92,
        "environment": 23,
        "equipment": 24,
        "evidence": 23,
        "calibration_evidence": 2,
    }
    if counts != expected:
        raise ValueError(f"Unexpected V3 persisted traceability counts: {counts}")
    return tuple(seeds)


def full_demo_traceability_counts(
    seeds: tuple[FullDemoRunSeed, ...] | None = None,
) -> dict[str, int]:
    values = seeds if seeds is not None else full_demo_run_seeds()
    return {
        "runs": len(values),
        "observations": sum(
            len(item.observation_batch["rows"]) for item in values
        ),
        "environment": sum(len(item.environment) for item in values),
        "equipment": sum(len(item.equipment) for item in values),
        "evidence": sum(len(item.evidence_hashes) for item in values),
        "calibration_evidence": sum(
            1
            for item in values
            for equipment in item.equipment
            if equipment.get("certificate_content_hash")
        ),
    }
