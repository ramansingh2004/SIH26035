"""Export the Phase 25 candidate into an external-review handoff pack.

This script never marks regulatory content VERIFIED and never modifies the
trusted candidate or verified-artifact directories.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.compliance.ruleset import load_ruleset
from app.compliance.stage7_activation import (
    REQUIRED_REGISTERS,
    REQUIRED_SOURCE_IDS,
)
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
REGISTER_PATH = REPO / "docs" / "regulatory" / "phase25_verification_register.csv"
TEMPLATE_PATH = (
    BACKEND
    / "app"
    / "compliance"
    / "rules"
    / "oiml_r76_2006_verified"
    / "stage7_verification_manifest.template.json"
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_pack(output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    ruleset = load_ruleset()
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    summary = {
        "schema_version": 1,
        "purpose": "PHASE25_EXTERNAL_INDEPENDENT_REVIEW_HANDOFF",
        "candidate_configuration_hash": ruleset.configuration_hash,
        "candidate_version": ruleset.metadata.version,
        "candidate_edition": ruleset.metadata.edition,
        "candidate_supported_test_codes": list(ruleset.metadata.supported_test_codes),
        "required_registers": list(REQUIRED_REGISTERS),
        "required_source_ids": sorted(REQUIRED_SOURCE_IDS),
        "implemented_test_codes": sorted(IMPLEMENTED_TEST_CODES),
        "warning": (
            "This export is candidate material only. It is not regulatory "
            "verification and cannot authorize activation."
        ),
    }
    (output / "00_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    source_rows = []
    for row in template["source_evidence"]:
        source_rows.append(
            {
                "source_id": row["source_id"],
                "part": row["part"],
                "edition": row["edition"],
                "official_url": row["official_url"],
                "identity": "",
                "sha256": "",
                "acquired_at": "",
                "acquisition_reference": "",
                "verified_by": "",
                "verified_at": "",
                "evidence_reference": "",
                "independent_of_implementation": "false",
                "review_status": "PENDING",
            }
        )
    _write_csv(
        output / "01_source_evidence.csv",
        list(source_rows[0]),
        source_rows,
    )

    register_rows = []
    with REGISTER_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            register_rows.append(
                {
                    **row,
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
    _write_csv(
        output / "02_register_signoff.csv",
        list(register_rows[0]),
        register_rows,
    )

    rule_rows = []
    for item in sorted(ruleset.rules, key=lambda value: value.key):
        rule_rows.append(
            {
                "item_type": "RULE",
                "item_key": item.key,
                "section": "" if item.section is None else item.section,
                "kind": item.kind,
                "description": item.description,
                "source_part": item.source.part,
                "source_edition": item.source.edition,
                "candidate_source_identity": item.source.identity,
                "candidate_source_clause": item.source.clause or "",
                "candidate_source_digest": item.source.digest or "",
                "candidate_verification_status": item.verification.status,
                "candidate_blockers": json.dumps(list(item.blockers)),
                "candidate_parameters": json.dumps(
                    [value.model_dump(mode="json") for value in item.parameters],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "review_status": "PENDING",
                "verified_source_identity": "",
                "verified_source_clause": "",
                "verified_source_digest": "",
                "verified_by": "",
                "verifier_role": "",
                "verified_at": "",
                "evidence_reference": "",
                "independent_of_implementation": "false",
                "resolved_parameters_or_policy_reference": "",
                "review_notes": "",
            }
        )
    _write_csv(
        output / "03_rule_review.csv",
        list(rule_rows[0]),
        rule_rows,
    )

    test_rows = []
    for item in sorted(ruleset.tests, key=lambda value: (value.section, value.code)):
        test_rows.append(
            {
                "item_type": "TEST",
                "item_key": item.code,
                "section": item.section,
                "parent": item.parent or "",
                "family": item.family or "",
                "name": item.name,
                "implemented": str(item.implemented).lower(),
                "dependencies": json.dumps(list(item.dependencies)),
                "source_part": item.source.part,
                "source_edition": item.source.edition,
                "candidate_source_identity": item.source.identity,
                "candidate_source_clause": item.source.clause or "",
                "candidate_source_digest": item.source.digest or "",
                "candidate_verification_status": item.verification.status,
                "review_status": "PENDING",
                "verified_source_identity": "",
                "verified_source_clause": "",
                "verified_source_digest": "",
                "verified_by": "",
                "verifier_role": "",
                "verified_at": "",
                "evidence_reference": "",
                "independent_of_implementation": "false",
                "supported_after_review": "",
                "review_notes": "",
            }
        )
    _write_csv(
        output / "04_test_review.csv",
        list(test_rows[0]),
        test_rows,
    )

    checklist_rows = []
    for item in sorted(ruleset.checklist, key=lambda value: (value.group, value.key)):
        checklist_rows.append(
            {
                "item_type": "CHECKLIST",
                "item_key": item.key,
                "group": item.group,
                "candidate_text": item.text,
                "candidate_applicability": (
                    item.applicability
                    if isinstance(item.applicability, str)
                    else json.dumps(item.applicability.model_dump(mode="json"))
                ),
                "candidate_evidence_required": (
                    "" if item.evidence_required is None else str(item.evidence_required).lower()
                ),
                "source_part": item.source.part,
                "source_edition": item.source.edition,
                "candidate_source_identity": item.source.identity,
                "candidate_source_clause": item.source.clause or "",
                "candidate_source_digest": item.source.digest or "",
                "candidate_verification_status": item.verification.status,
                "review_status": "PENDING",
                "verified_text": "",
                "verified_applicability_policy_json": "",
                "verified_evidence_required": "",
                "verified_source_identity": "",
                "verified_source_clause": "",
                "verified_source_digest": "",
                "verified_by": "",
                "verifier_role": "",
                "verified_at": "",
                "evidence_reference": "",
                "independent_of_implementation": "false",
                "review_notes": "",
            }
        )
    _write_csv(
        output / "05_checklist_review.csv",
        list(checklist_rows[0]),
        checklist_rows,
    )

    registry = implemented_registry()
    runtime_rows = []
    for code in sorted(IMPLEMENTED_TEST_CODES):
        registration = registry.resolve(code)
        runtime_rows.append(
            {
                "test_code": code,
                "available_procedure_schema_versions": ";".join(
                    sorted(
                        {
                            value.procedure_schema_version
                            for value in registration.contexts.registrations
                        }
                    )
                ),
                "available_observation_schema_versions": ";".join(
                    sorted(
                        {
                            value.observation_schema_version
                            for value in registration.observations.registrations
                        }
                    )
                ),
                "selected_procedure_schema_version": "",
                "selected_observation_schema_version": "",
                "evidence_reference": "",
                "review_status": "PENDING",
                "reviewed_by": "",
                "reviewed_at": "",
                "review_notes": "",
            }
        )
    _write_csv(
        output / "06_runtime_schema_review.csv",
        list(runtime_rows[0]),
        runtime_rows,
    )

    readme = f"""# SIH26035 Phase 25 — External Independent Review Pack

