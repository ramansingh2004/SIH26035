"""Phase 26 full-flow synthetic SIH demonstration rulesets.

V1 is the immutable Stage 1 applicability/catalog artifact.
V2 is the Stage 2 run-ready artifact.  It keeps the same synthetic-only
regulatory boundary while pinning every executable Sections 1-15 leaf test to a
real evaluator procedure variant and runtime schema.

Neither artifact is authoritative, activatable, or eligible for regulatory
review, approval, or official report issuance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from app.compliance.demo import (
    DEMO_SOURCE_REFERENCE,
    FULL_DEMO_EDITION,
    FULL_DEMO_RUN_EDITION,
    FULL_DEMO_RUN_STANDARD_NAME,
    FULL_DEMO_RUN_VERSION,
    FULL_DEMO_STANDARD_NAME,
    FULL_DEMO_VERSION,
    is_demo_ruleset,
)
from app.compliance.engine import synthetic_artifact
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.ruleset import RuleSet, load_ruleset

FULL_DEMO_ARTIFACT = "sih26035_full_flow_demo_v1"
FULL_DEMO_RUN_ARTIFACT = "sih26035_full_flow_demo_v2"

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "phase25_verified_v1_staging"

SOURCE = {
    "part": "SYNTHETIC",
    "edition": FULL_DEMO_EDITION,
    "identity": "SYNTHETIC TEST FIXTURE — SIH26035 FULL-FLOW DEMO ONLY",
    "clause": "demo-full-flow-only",
    "digest": "f" * 64,
}

RUN_SOURCE = {
    "part": "SYNTHETIC",
    "edition": FULL_DEMO_RUN_EDITION,
    "identity": "SYNTHETIC TEST FIXTURE — SIH26035 FULL-FLOW RUN DEMO ONLY",
    "clause": "demo-full-flow-run-only",
    "digest": "2" * 64,
}

CHECKLIST_APPLICABILITY = {
    "schema_version": "v1",
    "mode": "ALL",
    "conditions": [],
    "when_match": "REQUIRED",
    "when_not_match": "REQUIRED",
    "match_reason": "SYNTHETIC FULL-FLOW DEMO ONLY — checklist row selected",
    "no_match_reason": "SYNTHETIC FULL-FLOW DEMO ONLY — checklist row selected",
}


@dataclass(frozen=True)
class FullDemoRuntimeBinding:
    procedure_variant: str
    procedure_schema_version: str
    observation_schema_version: str


_RUNTIME_BINDING_ROWS = (
    ("WEIGHING_PERFORMANCE", "DIGITAL_PRE_ROUNDING", "v2", "v2"),
    ("TEMPERATURE_ZERO", "TEMPERATURE_SEQUENCE", "v1", "v1"),
    ("ECCENTRICITY", "WEIGHTS", "v1", "v1"),
    ("DISCRIMINATION", "DIGITAL", "v1", "v1"),
    ("SENSITIVITY", "NON_SELF_INDICATING", "v1", "v1"),
    ("REPEATABILITY", "DIGITAL_PRE_ROUNDING", "v1", "v1"),
    ("ZERO_RETURN", "ZERO_RETURN", "v2", "v2"),
    ("CREEP", "SHORT", "v2", "v2"),
    ("STABILITY_EQUILIBRIUM", "FUNCTIONAL", "v2", "v2"),
    ("TILTING", "LEVEL_INDICATOR", "v2", "v2"),
    ("TARE", "DIGITAL_PRE_ROUNDING", "v2", "v2"),
    ("WARM_UP", "WARM_UP", "v2", "v2"),
    ("VOLTAGE_VARIATION", "AC_MAINS", "v2", "v2"),
    (
        "DISTURBANCE_VOLTAGE_DIP",
        "AC_MAINS_DIPS_INTERRUPTION",
        "v2",
        "v2",
    ),
    ("DISTURBANCE_BURST", "BURST_LINES", "v2", "v2"),
    ("DISTURBANCE_SURGE", "SURGE_LINES", "v2", "v2"),
    ("DISTURBANCE_ESD", "ESD", "v2", "v2"),
    ("DISTURBANCE_RADIATED_RF", "RADIATED_RF", "v2", "v2"),
    ("DISTURBANCE_CONDUCTED_RF", "CONDUCTED_RF", "v2", "v2"),
    (
        "DISTURBANCE_VEHICLE_SUPPLY",
        "SUPPLY_LINE_CONDUCTION",
        "v2",
        "v2",
    ),
    ("DAMP_HEAT", "STEADY_STATE", "v2", "v2"),
    ("SPAN_STABILITY", "LONG_DURATION", "v2", "v2"),
    ("ENDURANCE", "MECHANICAL_CYCLING", "v2", "v2"),
)


def full_demo_runtime_schema_map() -> dict[str, FullDemoRuntimeBinding]:
    return {
        code: FullDemoRuntimeBinding(
            procedure_variant=variant,
            procedure_schema_version=procedure_version,
            observation_schema_version=observation_version,
        )
        for code, variant, procedure_version, observation_version in _RUNTIME_BINDING_ROWS
    }


def _verification(key: str) -> dict:
    return {
        "status": "VERIFIED",
        "verified_by": "SIH26035 FULL-FLOW DEMO FIXTURE — NOT REGULATORY VERIFIER",
        "verified_at": "2000-01-01T00:00:00Z",
        "evidence": f"SYNTHETIC-FULL-FLOW-DEMO:{key}",
    }


def _synthetic_parameters(rule, *, run_ready: bool) -> list[dict]:
    parameters = [item.model_dump(mode="python") for item in rule.parameters]
    if any(item["value"] is None for item in parameters):
        raise ValueError(
            f"Full-flow demo template contains unresolved parameter: {rule.key}"
        )

    if rule.kind != "applicability_policy_v1":
        return parameters

    matches = [item for item in parameters if item["name"] == "POLICY_JSON"]
    if len(matches) != 1 or not isinstance(matches[0]["value"], str):
        raise ValueError(f"Applicability policy is malformed: {rule.key}")

    policy = json.loads(matches[0]["value"])
    if policy.get("schema_version") != "v1" or not policy.get("scenarios"):
        raise ValueError(
            f"Applicability policy is not a usable v1 policy: {rule.key}"
        )

    code = rule.key.removeprefix("APP_")
    if run_ready:
        binding = full_demo_runtime_schema_map().get(code)
        if binding is not None:
            scenario = policy["scenarios"][0]["scenario"]
            policy["scenarios"] = [
                {
                    "procedure_variant": binding.procedure_variant,
                    "scenario": scenario,
                }
            ]
            if code == "WEIGHING_PERFORMANCE":
                # Existing run creation initializes Section 1 directly from the
                # applicability slot and therefore requires an explicit range.
                policy["scope"] = "EACH_RANGE"

    policy["cases"] = [
        {
            "when": {"kind": "always"},
            "decision": "REQUIRED",
            "reason": (
                "SYNTHETIC FULL-FLOW DEMO ONLY — required to exercise the "
                "complete 17-section workflow"
            ),
        }
    ]
    matches[0]["value"] = json.dumps(
        policy,
        sort_keys=True,
        separators=(",", ":"),
    )
    return parameters


def _synthetic_rule(rule, *, source: dict, run_ready: bool) -> dict:
    data = rule.model_dump(mode="python")
    data["source"] = source
    data["verification"] = _verification(rule.key)
    data["blockers"] = []
    data["parameters"] = _synthetic_parameters(rule, run_ready=run_ready)
    return data


def _synthetic_test(test, *, source: dict) -> dict:
    data = test.model_dump(mode="python")
    data["source"] = source
    data["verification"] = _verification(test.code)
    return data


def _synthetic_checklist(item, *, source: dict) -> dict:
    data = item.model_dump(mode="python")
    data["source"] = source
    data["verification"] = _verification(item.key)
    data["applicability"] = CHECKLIST_APPLICABILITY
    if data["evidence_required"] is None:
        data["evidence_required"] = False
    return data


def _build_full_demo_ruleset(
    *,
    version: str,
    edition: str,
    standard_name: str,
    source: dict,
    run_ready: bool,
) -> RuleSet:
    if not TEMPLATE_DIR.is_dir():
        raise RuntimeError(
            "Phase 25 verified staging template is missing; "
            "full-flow demo artifact cannot be constructed"
        )

    template = load_ruleset(TEMPLATE_DIR)
    ruleset = RuleSet.model_validate(
        {
            "metadata": {
                "schema_version": 1,
                "standard_code": "OIML_R76",
                "standard_name": standard_name,
                "edition": edition,
                "version": version,
                "standard_parts": [source],
                "supported_test_codes": list(
                    template.metadata.supported_test_codes
                ),
                "source_reference": DEMO_SOURCE_REFERENCE,
            },
            "rules": [
                _synthetic_rule(
                    item,
                    source=source,
                    run_ready=run_ready,
                )
                for item in template.rules
            ],
            "tests": [
                _synthetic_test(item, source=source)
                for item in template.tests
            ],
            "checklist": [
                _synthetic_checklist(item, source=source)
                for item in template.checklist
            ],
        }
    )

    sections = {item.section for item in ruleset.tests}
    if sections != set(range(1, 18)):
        raise ValueError("Full-flow demo artifact must expose Sections 1-17")
    if not synthetic_artifact(ruleset) or not is_demo_ruleset(ruleset):
        raise ValueError("Full-flow demo artifact lost its synthetic boundary")
    return ruleset


def load_full_demo_ruleset() -> RuleSet:
    """Return the immutable Stage 1 applicability/catalog artifact."""

    return _build_full_demo_ruleset(
        version=FULL_DEMO_VERSION,
        edition=FULL_DEMO_EDITION,
        standard_name=FULL_DEMO_STANDARD_NAME,
        source=SOURCE,
        run_ready=False,
    )


def load_full_demo_run_ruleset() -> RuleSet:
    """Return the Stage 2 run-ready synthetic full-flow artifact."""

    return _build_full_demo_ruleset(
        version=FULL_DEMO_RUN_VERSION,
        edition=FULL_DEMO_RUN_EDITION,
        standard_name=FULL_DEMO_RUN_STANDARD_NAME,
        source=RUN_SOURCE,
        run_ready=True,
    )


def is_full_demo_ruleset(ruleset: RuleSet) -> bool:
    metadata = ruleset.metadata
    return bool(
        metadata.version in {FULL_DEMO_VERSION, FULL_DEMO_RUN_VERSION}
        and metadata.source_reference == DEMO_SOURCE_REFERENCE
        and synthetic_artifact(ruleset)
    )


def is_full_demo_run_ruleset(ruleset: RuleSet) -> bool:
    metadata = ruleset.metadata
    return bool(
        metadata.version == FULL_DEMO_RUN_VERSION
        and metadata.edition == FULL_DEMO_RUN_EDITION
        and metadata.standard_name == FULL_DEMO_RUN_STANDARD_NAME
        and metadata.source_reference == DEMO_SOURCE_REFERENCE
        and synthetic_artifact(ruleset)
    )


def full_demo_registry() -> EvaluatorRegistry:
    """Clone all implemented evaluators into an isolated synthetic registry."""

    from app.compliance.suite import implemented_registry

    expected = set(full_demo_runtime_schema_map())
    registrations = tuple(
        replace(
            registration,
            implementation_version=(
                registration.implementation_version + "-full-demo-v2"
            ),
            synthetic_fixture=True,
        )
        for registration in implemented_registry().registrations
        if registration.test_code in expected
    )
    actual = {registration.test_code for registration in registrations}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            f"Full-demo evaluator registry mismatch; missing={missing}, extra={extra}"
        )
    return EvaluatorRegistry(registrations)
