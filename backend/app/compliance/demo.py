"""SIH26035 synthetic demonstration artifact.

This module supports Phase 23 SIH demonstrations only. It is not an OIML
ruleset, is never authoritative, cannot be activated, and cannot feed regulatory
review/final approval or official report generation.

The demo reuses the deterministic Section 1 mechanics with explicitly synthetic
policies. Sections 2–17 are explicitly NOT_APPLICABLE for this demonstration so
the complete 17-section UI remains visible without inventing regulatory rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.compliance.catalog import SECTIONS
from app.compliance.domain import EvaluationOutput
from app.compliance.evaluators import EvaluatorRegistration, EvaluatorRegistry
from app.compliance.ruleset import RuleSet
from app.compliance.weighing import WeighingEvaluator, section1_registration

DEMO_ARTIFACT = "sih26035_demo_v1"
DEMO_LAB_CODE = "SIH26035-DEMO"
DEMO_VERSION = "SYNTHETIC_TEST_SIH26035_DEMO_V1"
DEMO_EDITION = "SIH-DEMO-v1"
DEMO_SOURCE_REFERENCE = "SYNTHETIC TEST FIXTURE ONLY"

SOURCE = {
    "part": "SYNTHETIC",
    "edition": DEMO_EDITION,
    "identity": "SYNTHETIC TEST FIXTURE — SIH26035 DEMO ONLY",
    "clause": "demo-only",
    "digest": "d" * 64,
}
VERIFICATION = {
    "status": "VERIFIED",
    "verified_by": "SIH26035 DEMO FIXTURE — NOT REGULATORY VERIFIER",
    "verified_at": "2000-01-01T00:00:00Z",
    "evidence": "SYNTHETIC SIH DEMO ONLY — NOT REGULATORY EVIDENCE",
}


def _policy(*, required: bool) -> dict:
    return {
        "schema_version": "v1",
        "scope": "EACH_RANGE" if required else "INSTRUMENT",
        "scenarios": [
            {
                "procedure_variant": (
                    "DIGITAL_PRE_ROUNDING" if required else "DEMO_NOT_APPLICABLE"
                ),
                "scenario": "demo",
            }
        ],
        "cases": [
            {
                "when": {"kind": "always"},
                "decision": "REQUIRED" if required else "NOT_APPLICABLE",
                "reason": (
                    "SYNTHETIC SIH DEMO ONLY — Section 1 selected for demonstration"
                    if required
                    else "SYNTHETIC SIH DEMO ONLY — section excluded from this demo scenario"
                ),
            }
        ],
    }


def _rule(
    key: str,
    kind: str,
    policy: dict | None,
    *,
    section: int | None = None,
) -> dict:
    return {
        "key": key,
        "section": section,
        "kind": kind,
        "description": "SYNTHETIC SIH DEMO ONLY — not an OIML regulatory rule",
        "source": SOURCE,
        "verification": VERIFICATION,
        "dependencies": [],
        "blockers": [],
        "parameters": (
            []
            if policy is None
            else [
                {
                    "name": "POLICY_JSON",
                    "value": json.dumps(policy),
                    "numeric": False,
                }
            ]
        ),
    }


def load_demo_ruleset() -> RuleSet:
    rules = []
    tests = []

    for section, code in enumerate(SECTIONS, start=1):
        app_key = f"DEMO_APP_{section:02d}"
        required = section == 1
        rules.append(
            _rule(
                app_key,
                "applicability_policy_v1",
                _policy(required=required),
                section=section,
            )
        )

        dependencies = [app_key]
        implemented = False

        if required:
            implemented = True
            dependencies += [
                "SECTION1_PROCEDURE",
                "SECTION1_MPE",
                "SECTION1_CLASSIFICATION",
                "SECTION1_CALIBRATION",
            ]

        tests.append(
            {
                "code": code,
                "section": section,
                "name": f"{code.replace('_', ' ')} — SYNTHETIC DEMO",
                "source": SOURCE,
                "dependencies": dependencies,
                "implemented": implemented,
                "verification": VERIFICATION,
            }
        )

    rules += [
        _rule(
            "SECTION1_PROCEDURE",
            "weighing_procedure_v1",
            {
                "schema_version": "v1",
                "evaluation_context": "SIH_DEMO",
                "indication_type": "DIGITAL",
                "range_type": "SINGLE",
                "interval_basis": "e",
                "minimum_count": 4,
                "stages": ["UP", "DOWN"],
                "required_loads": [
                    {"direction": "UP", "load_g": "200"},
                    {"direction": "UP", "load_g": "30000"},
                    {"direction": "DOWN", "load_g": "30000"},
                    {"direction": "DOWN", "load_g": "200"},
                ],
                "transition_loads": [],
                "require_min": True,
                "require_max": True,
                "require_preload": False,
                "require_stabilization": False,
                "minimum_warmup_seconds": "0",
                "zero_condition": "DEMO_ZERO",
                "require_environment": False,
                "temperature_min_c": None,
                "temperature_max_c": None,
                "humidity_min_percent": None,
                "humidity_max_percent": None,
                "require_equipment": False,
                "require_certificate": False,
                "require_evidence": False,
                "require_monotonic_timestamps": True,
            },
            section=1,
        ),
        _rule(
            "SECTION1_MPE",
            "mpe_profile_v1",
            {
                "schema_version": "v1",
                "accuracy_class": "III",
                "evaluation_context": "SIH_DEMO",
                "operator": "<=",
                "semantics": "ABSOLUTE",
                "bands": [
                    {
                        "lower_e": "0",
                        "upper_e": None,
                        "lower_operator": ">=",
                        "upper_operator": "<=",
                        "multiplier_e": "1",
                    }
                ],
            },
            section=1,
        ),
        _rule("SECTION1_CLASSIFICATION", "dependency_v1", None, section=1),
        _rule("SECTION1_CALIBRATION", "dependency_v1", None, section=1),
    ]

    return RuleSet.model_validate(
        {
            "metadata": {
                "schema_version": 1,
                "standard_code": "OIML_R76",
                "standard_name": "SIH26035 SYNTHETIC DEMO — NOT OIML",
                "edition": DEMO_EDITION,
                "version": DEMO_VERSION,
                "standard_parts": [SOURCE],
                "supported_test_codes": ["WEIGHING_PERFORMANCE"],
                "source_reference": DEMO_SOURCE_REFERENCE,
            },
            "rules": rules,
            "tests": tests,
            "checklist": [],
        }
    )


def is_demo_ruleset(ruleset: RuleSet) -> bool:
    return bool(
        ruleset.metadata.version == DEMO_VERSION
        and ruleset.metadata.edition == DEMO_EDITION
        and ruleset.metadata.source_reference == DEMO_SOURCE_REFERENCE
        and ruleset.metadata.standard_name == "SIH26035 SYNTHETIC DEMO — NOT OIML"
    )


@dataclass(frozen=True)
class DemoWeighingEvaluator:
    delegate: WeighingEvaluator = WeighingEvaluator()

    def required_rules(self, **kwargs):
        return self.delegate.required_rules(**kwargs)

    def applicability(self, **kwargs):
        return self.delegate.applicability(**kwargs)

    def validate_procedure(self, **kwargs):
        return self.delegate.validate_procedure(**kwargs)

    def evaluate(self, **kwargs):
        result = self.delegate.evaluate(**kwargs)
        return EvaluationOutput(
            compliance_outcome=result.compliance_outcome,
            calculations=result.calculations,
            acceptance_limits=result.acceptance_limits,
            failed_conditions=result.failed_conditions,
            reasons=(
                "SYNTHETIC SIH DEMO ONLY — deterministic demonstration outcome; "
                "not a regulatory compliance conclusion",
            ),
        )


def demo_registry() -> EvaluatorRegistry:
    base = section1_registration()
    return EvaluatorRegistry(
        (
            EvaluatorRegistration(
                test_code=base.test_code,
                evaluator=DemoWeighingEvaluator(),
                contexts=base.contexts,
                observations=base.observations,
                implementation_version="section1-sih-demo-v1",
                synthetic_fixture=True,
                policy_schemas=base.policy_schemas,
            ),
        )
    )
