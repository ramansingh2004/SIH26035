# Phase 25 Stage 5 — Source mapping and engine-gap analysis

## Pinned editions

- OIML R 76-1 Edition 2006 (E)
- OIML R 76-2 Edition 2007 (E)

All facts in this package are **source-mapped candidate facts** and remain
pending independent regulatory verification.

## Section 16 — construction examination

R76-1 A.2 calls for examination of the instrument's devices against the
documentation. R76-1 A.3 links the initial examination to metrological
characteristics, descriptive markings and stamping/securing checks.

R76-2 Section 16 is an additional report page for construction information
that supplements the rest of the report and accompanying approval/certificate.
Candidate capture includes an overall instrument image, descriptions of main
components, remarks useful to verification authorities and manufacturer
references.

### Engine gap

The existing construction workflow is structurally suitable and fail closed.
The remaining gap is regulatory content: the candidate runtime artifact has
no independently verified Section 16 `construction_item_v1` catalog.

## Section 17 — checklist

R76-2 states that the checklist summarizes examinations and does not replace
the underlying R76-1 requirements.

The report divides the checklist into 17.1 general, 17.2 direct-sales,
17.3 electronic and 17.4 software-controlled groups.

R76-2 also states that non-self-indicating instruments use R76-1 clause 6 in
lieu of this checklist.

The Stage 5 candidate mapping connects the project's existing checklist
domains to the corresponding R76-1 clause families and R76-2 report groups.
It intentionally does not freeze exact wording, applicability logic or
evidence requirements.

### Engine gap

`ChecklistEngine` already fails closed when a row is not VERIFIED, its evidence
requirement is unresolved, applicability is unresolved/invalid, or required
responses/evidence are incomplete.

The remaining gap is independent verification of regulatory checklist content
and authoritative encoding of the non-self-indicating replacement branch.

## Stage 5 conclusion

No new compliance calculation path is invented for Sections 16–17. The safe
implementation work is source mapping, controlled candidate encoding, explicit
runtime ownership/gaps, and verification that candidate-v1 remains
review-blocked.
