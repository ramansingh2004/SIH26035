# OIML R 76 verified artifact intake directory

This directory is intentionally **not** an authoritative ruleset yet.

Phase 25 Stage 7 provides the fail-closed intake/registration/activation
machinery. A real `verified-v1` artifact may only be placed here after the
external regulatory verification package is complete.

Required final files:

- metadata.yaml
- classes.yaml
- mpe.yaml
- applicability.yaml
- voltage.yaml
- disturbances.yaml
- endurance.yaml
- checklist.yaml
- report_sections.yaml
- stage7_verification_manifest.json

`stage7_verification_manifest.template.json` is only a completion template.
It is not loaded and cannot authorize registration or activation.

Do not copy candidate YAML into this directory and label it VERIFIED.
Do not use developer, AI, or synthetic-test assertions as independent
regulatory sign-off.
