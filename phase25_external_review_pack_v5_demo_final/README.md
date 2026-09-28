# DEMO-ONLY SYNTHETIC COPY

**NOT REGULATORY REVIEW. NOT VERIFIED-V1. NOT FOR OFFICIAL REPORT ISSUE.**

This directory was populated automatically for SIH26035 integration/demo work
while independent review is pending. Every review decision must be replaced by
the real reviewer's conclusion before production validation/assembly.

---

# SIH26035 Phase 25 — External Independent Review Pack

Candidate configuration hash:

`e795f71177ad2c0745417d92cd0010b6d895607a3768c3a21bf9bbe283c5a26b`

This pack is an export of the current candidate state. It is deliberately
PENDING. The reviewer must work from controlled official sources and must not
treat these candidate rows as authoritative.

The reviewer completes:

1. `01_source_evidence.csv` — logical source-family sign-off
2. `01a_source_documents.csv` — one row per actual controlled PDF/Gazette document
3. `02_register_signoff.csv`
4. `03_rule_review.csv`
5. `04_test_review.csv`
6. `05_checklist_review.csv`
7. `06_runtime_schema_review.csv`
8. `07_executable_rule_review.csv` — exact runtime/service rule surface
9. `08_final_regulatory_declaration.json` — overall human sign-off

Do not overwrite candidate columns. Fill only the review/verified columns.

Each actual source document must have its own identity, official URL, SHA-256,
acquisition timestamp and acquisition reference. A logical amended rule family
must not be represented by one SHA-256. The independent reviewer must add all
principal/amendment document rows needed for the family and explicitly attest in
`01_source_evidence.csv` that the amendment set is complete through the stated
`current_through` date. Exact source bytes must be retained outside this CSV pack.

A developer, AI model, extraction script, or synthetic test is not an
independent regulatory verifier.

After review, run:

`uv run python -m scripts.validate_phase25_external_review --input <pack>`

A passing review-pack validator still does not activate a ruleset. Runtime
schema selection must be independently reviewed against the exported immutable
runtime binding. A schema label alone never enables authority. Passing this validator does
not authority-enable a schema version. The reviewed content must then be assembled
into the immutable `verified-v1` artifact and pass the separate fail-closed Stage 7
intake/registration/activation gates.
