# Phase 25 Stage 2A — Common Rules + Sections 1–5 Source Verification

Stage 2A converts the official OIML R 76-1:2006 / R 76-2:2007 source material
for common metrological rules and Sections 1–5 into a controlled, clause-level
verification transcript and a source-to-engine gap matrix.

This stage deliberately does NOT mark any production rule VERIFIED.

Reason: the current engine policy schemas were designed to reject guessed
regulatory defaults, and the official source shows several requirements that are
instrument-dependent or evaluation-context-dependent. Encoding them as fixed
absolute values would be incorrect.

## Official source scope

Primary source:
- OIML R 76-1:2006 (E)
- https://www.oiml.org/en/files/pdf_r/r076-1-e06.pdf

Cross-check/report source:
- OIML R 76-2:2007 (E)
- https://www.oiml.org/en/files/pdf_r/r076-2-e07.pdf

## Stage 2A findings

The following are now source-mapped but remain pending independent verifier
sign-off:

- classification rules in 3.1/3.2;
- initial-verification MPE bands in 3.5.1 / Table 6;
- weighing procedure in A.4.4;
- temperature requirements in 3.9.2 and A.5.3;
- eccentricity in 3.6.2 and A.4.7;
- discrimination in 3.8 and A.4.8;
- sensitivity in 6.1 and A.4.9;
- repeatability in 3.6.1 and A.4.10.

## Engine gap rule

A source-mapped requirement may not be encoded as a fixed policy when the OIML
requirement depends on:

- accuracy class;
- evaluation context (type evaluation / initial verification / subsequent
  metrological control);
- Max, Min, d, e or n;
- additive tare effect;
- support-point count or receptor construction;
- declared temperature range;
- instrument indication mode.

Stage 2B must generalize the affected typed policy schemas before Stage 2C can
encode a reusable official ruleset.

## Regulatory state after Stage 2A

Unchanged:

- `candidate-v1` stays DRAFT;
- `supported_test_codes` stays empty;
- REG-01 through REG-17 remain unresolved until their respective acceptance;
- no rule is changed to `VERIFIED`;
- no source digest is fabricated;
- no activation or official issue gate is weakened.
