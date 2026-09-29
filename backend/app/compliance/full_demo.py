"""Phase 26 Stage 1 — full-flow synthetic SIH demonstration ruleset.

The artifact is intentionally non-authoritative. It reuses the structural shape
of the Phase 25 verified staging package only as a deterministic demo template,
then replaces every source/verification identity with synthetic fixture
provenance and forces session applicability to REQUIRED for the full 17-section
walkthrough.

It must remain DRAFT, can never be activated, and must never feed regulatory
review, approval, or official report issuance.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.compliance.demo import (
    DEMO_SOURCE_REFERENCE,
    FULL_DEMO_EDITION,
    FULL_DEMO_STANDARD_NAME,
    FULL_DEMO_VERSION,
    is_demo_ruleset,
)
from app.compliance.engine import synthetic_artifact
from app.compliance.ruleset import RuleSet, load_ruleset

FULL_DEMO_ARTIFACT = "sih26035_full_flow_demo_v1"

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "phase25_verified_v1_staging"

SOURCE = {
    "part": "SYNTHETIC",
    "edition": FULL_DEMO_EDITION,
    "identity": "SYNTHETIC TEST FIXTURE — SIH26035 FULL-FLOW DEMO ONLY",
    "clause": "demo-full-flow-only",
    "digest": "f" * 64,
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


def _verification(key: str) -> dict:
    return {
        "status": "VERIFIED",
        "verified_by": "SIH26035 FULL-FLOW DEMO FIXTURE — NOT REGULATORY VERIFIER",
        "verified_at": "2000-01-01T00:00:00Z",
        "evidence": f"SYNTHETIC-FULL-FLOW-DEMO:{key}",
    }


def _synthetic_parameters(rule) -> list[dict]:
    parameters = [item.model_dump(mode="python") for item in rule.parameters]
    if any(item["value"] is None for item in parameters):
        raise ValueError(f"Full-flow demo template contains unresolved parameter: {rule.key}")

    if rule.kind != "applicability_policy_v1":
        return parameters

    matches = [item for item in parameters if item["name"] == "POLICY_JSON"]
    if len(matches) != 1 or not isinstance(matches[0]["value"], str):
        raise ValueError(f"Applicability policy is malformed: {rule.key}")

    policy = json.loads(matches[0]["value"])
    if policy.get("schema_version") != "v1" or not policy.get("scenarios"):
        raise ValueError(f"Applicability policy is not a usable v1 policy: {rule.key}")

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


def _synthetic_rule(rule) -> dict:
    data = rule.model_dump(mode="python")
    data["source"] = SOURCE
    data["verification"] = _verification(rule.key)
    data["blockers"] = []
    data["parameters"] = _synthetic_parameters(rule)
    return data


def _synthetic_test(test) -> dict:
    data = test.model_dump(mode="python")
    data["source"] = SOURCE
    data["verification"] = _verification(test.code)
    return data


def _synthetic_checklist(item) -> dict:
    data = item.model_dump(mode="python")
    data["source"] = SOURCE
    data["verification"] = _verification(item.key)
    data["applicability"] = CHECKLIST_APPLICABILITY
    if data["evidence_required"] is None:
        data["evidence_required"] = False
    return data


def load_full_demo_ruleset() -> RuleSet:
    """Return the immutable full-flow synthetic artifact."""

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
                "standard_name": FULL_DEMO_STANDARD_NAME,
                "edition": FULL_DEMO_EDITION,
                "version": FULL_DEMO_VERSION,
                "standard_parts": [SOURCE],
                "supported_test_codes": list(
                    template.metadata.supported_test_codes
                ),
                "source_reference": DEMO_SOURCE_REFERENCE,
            },
            "rules": [_synthetic_rule(item) for item in template.rules],
            "tests": [_synthetic_test(item) for item in template.tests],
            "checklist": [
                _synthetic_checklist(item) for item in template.checklist
            ],
        }
    )

    sections = {item.section for item in ruleset.tests}
    if sections != set(range(1, 18)):
        raise ValueError("Full-flow demo artifact must expose Sections 1-17")
    if not synthetic_artifact(ruleset) or not is_demo_ruleset(ruleset):
        raise ValueError("Full-flow demo artifact lost its synthetic boundary")
    return ruleset


def is_full_demo_ruleset(ruleset: RuleSet) -> bool:
    metadata = ruleset.metadata
    return bool(
        metadata.version == FULL_DEMO_VERSION
        and metadata.edition == FULL_DEMO_EDITION
        and metadata.standard_name == FULL_DEMO_STANDARD_NAME
        and metadata.source_reference == DEMO_SOURCE_REFERENCE
        and synthetic_artifact(ruleset)
    )
