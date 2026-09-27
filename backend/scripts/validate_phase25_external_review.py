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
from datetime import datetime
from pathlib import Path

from app.compliance.ruleset import load_ruleset
from app.compliance.stage7_activation import (
    REQUIRED_REGISTERS,
    REQUIRED_SOURCE_IDS,
)
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry

SHA64 = set("0123456789abcdef")


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


def validate_pack(input_dir: Path) -> dict[str, object]:
    input_dir = input_dir.resolve()
    blockers: list[str] = []

    required_files = (
        "00_summary.json",
        "01_source_evidence.csv",
        "02_register_signoff.csv",
        "03_rule_review.csv",
        "04_test_review.csv",
        "05_checklist_review.csv",
        "06_runtime_schema_review.csv",
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

    source_rows = _read(input_dir / "01_source_evidence.csv")
    source_ids = {row["source_id"] for row in source_rows}
    if source_ids != REQUIRED_SOURCE_IDS:
        blockers.append("SOURCE_SET_MISMATCH")

    for row in source_rows:
        prefix = f"SOURCE:{row['source_id']}"
        if row["review_status"] != "VERIFIED":
            blockers.append(f"NOT_VERIFIED:{prefix}")
        for field in (
            "identity",
            "sha256",
            "acquired_at",
            "acquisition_reference",
            "verified_by",
            "verified_at",
            "evidence_reference",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["sha256"]:
            _sha(row["sha256"], f"{prefix}:sha256", blockers)
        if row["acquired_at"]:
            _time(row["acquired_at"], f"{prefix}:acquired_at", blockers)
        if row["verified_at"]:
            _time(row["verified_at"], f"{prefix}:verified_at", blockers)
        if row["independent_of_implementation"].lower() != "true":
            blockers.append(f"INDEPENDENCE_REQUIRED:{prefix}")

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
        try:
            policy = json.loads(row["verified_applicability_policy_json"])
            if policy.get("schema_version") != "v1":
                blockers.append(f"INVALID_POLICY_SCHEMA:{prefix}")
        except Exception:
            blockers.append(f"INVALID_POLICY_JSON:{prefix}")
        if row["verified_evidence_required"].lower() not in {"true", "false"}:
            blockers.append(f"INVALID_EVIDENCE_REQUIRED:{prefix}")

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
            "evidence_reference",
            "reviewed_by",
            "reviewed_at",
        ):
            _required(row[field], f"{prefix}:{field}", blockers)
        if row["reviewed_at"]:
            _time(row["reviewed_at"], f"{prefix}:reviewed_at", blockers)

        registration = registry.resolve(code)
        available_procedure = {
            item.procedure_schema_version for item in registration.contexts.registrations
        }
        available_observation = {
            item.observation_schema_version for item in registration.observations.registrations
        }
        if row["selected_procedure_schema_version"] not in available_procedure:
            blockers.append(f"PROCEDURE_SCHEMA_UNAVAILABLE:{prefix}")
        if row["selected_observation_schema_version"] not in available_observation:
            blockers.append(f"OBSERVATION_SCHEMA_UNAVAILABLE:{prefix}")

        # Stage 7 currently keeps authoritative execution on v1.
        if row["selected_procedure_schema_version"] != "v1":
            blockers.append(f"AUTHORITATIVE_V1_REQUIRED:{prefix}:procedure")
        if row["selected_observation_schema_version"] != "v1":
            blockers.append(f"AUTHORITATIVE_V1_REQUIRED:{prefix}:observation")

    canonical = json.dumps(
        {
            "summary": summary,
            "sources": source_rows,
            "registers": registers,
            "rules": rule_rows,
            "tests": test_rows,
            "checklist": checklist_rows,
            "runtime": runtime_rows,
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
        "registers": len(registers),
        "rules": len(rule_rows),
        "tests": len(test_rows),
        "checklist": len(checklist_rows),
        "runtime_schemas": len(runtime_rows),
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
