# Phase 25 — Engineering Closeout and External Verification Handoff

## Repository state

All Phase 25 engineering stages are complete through Stage 8.

The remaining work is **not another implementation phase**. It consists of:

1. independent regulatory verification of the mapped OIML/Indian requirements;
2. assembly of the immutable `verified-v1` artifact;
3. Stage 7 registration/validation/activation;
4. execution of the real Stage 8 authoritative walkthrough.

## What this closeout package adds

This package adds two offline tools:

- `export_phase25_external_review.py`
- `validate_phase25_external_review.py`

The exporter creates a reviewer handoff directory containing:

- source evidence worksheet;
- REG-01 through REG-17 sign-off worksheet;
- every candidate rule;
- every candidate test definition;
- every candidate checklist item;
- every implemented runtime schema selection.

The validator checks completeness, exact item sets, SHA-256 shapes,
timezone-aware timestamps, independence declarations, checklist policy JSON and
runtime schema availability.

## Important boundary

A validator PASS means only that the external-review pack is structurally
complete.

It does **not**:

- independently verify OIML requirements;
- verify Indian legal-metrology interpretation;
- promote candidate fields;
- create `verified-v1`;
- activate a ruleset;
- complete Stage 8.

The actual reviewer must be independent of implementation and must preserve the
controlled official-source bytes/evidence referenced by the pack.

## Current pinned public source set

The current project pins OIML R 76-1:2006 and R 76-2:2007 and separately maps
Indian Legal Metrology authority requirements. Exact source bytes and hashes
must be acquired and retained by the external verification workflow.

## Handoff workflow

Export:

`uv run python -m scripts.export_phase25_external_review --output <directory>`

The independent reviewer completes that directory.

Validate:

`uv run python -m scripts.validate_phase25_external_review --input <directory>`

After the pack is independently completed and validated, the regulatory artifact
owner assembles the reviewed content into the fixed Stage 7
`oiml_r76_2006_verified` directory and supplies the completed
`stage7_verification_manifest.json`.

Then run:

- `uv run python -m scripts.verify_phase25_stage7`
- register `oiml_r76_2006/verified-v1`
- validate the registered artifact
- activate it
- `uv run python -m scripts.verify_phase25_stage8`
- execute the real Stage 8 runbook.

## Completion definition

Phase 25 engineering: **COMPLETE**

Independent regulatory verification: **PENDING**

Authoritative verified-v1 activation: **PENDING**

Authoritative Stage 8 walkthrough: **PENDING**
