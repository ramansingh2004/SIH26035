"""Phase 26 Stage 4 synthetic Section 16 construction data.

This module describes software-demonstration inputs only. It does not create
regulatory evidence and is accepted only for the V3 full-demo artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.compliance.full_demo_execution import is_full_demo_execution_ruleset
from app.compliance.ruleset import RuleSet

EXPECTED_CATEGORIES = (
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
)

NOTICE = (
    "SYNTHETIC SIH26035 SECTION 16 DEMO ONLY — metadata-only software "
    "fixture; not regulatory evidence and not an OIML examination conclusion"
)


@dataclass(frozen=True)
class FullDemoConstructionItem:
    item_key: str
    category: str
    value_json: dict[str, str]
    remarks: str
    evidence_required: bool
    evidence_file_name: str
    evidence_content_type: str
    evidence_size: int
    evidence_sha256: str


def _policy(rule) -> dict:
    values = [
        item.value
        for item in rule.parameters
        if item.name == "POLICY_JSON"
    ]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError(f"{rule.key}: construction POLICY_JSON missing")
    value = json.loads(values[0])
    if value.get("schema_version") != "v1":
        raise ValueError(f"{rule.key}: construction policy must be v1")
    return value


def full_demo_construction_plan(
    ruleset: RuleSet,
) -> tuple[FullDemoConstructionItem, ...]:
    if not is_full_demo_execution_ruleset(ruleset):
        raise ValueError(
            "Section 16 synthetic completion is restricted to the V3 "
            "full-demo execution artifact"
        )

    rows = []
    for rule in ruleset.rules:
        if rule.section != 16 or rule.kind != "construction_item_v1":
            continue
        if rule.verification.status != "VERIFIED":
            raise ValueError(f"{rule.key}: synthetic construction rule is not verified")
        policy = _policy(rule)
        if policy.get("required") is not True:
            raise ValueError(f"{rule.key}: Stage 4 expects a required demo item")

        item_key = str(policy["item_key"])
        category = str(policy["category"])
        required_keys = tuple(policy.get("required_value_keys", ()))
        values = {
            key: f"SYNTHETIC_DEMO_CAPTURED:{item_key}:{key}"
            for key in required_keys
        }
        payload = (
            f"{NOTICE}\n"
            f"item_key={item_key}\n"
            f"category={category}\n"
        ).encode()
        rows.append(
            FullDemoConstructionItem(
                item_key=item_key,
                category=category,
                value_json=values,
                remarks=NOTICE,
                evidence_required=bool(policy.get("evidence_required")),
                evidence_file_name=f"{item_key.lower()}.txt",
                evidence_content_type="text/plain",
                evidence_size=len(payload),
                evidence_sha256=hashlib.sha256(payload).hexdigest(),
            )
        )

    rows.sort(key=lambda item: EXPECTED_CATEGORIES.index(item.category))
    if len(rows) != 8:
        raise ValueError("Stage 4 requires exactly eight Section 16 demo items")
    if tuple(item.category for item in rows) != EXPECTED_CATEGORIES:
        raise ValueError("Stage 4 Section 16 category set is incomplete")
    if len({item.item_key for item in rows}) != 8:
        raise ValueError("Stage 4 construction item keys must be unique")
    if not all(item.evidence_required for item in rows):
        raise ValueError("Stage 4 V3 dossier expects evidence for all eight items")
    return tuple(rows)
