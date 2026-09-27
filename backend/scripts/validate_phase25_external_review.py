"""Validate a completed Phase 25 external independent-review pack.

Passing this validator means the handoff pack is internally complete. It does
not itself establish regulatory verification, install a verified artifact, or
activate anything.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from app.compliance.checklist import (
    ChecklistApplicabilityPolicy,
    ChecklistApplicabilityPolicyV2,
)
from app.compliance.ruleset import load_ruleset
from app.compliance.runtime_binding import (
    RuntimeBindingError,
    runtime_binding_catalog_json,
    runtime_binding_hash,
)
from app.compliance.stage7_activation import (
    REQUIRED_REGISTERS,
    REQUIRED_SOURCE_IDS,
)
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.compliance.verified_blueprint import (
    ASSEMBLY_CONTRACT_VERSION,
    validate_executable_review_rows,
)

SHA64 = set("0123456789abcdef")
BACKEND = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    BACKEND
    / "app"
    / "compliance"
    / "rules"
    / "oiml_r76_2006_verified"
    / "stage7_verification_manifest.template.json"
)
SINGLE_DOCUMENT_SOURCE_IDS = {
    "SRC-R76-1-2006-E",
    "SRC-R76-2-2007-E",
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _required(value: str, label: str, blockers: list[str]) -> None:
    if not value or not value.strip():
        blockers.append(f"MISSING:{label}")


def _sha(value: str, label: str, blockers: list[str]) -> None:
    if len(value) != 64 or any(char not in SHA64 for char in value):
        blockers.append(f"INVALID_SHA256:{label}")


def _time(value: str, label: str, blockers: list[str]) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        blockers.append(f"INVALID_TIMESTAMP:{label}")
        return
    if parsed.tzinfo is None:
        blockers.append(f"TIMEZONE_REQUIRED:{label}")


def _strict_boolean(value: str, label: str, blockers: list[str]) -> None:
    if value.strip().lower() not in {"true", "false"}:
        blockers.append(f"INVALID_BOOLEAN:{label}")


def _date(value: str, label: str, blockers: list[str]) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        blockers.append(f"INVALID_DATE:{label}")


def _validate_checklist_policy(value: str, prefix: str, blockers: list[str]) -> None:
    try:
        policy = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        blockers.append(f"INVALID_POLICY_JSON:{prefix}")
        return

    if not isinstance(policy, dict):
        blockers.append(f"INVALID_POLICY_STRUCTURE:{prefix}")
        return

    schema_version = policy.get("schema_version")
    schema = {
        "v1": ChecklistApplicabilityPolicy,
        "v2": ChecklistApplicabilityPolicyV2,
    }.get(schema_version)
    if schema is None:
        blockers.append(f"INVALID_POLICY_SCHEMA:{prefix}")
        return

    try:
        schema.model_validate(policy)
    except ValueError:
        blockers.append(f"INVALID_POLICY_STRUCTURE:{prefix}")


def _runtime_protocols(registrations, *, version: str) -> set[str]:
    protocols: set[str] = set()
    for item in registrations:
        if item.procedure_schema_version != version:
            continue
        protocol = item.schema.model_fields["protocol"].default
        if isinstance(protocol, str):
            protocols.add(protocol)
    return protocols


def validate_pack(input_dir: Path) -> dict[str, object]:
    input_dir = input_dir.resolve()
    blockers: list[str] = []

    required_files = (
        "00_summary.json",
        "01_source_evidence.csv",
        "01a_source_documents.csv",
        "02_register_signoff.csv",
        "03_rule_review.csv",
        "04_test_review.csv",
        "05_checklist_review.csv",
        "06_runtime_schema_review.csv",
        "07_executable_rule_review.csv",
        "08_final_regulatory_declaration.json",
        "README.md",
    )
    for name in required_files:
        if not (input_dir / name).is_file():
            blockers.append(f"MISSING_FILE:{name}")

    if blockers:
        return {"valid": False, "blockers": tuple(sorted(set(blockers)))}

    candidate = load_ruleset()
    summary = json.loads((input_dir / "00_summary.json").read_text(encoding="utf-8"))
    if summary.get("candidate_configuration_hash") != candidate.configuration_hash:
        blockers.append("CANDIDATE_HASH_MISMATCH")
    if summary.get("assembly_contract_version") != ASSEMBLY_CONTRACT_VERSION:
        blockers.append("ASSEMBLY_CONTRACT_MISMATCH")

    source_rows = _read(input_dir / "01_source_evidence.csv")
    source_ids = {row["source_id"] for row in source_rows}
    if source_ids != REQUIRED_SOURCE_IDS:
        blockers.append("SOURCE_SET_MISMATCH")

    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    source_catalog = {row["source_id"]: row for row in template["source_evidence"]}

    source_documents = _read(input_dir / "01a_source_documents.csv")
    documents_by_source: dict[str, list[dict[str, str]]] = {
        source_id: [] for source_id in REQUIRED_SOURCE_IDS
    }
    document_keys: set[tuple[str, str]] = set()
    for row in source_documents:
        source_id = row.get("source_id", "")
        document_id = row.get("document_id", "")
        prefix = f"SOURCE_DOCUMENT:{source_id or '<missing>'}:{document_id or '<missing>'}"
        for field in (
            "source_id",
            "document_id",
            "identity",
            "official_url",
            "sha256",
            "acquired_at",
            "acquisition_reference",
        ):
            _required(row.get(field, ""), f"{prefix}:{field}", blockers)
        if source_id not in REQUIRED_SOURCE_IDS:
            blockers.append(f"UNKNOWN_SOURCE_DOCUMENT_FAMILY:{prefix}")
            continue
        key = (source_id, document_id)
        if document_id and key in document_keys:
            blockers.append(f"DUPLICATE_SOURCE_DOCUMENT:{prefix}")
        document_keys.add(key)
        documents_by_source[source_id].append(row)
        if row.get("sha256"):
            _sha(row["sha256"], f"{prefix}:sha256", blockers)
        if row.get("acquired_at"):
            _time(row["acquired_at"], f"{prefix}:acquired_at", blockers)

    for row in source_rows:
        source_id = row["source_id"]
        prefix = f"SOURCE:{source_id}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        expected = source_catalog.get(source_id)
        if expected is not None:
            if row["part"] != expected["part"]:
                blockers.append(f"SOURCE_CANDIDATE_MISMATCH:{prefix}:part")
            if row["edition"] != expected["edition"]:
                blockers.append(f"SOURCE_CANDIDATE_MISMATCH:{prefix}:edition")
            if row["discovery_url"] != expected["official_url"]:
                blockers.append(f"SOURCE_CANDIDATE_MISMATCH:{prefix}:discovery_url")
        for field in (
            "identity",
            "current_through",
            "verified_by",
            "verified_at",
            "evidence_reference",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["current_through"]:
            _date(row["current_through"], f"{prefix}:current_through", blockers)
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["amendment_set_complete"].lower() != "true":
            blockers.append(f"AMENDMENT_SET_COMPLETENESS_REQUIRED:{prefix}")
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")

        documents = documents_by_source[source_id]
        if not documents:
            blockers.append(f"SOURCE_DOCUMENTS_REQUIRED:{prefix}")
        if source_id in SINGLE_DOCUMENT_SOURCE_IDS:
            if len(documents) != 1:
                blockers.append(f"SINGLE_DOCUMENT_SOURCE_REQUIRED:{prefix}")
            elif expected is not None and documents[0]["official_url"] != expected["official_url"]:
                blockers.append(f"SOURCE_DOCUMENT_URL_MISMATCH:{prefix}")

    registers = _read(input_dir / "02_register_signoff.csv")
    register_ids = {row["register_id"] for row in registers}
    if register_ids != set(REQUIRED_REGISTERS):
        blockers.append("REGISTER_SET_MISMATCH")

    for row in registers:
        prefix = f"REGISTER:{row['register_id']}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "verified_by",
            "verifier_role",
            "verifier_organization",
            "verified_at",
            "evidence_reference",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")

    rule_rows = _read(input_dir / "03_rule_review.csv")
    if {row["item_key"] for row in rule_rows} != {item.key for item in candidate.rules}:
        blockers.append("RULE_SET_MISMATCH")

    for row in rule_rows:
        prefix = f"RULE:{row['item_key']}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "verified_source_part",
            "verified_source_edition",
            "verified_source_identity",
            "verified_source_clause",
            "verified_source_digest",
            "verified_by",
            "verifier_role",
            "verified_at",
            "evidence_reference",
            "resolved_parameters_or_policy_reference",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["verified_source_digest"]:
            _sha(
                row["verified_source_digest"],
                f"{prefix}:verified_source_digest",
                blockers,
            )
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")

    test_rows = _read(input_dir / "04_test_review.csv")
    if {row["item_key"] for row in test_rows} != {item.code for item in candidate.tests}:
        blockers.append("TEST_SET_MISMATCH")

    for row in test_rows:
        prefix = f"TEST:{row['item_key']}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "verified_source_part",
            "verified_source_edition",
            "verified_source_identity",
            "verified_source_clause",
            "verified_source_digest",
            "verified_by",
            "verifier_role",
            "verified_at",
            "evidence_reference",
            "supported_after_review",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["verified_source_digest"]:
            _sha(
                row["verified_source_digest"],
                f"{prefix}:verified_source_digest",
                blockers,
            )
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")
        _strict_boolean(
            row["supported_after_review"],
            f"{prefix}:supported_after_review",
            blockers,
        )
        supported = row["supported_after_review"].strip().lower()
        if supported in {"true", "false"}:
            expected = row["item_key"] in set(IMPLEMENTED_TEST_CODES)
            if (supported == "true") != expected:
                blockers.append(f"TEST_SUPPORT_SET_MISMATCH:{prefix}")

    checklist_rows = _read(input_dir / "05_checklist_review.csv")
    if {row["item_key"] for row in checklist_rows} != {
        item.key for item in candidate.checklist
    }:
        blockers.append("CHECKLIST_SET_MISMATCH")

    for row in checklist_rows:
        prefix = f"CHECKLIST:{row['item_key']}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "verified_text",
            "verified_applicability_policy_json",
            "verified_evidence_required",
            "verified_source_part",
            "verified_source_edition",
            "verified_source_identity",
            "verified_source_clause",
            "verified_source_digest",
            "verified_by",
            "verifier_role",
            "verified_at",
            "evidence_reference",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["verified_source_digest"]:
            _sha(
                row["verified_source_digest"],
                f"{prefix}:verified_source_digest",
                blockers,
            )
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")
        _validate_checklist_policy(
            row["verified_applicability_policy_json"],
            prefix,
            blockers,
        )
        _strict_boolean(
            row["verified_evidence_required"],
            f"{prefix}:verified_evidence_required",
            blockers,
        )

    runtime_rows = _read(input_dir / "06_runtime_schema_review.csv")
    runtime_codes = {row["test_code"] for row in runtime_rows}
    if runtime_codes != set(IMPLEMENTED_TEST_CODES):
        blockers.append("RUNTIME_SCHEMA_SET_MISMATCH")

    registry = implemented_registry()
    for row in runtime_rows:
        code = row["test_code"]
        prefix = f"RUNTIME:{code}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "selected_procedure_schema_version",
            "selected_observation_schema_version",
            "selected_runtime_binding_sha256",
            "evidence_reference",
            "reviewed_by",
            "reviewer_role",
            "reviewer_organization",
            "reviewed_at",
        ):
            _required(row.get(field, ""), f"{prefix}:{field}", blockers)
        if row.get("selected_runtime_binding_sha256"):
            _sha(
                row["selected_runtime_binding_sha256"],
                f"{prefix}:selected_runtime_binding_sha256",
                blockers,
            )
        if row.get("reviewed_at"):
            _time(row["reviewed_at"], f"{prefix}:reviewed_at", blockers)

        if row.get("independent_of_implementation", "").lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")

        registration = registry.resolve(code)
        if row.get("implementation_version") != registration.implementation_version:
            blockers.append(
                f"RUNTIME_SCHEMA_CANDIDATE_MISMATCH:{prefix}:implementation"
            )
        expected_binding_catalog = runtime_binding_catalog_json(registration)
        if row.get("available_runtime_bindings_json") != expected_binding_catalog:
            blockers.append(
                f"RUNTIME_SCHEMA_CANDIDATE_MISMATCH:{prefix}:bindings"
            )
        available_procedure = {
            item.procedure_schema_version for item in registration.contexts.registrations
        }
        available_observation = {
            item.observation_schema_version for item in registration.observations.registrations
        }
        expected_procedure = ";".join(sorted(available_procedure))
        expected_observation = ";".join(sorted(available_observation))
        if row["available_procedure_schema_versions"] != expected_procedure:
            blockers.append(f"RUNTIME_SCHEMA_CANDIDATE_MISMATCH:{prefix}:procedure")
        if row["available_observation_schema_versions"] != expected_observation:
            blockers.append(f"RUNTIME_SCHEMA_CANDIDATE_MISMATCH:{prefix}:observation")

        procedure_version = row["selected_procedure_schema_version"]
        observation_version = row["selected_observation_schema_version"]
        if procedure_version not in available_procedure:
            blockers.append(f"PROCEDURE_SCHEMA_UNAVAILABLE:{prefix}")
        if observation_version not in available_observation:
            blockers.append(f"OBSERVATION_SCHEMA_UNAVAILABLE:{prefix}")

        if (
            procedure_version in available_procedure
            and observation_version in available_observation
        ):
            procedure_protocols = _runtime_protocols(
                registration.contexts.registrations,
                version=procedure_version,
            )
            observation_protocols = {
                item.protocol
                for item in registration.observations.registrations
                if item.observation_schema_version == observation_version
            }
            if not procedure_protocols & observation_protocols:
                blockers.append(f"RUNTIME_SCHEMA_PAIR_UNAVAILABLE:{prefix}")
            else:
                try:
                    expected_binding = runtime_binding_hash(
                        registration,
                        procedure_version,
                        observation_version,
                    )
                except RuntimeBindingError:
                    blockers.append(f"RUNTIME_SCHEMA_PAIR_UNAVAILABLE:{prefix}")
                else:
                    if (
                        row.get("selected_runtime_binding_sha256")
                        != expected_binding
                    ):
                        blockers.append(f"RUNTIME_BINDING_MISMATCH:{prefix}")

        # This validator checks the independently reviewed exact runtime binding
        # against the implementation. Authority enablement remains a separate
        # Stage 7 fail-closed decision.

    executable_rows = _read(input_dir / "07_executable_rule_review.csv")
    blockers.extend(validate_executable_review_rows(executable_rows, candidate))

    declaration = json.loads(
        (input_dir / "08_final_regulatory_declaration.json").read_text(
            encoding="utf-8"
        )
    )
    if declaration.get("schema_version") != 1:
        blockers.append("FINAL_DECLARATION_SCHEMA_MISMATCH")
    if declaration.get("candidate_configuration_hash") != candidate.configuration_hash:
        blockers.append("FINAL_DECLARATION_CANDIDATE_HASH_MISMATCH")
    if declaration.get("assembly_contract_version") != ASSEMBLY_CONTRACT_VERSION:
        blockers.append("FINAL_DECLARATION_ASSEMBLY_CONTRACT_MISMATCH")
    if declaration.get("regulatory_signoff") is not True:
        blockers.append("FINAL_REGULATORY_SIGNOFF_REQUIRED")
    if declaration.get("independent_of_implementation") is not True:
        blockers.append("FINAL_INDEPENDENCE_REQUIRED")
    for field in (
        "signed_by",
        "signer_role",
        "signer_organization",
        "signed_at",
        "evidence_reference",
    ):
        value = declaration.get(field)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"MISSING:FINAL_DECLARATION:{field}")
    if isinstance(declaration.get("signed_at"), str) and declaration["signed_at"].strip():
        _time(declaration["signed_at"], "FINAL_DECLARATION:signed_at", blockers)

    family_by_scope = {
        (row["part"], row["edition"]): row["source_id"]
        for row in source_rows
    }
    document_keys = {
        (row["source_id"], row["identity"], row["sha256"])
        for row in source_documents
    }

    def check_item_source(row, prefix):
        scope = (
            row.get("verified_source_part", ""),
            row.get("verified_source_edition", ""),
        )
        source_id = family_by_scope.get(scope)
        if source_id is None:
            blockers.append(f"ITEM_SOURCE_FAMILY_MISMATCH:{prefix}")
            return
        key = (
            source_id,
            row.get("verified_source_identity", ""),
            row.get("verified_source_digest", ""),
        )
        if key not in document_keys:
            blockers.append(f"ITEM_SOURCE_DOCUMENT_MISMATCH:{prefix}")

    for row in rule_rows:
        check_item_source(row, f"CANDIDATE_RULE:{row['item_key']}")
    for row in test_rows:
        check_item_source(row, f"TEST:{row['item_key']}")
    for row in checklist_rows:
        check_item_source(row, f"CHECKLIST:{row['item_key']}")
    for row in executable_rows:
        check_item_source(row, f"EXEC_RULE:{row['rule_key']}")

    canonical = json.dumps(
        {
            "summary": summary,
            "sources": source_rows,
            "source_documents": source_documents,
            "registers": registers,
            "rules": rule_rows,
            "tests": test_rows,
            "checklist": checklist_rows,
            "runtime": runtime_rows,
            "executable_rules": executable_rows,
            "final_declaration": declaration,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return {
        "valid": not blockers,
        "blockers": tuple(sorted(set(blockers))),
        "review_pack_sha256": hashlib.sha256(canonical).hexdigest(),
        "sources": len(source_rows),
        "source_documents": len(source_documents),
        "registers": len(registers),
        "rules": len(rule_rows),
        "tests": len(test_rows),
        "checklist": len(checklist_rows),
        "runtime_schemas": len(runtime_rows),
        "executable_rules": len(executable_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    result = validate_pack(args.input)
    print(f"External review pack valid: {result['valid']}")
    print(f"Blocker count: {len(result['blockers'])}")
    if result.get("review_pack_sha256"):
        print(f"Review pack SHA-256: {result['review_pack_sha256']}")
    for blocker in result["blockers"]:
        print(f"- {blocker}")

    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
