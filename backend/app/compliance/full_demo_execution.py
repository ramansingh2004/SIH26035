"""Phase 26 Stage 3 static full-flow execution artifact.

The JSON files loaded here are generated from existing deterministic synthetic
domain fixtures by ``scripts.build_phase26_stage3_execution``.  Runtime loading
does not import test modules.

V3 is a software-exercise artifact only.  It intentionally combines procedure
branches that would not all be applicable to one real regulatory instrument.
It can never become authoritative or feed official review/report paths.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.compliance.demo import (
    DEMO_SOURCE_REFERENCE,
    FULL_DEMO_EXECUTION_EDITION,
    FULL_DEMO_EXECUTION_STANDARD_NAME,
    FULL_DEMO_EXECUTION_VERSION,
)
from app.compliance.domain import InstrumentSnapshot
from app.compliance.engine import synthetic_artifact
from app.compliance.full_demo import FullDemoRuntimeBinding
from app.compliance.ruleset import RuleSet

FULL_DEMO_EXECUTION_ARTIFACT = "sih26035_full_flow_demo_v3"

ROOT = Path(__file__).with_name("demo_artifacts")
RULESET_PATH = ROOT / "phase26_full_demo_v3_ruleset.json"
DATA_PATH = ROOT / "phase26_full_demo_v3_data.json"


def _read(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(
            f"Phase 26 Stage 3 generated artifact is missing: {path.name}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_full_demo_execution_ruleset() -> RuleSet:
    ruleset = RuleSet.model_validate(_read(RULESET_PATH))
    metadata = ruleset.metadata
    if (
        metadata.version != FULL_DEMO_EXECUTION_VERSION
        or metadata.edition != FULL_DEMO_EXECUTION_EDITION
        or metadata.standard_name != FULL_DEMO_EXECUTION_STANDARD_NAME
        or metadata.source_reference != DEMO_SOURCE_REFERENCE
        or not synthetic_artifact(ruleset)
    ):
        raise ValueError("Invalid Phase 26 Stage 3 execution artifact identity")
    return ruleset


def is_full_demo_execution_ruleset(ruleset: RuleSet) -> bool:
    metadata = ruleset.metadata
    return bool(
        metadata.version == FULL_DEMO_EXECUTION_VERSION
        and metadata.edition == FULL_DEMO_EXECUTION_EDITION
        and metadata.standard_name == FULL_DEMO_EXECUTION_STANDARD_NAME
        and metadata.source_reference == DEMO_SOURCE_REFERENCE
        and synthetic_artifact(ruleset)
    )


def load_full_demo_execution_data() -> dict:
    data = _read(DATA_PATH)
    if (
        data.get("schema_version") != 1
        or data.get("artifact") != FULL_DEMO_EXECUTION_ARTIFACT
        or data.get("ruleset_version") != FULL_DEMO_EXECUTION_VERSION
        or data.get("evaluation_context") != "SYNTHETIC"
        or len(data.get("datasets", [])) != 23
    ):
        raise ValueError("Invalid Phase 26 Stage 3 execution data manifest")
    return data


def full_demo_execution_instrument() -> InstrumentSnapshot:
    return InstrumentSnapshot.model_validate(
        load_full_demo_execution_data()["instrument_snapshot"]
    )


def full_demo_execution_dataset(test_code: str) -> dict:
    rows = [
        item
        for item in load_full_demo_execution_data()["datasets"]
        if item["test_code"] == test_code
    ]
    if len(rows) != 1:
        raise KeyError(test_code)
    return rows[0]


def full_demo_execution_runtime_schema_map() -> dict[str, FullDemoRuntimeBinding]:
    result = {}
    for item in load_full_demo_execution_data()["datasets"]:
        context = item["procedure_context"]
        observations = item["observation_batch"]
        result[item["test_code"]] = FullDemoRuntimeBinding(
            procedure_variant=context["procedure_variant"],
            procedure_schema_version=context["procedure_schema_version"],
            observation_schema_version=observations[
                "observation_schema_version"
            ],
        )
    return result
