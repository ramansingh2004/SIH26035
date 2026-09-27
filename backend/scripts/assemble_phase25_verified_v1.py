"""Assemble an independently reviewed Phase 25 pack into verified-v1 staging.

This tool never fabricates regulatory signoff. It refuses to run unless the
external-review validator reports zero blockers, including the exact executable
rule review and final independent regulatory declaration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from app.compliance.ruleset import RuleSet, load_ruleset
from app.compliance.stage7_activation import Stage7VerificationManifest, inspect_verified_artifact
from app.compliance.suite import IMPLEMENTED_TEST_CODES
from app.compliance.verified_blueprint import executable_rule_blueprint, verified_test_dependencies
from scripts.validate_phase25_external_review import validate_pack


class AssemblyError(ValueError):
    pass


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in {"true", "false"}:
        raise AssemblyError(f"Invalid strict boolean: {value!r}")
    return lowered == "true"


def _source(row: dict[str, str]) -> dict:
    return {
        "part": row["verified_source_part"],
        "edition": row["verified_source_edition"],
        "identity": row["verified_source_identity"],
        "clause": row["verified_source_clause"],
        "digest": row["verified_source_digest"],
    }


def _verification(row: dict[str, str], *, actor_field: str = "verified_by") -> dict:
    return {
        "status": "VERIFIED",
        "verified_by": row[actor_field],
        "verified_at": row["verified_at"],
        "evidence": row["evidence_reference"],
    }


def _canonical_policy(value: str) -> str:
    parsed = json.loads(value)
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def assemble_verified_v1(
    review_dir: Path,
    evidence_package: Path,
    output_dir: Path,
) -> dict[str, object]:
    review_dir = review_dir.resolve()
    evidence_package = evidence_package.resolve()
    output_dir = output_dir.resolve()

    validation = validate_pack(review_dir)
    if not validation["valid"]:
        raise AssemblyError(
            "External review pack is not assembly-ready:\n"
            + "\n".join(f"- {item}" for item in validation["blockers"])
        )
    if not evidence_package.is_file():
        raise AssemblyError("Evidence package ZIP/file does not exist")
    if output_dir.exists():
        raise AssemblyError("Output directory already exists")

    candidate = load_ruleset()
    blueprint = executable_rule_blueprint(candidate)
    dependency_map = verified_test_dependencies(candidate)

    executable_rows = {
        row["rule_key"]: row for row in _read(review_dir / "07_executable_rule_review.csv")
    }
    test_rows = {row["item_key"]: row for row in _read(review_dir / "04_test_review.csv")}
    checklist_rows = {
        row["item_key"]: row for row in _read(review_dir / "05_checklist_review.csv")
    }

    rules: list[dict] = []
    for item in blueprint:
        row = executable_rows[item.rule_key]
        kind = row["selected_kind"]
        parameters = []
        if kind != "dependency_v1":
            parameters = [
                {
                    "name": "POLICY_JSON",
                    "value": _canonical_policy(row["verified_policy_json"]),
                    "unit": None,
                    "numeric": False,
                }
            ]
        rules.append(
            {
                "key": item.rule_key,
                "section": item.section,
                "kind": kind,
                "description": item.description,
                "source": _source(row),
                "verification": _verification(row),
                "dependencies": list(item.required_dependencies),
                "blockers": [],
                "parameters": parameters,
            }
        )

    candidate_tests = {item.code: item for item in candidate.tests}
    implemented = set(IMPLEMENTED_TEST_CODES)
    tests: list[dict] = []
    for code, item in sorted(
        candidate_tests.items(), key=lambda pair: (pair[1].section, pair[0])
    ):
        row = test_rows[code]
        tests.append(
            {
                "code": code,
                "section": item.section,
                "name": item.name,
                "parent": item.parent,
                "family": item.family,
                "source": _source(row),
                "dependencies": list(dependency_map[code]),
                "implemented": code in implemented,
                "verification": _verification(row),
            }
        )

    candidate_checklist = {item.key: item for item in candidate.checklist}
    checklist: list[dict] = []
    for key, item in sorted(candidate_checklist.items()):
        row = checklist_rows[key]
        checklist.append(
            {
                "key": key,
                "group": item.group,
                "text": row["verified_text"],
                "source": _source(row),
                "applicability": json.loads(row["verified_applicability_policy_json"]),
                "evidence_required": _bool(row["verified_evidence_required"]),
                "verification": _verification(row),
            }
        )

    standard_parts = []
    seen = set()
    for item in (*rules, *tests, *checklist):
        source = item["source"]
        key = (
            source["part"],
            source["edition"],
            source["identity"],
            source["digest"],
        )
        if key in seen:
            continue
        seen.add(key)
        standard_parts.append(
            {
                "part": source["part"],
                "edition": source["edition"],
                "identity": source["identity"],
                "clause": None,
                "digest": source["digest"],
            }
        )

    metadata = {
        "schema_version": 1,
        "standard_code": candidate.metadata.standard_code,
        "standard_name": candidate.metadata.standard_name,
        "edition": candidate.metadata.edition,
        "version": "verified-v1",
        "standard_parts": standard_parts,
        "supported_test_codes": list(IMPLEMENTED_TEST_CODES),
        "source_reference": (
            "Phase 25 independent external review pack "
            f"SHA-256:{validation['review_pack_sha256']}"
        ),
    }

    ruleset = RuleSet.model_validate(
        {
            "metadata": metadata,
            "rules": rules,
            "tests": tests,
            "checklist": checklist,
        }
    )

    output_dir.mkdir(parents=True)
    _write_json(output_dir / "metadata.yaml", ruleset.metadata.model_dump(mode="json"))

    dumped = ruleset.model_dump(mode="json")
    dumped_rules = {item["key"]: item for item in dumped["rules"]}
    for bucket in (
        "classes",
        "mpe",
        "applicability",
        "voltage",
        "disturbances",
        "endurance",
        "checklist",
    ):
        selected = [
            dumped_rules[item.rule_key]
            for item in blueprint
            if item.file_bucket == bucket
        ]
        payload = {"schema_version": 1, "rules": selected}
        if bucket == "checklist":
            payload["checklist"] = dumped["checklist"]
        _write_json(output_dir / f"{bucket}.yaml", payload)

    _write_json(
        output_dir / "report_sections.yaml",
        {"schema_version": 1, "tests": dumped["tests"]},
    )

    source_rows = _read(review_dir / "01_source_evidence.csv")
    document_rows = _read(review_dir / "01a_source_documents.csv")
    register_rows = _read(review_dir / "02_register_signoff.csv")
    runtime_rows = _read(review_dir / "06_runtime_schema_review.csv")
    declaration = json.loads(
        (review_dir / "08_final_regulatory_declaration.json").read_text(encoding="utf-8")
    )

    source_evidence = [
        {
            "source_id": row["source_id"],
            "part": row["part"],
            "edition": row["edition"],
            "identity": row["identity"],
            "official_url": row["discovery_url"],
            "current_through": row["current_through"],
            "amendment_set_complete": True,
            "verified_by": row["verified_by"],
            "verified_at": row["verified_at"],
            "evidence_reference": row["evidence_reference"],
            "independent_of_implementation": True,
        }
        for row in source_rows
    ]
    source_documents = [
        {
            "source_id": row["source_id"],
            "document_id": row["document_id"],
            "identity": row["identity"],
            "official_url": row["official_url"],
            "sha256": row["sha256"],
            "acquired_at": row["acquired_at"],
            "acquisition_reference": row["acquisition_reference"],
            "document_notes": row.get("document_notes") or None,
        }
        for row in document_rows
    ]
    register_signoffs = [
        {
            "register_id": row["register_id"],
            "status": "VERIFIED",
            "verified_by": row["verified_by"],
            "verifier_role": row["verifier_role"],
            "verifier_organization": row["verifier_organization"],
            "verified_at": row["verified_at"],
            "evidence_reference": row["evidence_reference"],
            "independent_of_implementation": True,
        }
        for row in register_rows
    ]

    item_signoffs = []
    for item in blueprint:
        row = executable_rows[item.rule_key]
        item_signoffs.append(
            {
                "item_type": "RULE",
                "item_key": item.rule_key,
                "source_part": row["verified_source_part"],
                "source_edition": row["verified_source_edition"],
                "source_identity": row["verified_source_identity"],
                "source_clause": row["verified_source_clause"],
                "source_digest": row["verified_source_digest"],
                "verified_by": row["verified_by"],
                "verifier_role": row["verifier_role"],
                "verified_at": row["verified_at"],
                "evidence_reference": row["evidence_reference"],
                "independent_of_implementation": True,
            }
        )
    for code in sorted(candidate_tests):
        row = test_rows[code]
        item_signoffs.append(
            {
                "item_type": "TEST",
                "item_key": code,
                "source_part": row["verified_source_part"],
                "source_edition": row["verified_source_edition"],
                "source_identity": row["verified_source_identity"],
                "source_clause": row["verified_source_clause"],
                "source_digest": row["verified_source_digest"],
                "verified_by": row["verified_by"],
                "verifier_role": row["verifier_role"],
                "verified_at": row["verified_at"],
                "evidence_reference": row["evidence_reference"],
                "independent_of_implementation": True,
            }
        )
    for key in sorted(candidate_checklist):
        row = checklist_rows[key]
        item_signoffs.append(
            {
                "item_type": "CHECKLIST",
                "item_key": key,
                "source_part": row["verified_source_part"],
                "source_edition": row["verified_source_edition"],
                "source_identity": row["verified_source_identity"],
                "source_clause": row["verified_source_clause"],
                "source_digest": row["verified_source_digest"],
                "verified_by": row["verified_by"],
                "verifier_role": row["verifier_role"],
                "verified_at": row["verified_at"],
                "evidence_reference": row["evidence_reference"],
                "independent_of_implementation": True,
            }
        )

    runtime_schemas = [
        {
            "test_code": row["test_code"],
            "procedure_schema_version": row["selected_procedure_schema_version"],
            "observation_schema_version": row["selected_observation_schema_version"],
            "runtime_binding_sha256": row["selected_runtime_binding_sha256"],
            "status": "VERIFIED",
            "reviewed_by": row["reviewed_by"],
            "reviewer_role": row["reviewer_role"],
            "reviewer_organization": row["reviewer_organization"],
            "reviewed_at": row["reviewed_at"],
            "evidence_reference": row["evidence_reference"],
            "independent_of_implementation": True,
        }
        for row in runtime_rows
    ]

    summary = json.loads((review_dir / "00_summary.json").read_text(encoding="utf-8"))
    manifest = Stage7VerificationManifest.model_validate(
        {
            "schema_version": 1,
            "artifact_id": "oiml_r76_2006/verified-v1",
            "target_standard_code": "OIML_R76",
            "target_edition": candidate.metadata.edition,
            "target_version": "verified-v1",
            "candidate_configuration_hash": summary["candidate_configuration_hash"],
            "verified_configuration_hash": ruleset.configuration_hash,
            "evidence_package_sha256": _sha256(evidence_package),
            "regulatory_signoff": declaration["regulatory_signoff"],
            "source_evidence": source_evidence,
            "source_documents": source_documents,
            "register_signoffs": register_signoffs,
            "item_signoffs": item_signoffs,
            "runtime_schemas": runtime_schemas,
        }
    )
    _write_json(
        output_dir / "stage7_verification_manifest.json",
        manifest.model_dump(mode="json"),
    )

    readiness = inspect_verified_artifact(output_dir)
    if not readiness.ready:
        raise AssemblyError(
            "Assembled artifact failed Stage 7 intake:\n"
            + "\n".join(f"- {item}" for item in readiness.blockers)
        )

    return {
        "candidate_hash": readiness.candidate_hash,
        "verified_hash": readiness.verified_hash,
        "manifest_hash": readiness.manifest_hash,
        "review_pack_hash": validation["review_pack_sha256"],
        "evidence_package_sha256": _sha256(evidence_package),
        "rules": len(rules),
        "tests": len(tests),
        "checklist": len(checklist),
        "runtime_schemas": len(runtime_schemas),
        "ready": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--evidence-package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = assemble_verified_v1(args.input, args.evidence_package, args.output)
    except AssemblyError as exc:
        print(str(exc))
        raise SystemExit(1) from None

    print("Phase 25 verified-v1 staging assembly passed Stage 7 intake.")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