Candidate configuration hash:

`{ruleset.configuration_hash}`

This pack is an export of the current candidate state. It is deliberately
PENDING. The reviewer must work from controlled official sources and must not
treat these candidate rows as authoritative.

The reviewer completes:

1. `01_source_evidence.csv`
2. `02_register_signoff.csv`
3. `03_rule_review.csv`
4. `04_test_review.csv`
5. `05_checklist_review.csv`
6. `06_runtime_schema_review.csv`

Do not overwrite candidate columns. Fill only the review/verified columns.

The source acquisitions must be retained outside this CSV pack with their exact
bytes and SHA-256 values.

A developer, AI model, extraction script, or synthetic test is not an
independent regulatory verifier.

After review, run:

`uv run python -m scripts.validate_phase25_external_review --input <pack>`

A passing review-pack validator still does not activate a ruleset. The reviewed
content must then be assembled into the immutable `verified-v1` artifact and
must pass the existing Stage 7 intake/registration/activation gates.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    return {
        "candidate_hash": ruleset.configuration_hash,
        "rules": len(rule_rows),
        "tests": len(test_rows),
        "checklist": len(checklist_rows),
        "runtime_schemas": len(runtime_rows),
        "registers": len(register_rows),
        "sources": len(source_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = export_pack(args.output)
    print("Phase 25 external review pack exported.")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
