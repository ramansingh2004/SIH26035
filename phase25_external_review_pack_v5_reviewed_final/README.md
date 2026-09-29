# SIH26035 — Phase 25 External Independent Review Pack

## Purpose

This directory contains the completed Phase 25 external independent-review handoff for the SIH26035 OIML R 76 compliance project.

- **Assembly contract:** `verified-blueprint-v1`
- **Candidate configuration hash:** `e795f71177ad2c0745417d92cd0010b6d895607a3768c3a21bf9bbe283c5a26b`
- **Candidate version:** `candidate-v1`
- **Candidate edition:** `R76-1:2006 / R76-2:2007`

The review package records the reviewer decisions for source evidence, source documents, regulatory registers, candidate rule mappings, test mappings, checklist mappings, runtime schema bindings, executable rules, and the final regulatory declaration.

## Required Files

The completed review directory must contain these exact canonical filenames:

```text
00_summary.json
01_source_evidence.csv
01a_source_documents.csv
02_register_signoff.csv
03_rule_review.csv
04_test_review.csv
05_checklist_review.csv
06_runtime_schema_review.csv
07_executable_rule_review.csv
08_final_regulatory_declaration.json
README.md
```

Do not rename these files or add upload suffixes such as `(1)`, `(2)`, etc. when running the validator.

## Review Status

The completed reviewer return includes:

- source-family review and source-document provenance;
- REG-01 through REG-17 sign-off;
- candidate regulatory rule review;
- test-definition review;
- checklist-item review;
- runtime schema and exact runtime-binding review;
- 100 executable-rule review rows;
- final regulatory declaration.

The final declaration records:

```text
regulatory_signoff = true
signed_by = Dr. Y.G prajapati
signer_role = Independent Regulatory Reviewer
signer_organization = Independent Reviewer
signed_at = 2026-09-29T09:58:00+05:30
independent_of_implementation = true
```

The candidate configuration hash and assembly contract version must remain unchanged across the review package.

## Reviewer-Locked Runtime File

`06_runtime_schema_review.csv` contains the reviewer-selected procedure schema version, observation schema version, and exact runtime-binding SHA-256 for each implemented evaluator.

The runtime review verifies the selected software binding for the implementation being reviewed. It does not alter the exported implementation metadata or available runtime-binding catalog.

## Reviewer-Locked Executable Rules

`07_executable_rule_review.csv` contains all 100 executable-rule review rows.

The completed file contains:

```text
100 VERIFIED executable-rule rows
70 policy-bearing rows with policy JSON
30 dependency_v1 rows
0 missing required policy JSON
```

The Section 12 disturbance procedure policies are represented using the exported `disturbance_procedure_v2` schema. Detailed physical laboratory waveform/setup execution remains tied to the referenced IEC/ISO standards and retained evidence rather than being synthesized by the web application.

## Final Regulatory Declaration

`08_final_regulatory_declaration.json` is the final reviewer declaration for this package.

It must preserve:

```text
schema_version = 1
candidate_configuration_hash = e795f71177ad2c0745417d92cd0010b6d895607a3768c3a21bf9bbe283c5a26b
assembly_contract_version = verified-blueprint-v1
```

The declaration references the completed File 6 and File 7 review outputs.

## Validation

Place all required files in one directory, for example:

```text
phase25_external_review_pack_v5_reviewed_final/
```

Then run from the backend directory:

```powershell
cd D:\SIH\sih26035\backend

uv run python -m scripts.validate_phase25_external_review `
  --input ..\phase25_external_review_pack_v5_reviewed_final
```

A successful structural/consistency validation should report:

```text
External review pack valid: True
Blocker count: 0
```

The validator checks the completed handoff for internal completeness and consistency against the candidate implementation. A validator pass does not itself install, activate, or authorize a production ruleset.

## Package Handling

Keep the reviewer-returned files together as one controlled package.

Recommended archive name:

```text
phase25_external_review_pack_v5_reviewed_final.zip
```

If the validator reports a blocker, correct the specific file or cross-file inconsistency and rerun validation before proceeding to verified-ruleset assembly or activation steps.
