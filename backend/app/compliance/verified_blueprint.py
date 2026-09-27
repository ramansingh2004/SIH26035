"""Exact executable-rule blueprint for Phase 25 verified-v1 assembly.

This module contains no regulatory values. It defines only which exact rules
the current evaluators/services consume and which schema families each rule
slot can accept.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import Frozen
from app.compliance.ruleset import RuleSet
from app.compliance.selection import SelectionPolicy
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry

ASSEMBLY_CONTRACT_VERSION = "verified-blueprint-v1"
INDIA_SUBSTITUTION_RULE = "SECTION1_INDIA_STANDARD_WEIGHT_SUBSTITUTION"

ConstructionCategory = Literal[
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
]


class ConstructionRulePolicyContract(Frozen):
    # Pure-domain mirror of the Section 16 construction policy wire shape.

    schema_version: Literal["v1"]
    category: ConstructionCategory
    item_key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]*$",
    )
    sort_order: int = Field(ge=0, strict=True)
    required: StrictBool
    evidence_required: StrictBool
    allow_not_applicable: StrictBool
    required_value_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_required_keys(self):
        if len(set(self.required_value_keys)) != len(self.required_value_keys):
            raise ValueError("Duplicate required construction value key")
        if any(not key.strip() for key in self.required_value_keys):
            raise ValueError("Construction value keys cannot be blank")
        return self


CONSTRUCTION_ITEMS = (
    ("GENERAL", "Overall construction description and additional instrument information."),
    ("RECEPTOR_LOAD_CELLS", "Load receptor, "
    "load-transmitting/load-measuring devices and module identity."),
    ("INDICATOR_DISPLAY", "Indicator/display construction and primary-indication characteristics."),
    ("PRINTER_PERIPHERALS", "Printing, storage, peripheral and connected-device construction."),
    ("POWER_INTERFACES", "Power arrangements, interfaces and external-equipment construction."),
    ("TILT_ZERO_TARE", "Tilt/level, zero-setting and tare-related devices."),
    ("SEALS_SECURITY_SOFTWARE", "Securing, sealing, software security and identification."),
    ("DOCUMENTS_PHOTOS", "Documentation, photographs, "
    "component descriptions and manufacturer references."),
)

# These registrations expose a v2 schema, but their current evaluator still
# loads the v1 procedure policy directly. Do not offer a v2 authoritative rule
# until evaluator dispatch is explicitly upgraded.
V1_ONLY_PROCEDURE_RULES = frozenset(
    {
        "SECTION11_VOLTAGE_PROCEDURE",
        "SECTION13_DAMP_HEAT_PROCEDURE",
        "SECTION14_SPAN_STABILITY_PROCEDURE",
        "SECTION15_ENDURANCE_PROCEDURE",
    }
)


@dataclass(frozen=True)
class RuleBlueprint:
    rule_key: str
    section: int | None
    role: str
    required_by_tests: tuple[str, ...]
    file_bucket: str
    allowed_kinds: tuple[str, ...]
    required_dependencies: tuple[str, ...]
    description: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _procedure_kinds(registration) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                item.kind
                for item in registration.policy_schemas
                if "_procedure_" in item.kind
            }
        )
    )


def _mpe_kinds(registration) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                item.kind
                for item in registration.policy_schemas
                if item.kind.startswith("mpe_profile")
            }
        )
    )


def _rule_role(key: str) -> str:
    if key.endswith("_MPE"):
        return "MPE"
    if "PROCEDURE" in key:
        return "PROCEDURE"
    return "DEPENDENCY"


def _file_bucket(*, role: str, section: int | None) -> str:
    if role == "APPLICABILITY":
        return "applicability"
    if role == "MPE":
        return "mpe"
    if role == "CONSTRUCTION":
        return "checklist"
    if section == 11:
        return "voltage"
    if section == 12:
        return "disturbances"
    if section == 15:
        return "endurance"
    return "classes"


def _policy_schema_map() -> dict[str, type]:
    result: dict[str, type] = {}
    for registration in implemented_registry().registrations:
        for item in registration.policy_schemas:
            existing = result.get(item.kind)
            if existing is not None and existing is not item.schema:
                raise ValueError(f"Conflicting policy schema registration for {item.kind}")
            result[item.kind] = item.schema
    result["construction_item_v1"] = ConstructionRulePolicyContract
    result["run_selection_v1"] = SelectionPolicy
    return result


def executable_rule_blueprint(candidate: RuleSet) -> tuple[RuleBlueprint, ...]:
    tests = {item.code: item for item in candidate.tests}
    registry = implemented_registry()
    rows: dict[str, dict[str, Any]] = {}

    def add(
        key: str,
        *,
        section: int | None,
        role: str,
        required_by: tuple[str, ...],
        allowed_kinds: tuple[str, ...],
        dependencies: tuple[str, ...] = (),
        description: str,
    ) -> None:
        normalized_kinds = tuple(sorted(set(allowed_kinds)))
        normalized_dependencies = tuple(sorted(set(dependencies)))
        payload = rows.get(key)
        if payload is None:
            rows[key] = {
                "section": section,
                "role": role,
                "required_by": set(required_by),
                "allowed_kinds": normalized_kinds,
                "dependencies": normalized_dependencies,
                "description": description,
            }
            return
        if (
            payload["section"] != section
            or payload["role"] != role
            or payload["allowed_kinds"] != normalized_kinds
            or payload["dependencies"] != normalized_dependencies
        ):
            raise ValueError(f"Conflicting executable-rule blueprint for {key}")
        payload["required_by"].update(required_by)

    # Every catalog row gets one explicit applicability root.
    for test in candidate.tests:
        add(
            f"APP_{test.code}",
            section=test.section,
            role="APPLICABILITY",
            required_by=(test.code,),
            allowed_kinds=("applicability_policy_v1",),
            description=f"Verified applicability policy for {test.code}.",
        )

    # Exact concrete rules consumed by implemented evaluators.
    for code in IMPLEMENTED_TEST_CODES:
        registration = registry.resolve(code)
        section = tests[code].section
        procedure_kinds = _procedure_kinds(registration)
        mpe_kinds = _mpe_kinds(registration)
        for key in registration.evaluator.required_rules():
            role = _rule_role(key)
            if role == "PROCEDURE":
                allowed = procedure_kinds
                if key in V1_ONLY_PROCEDURE_RULES:
                    allowed = tuple(value for value in allowed if value.endswith("_v1"))
                if not allowed:
                    raise ValueError(f"No executable procedure policy kind for {key}")
            elif role == "MPE":
                allowed = mpe_kinds
                if not allowed:
                    raise ValueError(f"No executable MPE policy kind for {key}")
            else:
                allowed = ("dependency_v1",)
            dependencies = (
                (INDIA_SUBSTITUTION_RULE,) if key == "SECTION1_PROCEDURE" else ()
            )
            add(
                key,
                section=section,
                role=role,
                required_by=(code,),
                allowed_kinds=allowed,
                dependencies=dependencies,
                description=f"Verified {role.lower()} rule consumed by {code}.",
            )

    # Separate provenance dependency for the India-specific substitution branch.
    add(
        INDIA_SUBSTITUTION_RULE,
        section=1,
        role="DEPENDENCY",
        required_by=("WEIGHING_PERFORMANCE",),
        allowed_kinds=("dependency_v1",),
        description=(
            "India-specific standard-weight substitution provenance dependency "
            "for the verified Section 1 procedure."
        ),
    )

    # Service-level policy consumed outside the evaluator registry.
    add(
        "RETEST_SELECTION",
        section=None,
        role="SYSTEM_POLICY",
        required_by=(),
        allowed_kinds=("run_selection_v1",),
        description="Verified authoritative retest/run-selection policy.",
    )

    # Section 16 requires a real structural construction catalog.
    for category, description in CONSTRUCTION_ITEMS:
        add(
            f"SECTION16_{category}",
            section=16,
            role="CONSTRUCTION",
            required_by=("CONSTRUCTION_EXAMINATION",),
            allowed_kinds=("construction_item_v1",),
            description=description,
        )

    result = []
    for key, payload in sorted(rows.items()):
        result.append(
            RuleBlueprint(
                rule_key=key,
                section=payload["section"],
                role=payload["role"],
                required_by_tests=tuple(sorted(payload["required_by"])),
                file_bucket=_file_bucket(role=payload["role"], section=payload["section"]),
                allowed_kinds=payload["allowed_kinds"],
                required_dependencies=payload["dependencies"],
                description=payload["description"],
            )
        )
    return tuple(result)


def verified_test_dependencies(candidate: RuleSet) -> dict[str, tuple[str, ...]]:
    registry = implemented_registry()
    implemented = set(IMPLEMENTED_TEST_CODES)
    result: dict[str, tuple[str, ...]] = {}
    for test in candidate.tests:
        values = [f"APP_{test.code}"]
        if test.code in implemented:
            values.extend(registry.resolve(test.code).evaluator.required_rules())
        result[test.code] = tuple(dict.fromkeys(values))
    return result


def executable_review_rows(candidate: RuleSet) -> list[dict[str, str]]:
    rows = []
    schemas = _policy_schema_map()
    for item in executable_rule_blueprint(candidate):
        schema_catalog = {
            kind: schemas[kind].model_json_schema()
            for kind in item.allowed_kinds
            if kind != "dependency_v1"
        }
        rows.append(
            {
                "rule_key": item.rule_key,
                "section": "" if item.section is None else str(item.section),
                "role": item.role,
                "required_by_tests_json": _canonical_json(list(item.required_by_tests)),
                "file_bucket": item.file_bucket,
                "allowed_kinds_json": _canonical_json(list(item.allowed_kinds)),
                "policy_schema_catalog_json": _canonical_json(schema_catalog),
                "required_dependencies_json": _canonical_json(
                    list(item.required_dependencies)
                ),
                "description": item.description,
                "selected_kind": "",
                "verified_policy_json": "",
                "verified_source_part": "",
                "verified_source_edition": "",
                "verified_source_identity": "",
                "verified_source_clause": "",
                "verified_source_digest": "",
                "review_status": "PENDING",
                "verified_by": "",
                "verifier_role": "",
                "verifier_organization": "",
                "verified_at": "",
                "evidence_reference": "",
                "independent_of_implementation": "false",
                "review_notes": "",
            }
        )
    return rows


def _time_is_aware(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


def validate_executable_review_rows(
    rows: list[dict[str, str]],
    candidate: RuleSet,
) -> tuple[str, ...]:
    blockers: set[str] = set()
    expected = {item.rule_key: item for item in executable_rule_blueprint(candidate)}
    supplied: dict[str, dict[str, str]] = {}

    for row in rows:
        key = row.get("rule_key", "")
        if not key:
            blockers.add("EXEC_RULE:MISSING_RULE_KEY")
            continue
        if key in supplied:
            blockers.add(f"EXEC_RULE:DUPLICATE:{key}")
        supplied[key] = row

    if set(supplied) != set(expected):
        blockers.add("EXEC_RULE_SET_MISMATCH")

    schemas = _policy_schema_map()
    sha_chars = set("0123456789abcdef")

    for key, blueprint in expected.items():
        row = supplied.get(key)
        if row is None:
            continue
        prefix = f"EXEC_RULE:{key}"
        immutable = {
            "section": "" if blueprint.section is None else str(blueprint.section),
            "role": blueprint.role,
            "required_by_tests_json": _canonical_json(list(blueprint.required_by_tests)),
            "file_bucket": blueprint.file_bucket,
            "allowed_kinds_json": _canonical_json(list(blueprint.allowed_kinds)),
            "policy_schema_catalog_json": _canonical_json(
                {
                    kind: schemas[kind].model_json_schema()
                    for kind in blueprint.allowed_kinds
                    if kind != "dependency_v1"
                }
            ),
            "required_dependencies_json": _canonical_json(
                list(blueprint.required_dependencies)
            ),
            "description": blueprint.description,
        }
        for field, value in immutable.items():
            if row.get(field, "") != value:
                blockers.add(f"EXEC_RULE_BLUEPRINT_MISMATCH:{key}:{field}")

        if row.get("review_status") != "VERIFIED":
            blockers.add(f"NOT_VERIFIED:{prefix}")
        if row.get("independent_of_implementation", "").lower() != "true":
            blockers.add(f"INDEPENDENCE_REQUIRED:{prefix}")

        for field in (
            "selected_kind",
            "verified_source_part",
            "verified_source_edition",
            "verified_source_identity",
            "verified_source_clause",
            "verified_source_digest",
            "verified_by",
            "verifier_role",
            "verifier_organization",
            "verified_at",
            "evidence_reference",
        ):
            if not row.get(field, "").strip():
                blockers.add(f"MISSING:{prefix}:{field}")

        digest = row.get("verified_source_digest", "")
        if len(digest) != 64 or any(char not in sha_chars for char in digest):
            blockers.add(f"INVALID_SHA256:{prefix}:verified_source_digest")
        if row.get("verified_at") and not _time_is_aware(row["verified_at"]):
            blockers.add(f"INVALID_OR_NAIVE_TIMESTAMP:{prefix}:verified_at")

        kind = row.get("selected_kind", "")
        if kind not in blueprint.allowed_kinds:
            blockers.add(f"UNSUPPORTED_KIND:{prefix}:{kind or 'EMPTY'}")
            continue

        policy_json = row.get("verified_policy_json", "")
        if kind == "dependency_v1":
            if policy_json.strip():
                blockers.add(f"UNEXPECTED_POLICY_JSON:{prefix}")
        else:
            if not policy_json.strip():
                blockers.add(f"MISSING:{prefix}:verified_policy_json")
                continue
            schema = schemas.get(kind)
            if schema is None:
                blockers.add(f"POLICY_SCHEMA_UNAVAILABLE:{prefix}:{kind}")
                continue
            try:
                schema.model_validate_json(policy_json)
            except ValueError:
                blockers.add(f"INVALID_POLICY_JSON:{prefix}:{kind}")

        if (
            key == INDIA_SUBSTITUTION_RULE
            and row.get("verified_source_part") != "INDIA-LM-GENERAL"
        ):
            blockers.add(f"INDIA_SOURCE_REQUIRED:{prefix}:INDIA-LM-GENERAL")

    return tuple(sorted(blockers))


__all__ = [
    "ASSEMBLY_CONTRACT_VERSION",
    "CONSTRUCTION_ITEMS",
    "INDIA_SUBSTITUTION_RULE",
    "RuleBlueprint",
    "V1_ONLY_PROCEDURE_RULES",
    "executable_review_rows",
    "executable_rule_blueprint",
    "validate_executable_review_rows",
    "verified_test_dependencies",
]
