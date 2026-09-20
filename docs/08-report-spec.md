# SIH26035 — Report Specification

Specification Freeze v1 — 2026-09-20. See [DECISIONS.md](../DECISIONS.md) F12, [05-database-schema.md](05-database-schema.md) and [06-api-spec.md](06-api-spec.md).

## 1. Two separate deliverables

**Unofficial preview:** capture a consistent working snapshot at a session regulatory_revision. It may include incomplete, stale or unverified sections, clearly labeled. Watermark UNOFFICIAL PREVIEW; no official report number, approval implication or issue action. Store in report_previews with private files and explicit expiry; preview access still requires lab authorization.

**Official report:** generation requires APPROVED workflow, COMPLETE evaluation, current valid results, required evidence and determined COMPLIANT or NONCOMPLIANT outcome. A completed failure is a legitimate report outcome. Missing rules, unknown applicability, unfinished/stale work or invalidated review blocks generation/issue. report:generate does not grant report:issue. Both PDF and editable DOCX are mandatory.

## 2. Immutable ReportContext and generation

Final approval captures an immutable session_approval_snapshot, including historical master/actor/evidence facts. The report service reads that approved snapshot, adds reserved report/issue/render metadata under a session lock, verifies regulatory_revision and persists report_context_snapshot before rendering. It never assembles approved facts from mutable master records. This snapshot is immutable on each report_generations record. A report points to the chosen generation; a new render attempt needing changed content creates a new snapshot/attempt, never updates the old context.

The context contains report metadata/number/revision; planned_issue_date and intended issuer; frozen laboratory/manufacturer identity/address/contact/logo; instrument/ranges/components; all 17 section applicability/readiness/outcome summaries; exact observations, typed procedure context, calculations/limits/references and selected results; relevant previous evaluations/retest reasons; equipment/calibration and environmental snapshots; construction; full checklist rule wording and responses; evidence identities/content hashes/object versions; approval names/roles/timestamps and reviewed revision; standard parts/editions, rule hash/version, engine/schema/context/template/renderer identities. Exclude password/token/secret data.

Both renderers consume exactly this context and referenced immutable evidence bytes. They must not query live manufacturers, users, calibration records or rule tables, and must not rerun compliance calculations. Graphs plot stored values; any display rounding never changes values used in the stored decisions. PDF/DOCX must be semantically equivalent, not necessarily byte/pixel-identical.

Store template artifacts, fonts, renderer/runtime identities and rule/engine artifacts with the version manifest for reproducibility. Retain original issued bytes as authoritative; metadata such as PDF creation dates may prevent byte-identical regeneration. Report-context golden tests verify semantic reproducibility.

## 3. Numbering, issue, failures and revisions

Official series uses R76-<year>-<atomic sequence>; number allocation is global and concurrency-safe. UNIQUE(report_number, revision_no), with positive revisions, root_report_id, supersedes_report_id and revision_reason. report_status is UNISSUED/ISSUED/SUPERSEDED; generation_status is GENERATING/READY/FAILED. Neither is the session compliance outcome.

Generation reserves metadata and produces staged private files outside DB locks. Both formats/hashes must be READY before issue; a failed DOCX/PDF pair cannot issue partially. Staged retry artifacts cannot overwrite issued objects. File publication, selected generation and audit are finalized transactionally after object verification. Use persistent generation attempts/idempotency keys; crash recovery checks state/object hashes before retry.

At issue, the authenticated user requires explicit lab-scoped report:issue, the session remains APPROVED with the captured current revision, intended_issuer_id matches, and current UTC calendar date equals planned_issue_date. Printed issue metadata is the date; printed approval timestamps come from frozen approval actions. If issuer/date changed, regenerate an unissued attempt/context first. Actual issued_at is recorded separately in the immutable issuance manifest and report row; do not edit rendered bytes to insert a later timestamp. This v1 numbering/date convention remains subject to REG-17 authority acceptance before real official use.

Issue atomically marks the report ISSUED, the session REPORT_ISSUED and, for a revision, its expected predecessor SUPERSEDED. A unique partial index permits one current ISSUED report per series. Old context/files remain readable. An unissued/failed successor leaves the original current. Concurrent successors compare expected predecessor and reject stale chains.

Post-approval corrections require a new linked session revision, fresh evaluation/review/final approval and then a same-number report revision. No editorial bypass exists in v1. A user-edited exported DOCX is an external edited copy; it never replaces the canonical issued object or updates its compliance decisions.

Context hash excludes its own hash field; file hashes cover exact bytes; report hash covers context hash plus per-format file hashes. The issue manifest records report/generation/hash/actor/time/predecessor without a self-referential hash. Hashes provide integrity, not an optional digital signature or certification claim.

# 4. Page 1 — cover page

Include:

```text
laboratory name
laboratory logo if configured
report title
report number
revision
application number
instrument model
manufacturer
date of issue
report status
```

Suggested title:

```text
OIML R 76
NON-AUTOMATIC WEIGHING INSTRUMENT
TYPE-EVALUATION TEST REPORT
```

---

# 5. Document-control block

Include:

```text
Report Number
Revision
Issue Date
Test Session ID
Application Number
Ruleset
Standard Edition
Ruleset Version
Engine Version
```

Optional printed integrity reference: context_hash. The final report manifest/file hashes are available in repository metadata; do not recursively embed the file hash in its own bytes.

---

# 6. Laboratory details

Include:

```text
laboratory name
address
contact details
accreditation/reference number if applicable
```

---

# 7. Manufacturer details

Include:

```text
manufacturer name
registration/reference
address
contact person
email
phone
country
```

---

# 8. Instrument identification

Include:

```text
model name
type designation
serial number
accuracy class

Max
Min
d
e
n

range type
indication type
electronic/non-electronic
self-indicating
software-controlled
portable/mobile

load receptor
support points

tare type
maximum tare

zero-setting type
zero tracking

power supply
temperature range
software identifier
```

For multi-range instruments include a range table.

---

# 9. Instrument range table

Columns:

```text
Range
Min
Max
d
e
```

---

# 10. Ruleset declaration

Example:

```text
Standard:
OIML R 76

Requirements edition:
R76-1:2006 (candidate until verified)

Report-format edition:
R76-2:2007 (candidate until verified)

Ruleset Version:
1.0.0

Ruleset Configuration Hash:
...
```

Also list relevant national/legal framework references if configured.

---

# 11. Test equipment table

Columns:

```text
Equipment Type
Manufacturer
Model
Serial No.
Reference No.
Calibration Certificate
Calibration Date
Calibration Due
Accuracy/Class
```

Only include equipment linked to the test session.

---

# 12. Environmental conditions

For short tests:

```text
Start
Maximum/Minimum where needed
End
```

For long-duration tests use dedicated tables/graphs.

Columns:

```text
Date/Time
Test/Phase
Temperature
Relative Humidity
Barometric Pressure
Remarks
```

---

# 13. Executive summary of all 17 sections

Required summary table (render actual stored values; no assumed PASS):

| No. | Section | Applicability | Evaluation status | Compliance outcome | Remarks |
|---:|---|---|---|---|---|
| 1 | Weighing Performance | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 2 | Temperature Effect | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 3 | Eccentricity | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 4 | Discrimination / Sensitivity | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 5 | Repeatability | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 6 | Time Dependence | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 7 | Stability of Equilibrium | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 8 | Tilting | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 9 | Tare | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 10 | Warm-up | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 11 | Voltage Variations | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 12 | Electrical Disturbances | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 13 | Damp Heat | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 14 | Span Stability | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 15 | Endurance | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 16 | Construction Examination | Stored decision | Stored readiness | Stored outcome | Stored reason |
| 17 | Checklist | Stored decision | Stored readiness | Stored outcome | Stored reason |

This table must always show all 17 top-level sections.

---

# 14. Section 1 — Weighing Performance

Header:

```text
Section 1 — Weighing Performance
```

Include procedure metadata.

Recommended result table:

```text
Direction
Load L
Indication I
Additional Load ΔL
P
E
E0
Ec
MPE
Result
```

Include:

```text
loading sequence
unloading sequence
```

Optional graph:

```text
load vs corrected error
load vs MPE boundaries
```

Do not rely on a graph as the only result evidence.

---

# 15. Section 2 — Temperature Effect on No-load Indication

Table:

```text
Temperature
Zero Indication
ΔL
P
Previous Temperature
ΔT
ΔP
Normalized Drift
Allowed Drift
Result
```

Include declared temperature range.

---

# 16. Section 3 — Eccentricity

Include load-receptor diagram if available.

Table:

```text
Position
Load
Indication
ΔL
E
E0
Ec
MPE
Result
```

For rolling load:

```text
direction
position
```

---

# 17. Section 4 — Discrimination and Sensitivity

Split into subsections:

```text
4.1 Discrimination
4.2 Sensitivity
```

Discrimination table:

```text
Load
Initial Indication
Additional Load
Final Indication
Required Response
Actual Response
Result
```

Sensitivity table:

```text
Load
Applied Increment
Initial Position
Final Position
Displacement
Required Condition
Result
```

If sensitivity is not applicable:

```text
NOT APPLICABLE
Reason: ...
```

---

# 18. Section 5 — Repeatability

Per series:

```text
Target Load
Repetition
Indication
Error
Corrected Error
Individual MPE Result
```

Summary:

```text
Emin
Emax
Emax - Emin
Allowed range
Series result
```

---

# 19. Section 6 — Time Dependence

## 6.1 Zero Return

Table:

```text
Initial Zero
Applied Load
Load Duration
Final Zero
Deviation
Limit
Result
```

## 6.2 Creep

Table:

```text
Elapsed Time
Indication
Change from Initial
```

Include time-series chart.

Display:

```text
short-test condition
extended-test condition if applicable
overall result
```

---

# 20. Section 7 — Stability of Equilibrium

Split:

```text
printing/storage
zero operation
tare operation
```

Table example:

```text
Trial
Operation
Initial State
First Stored/Printed Value
Subsequent Values
Deviation
Allowed
Result
```

---

# 21. Section 8 — Tilting

Table:

```text
Direction
Tilt
Load
Reference Indication/Error
Tilted Indication/Error
Difference
Allowed Difference
Result
```

Also include tilt-device functional checks.

---

# 22. Section 9 — Tare

Table:

```text
Tare Type
Tare Value
Gross Load
Net Load
Indication
ΔL
E
E0
Ec
MPE
Result
```

---

# 23. Section 10 — Warm-up Time

Table:

```text
Elapsed Time
Zero Error
Applied Load
Loaded Error
Corrected Error
MPE
Result
```

---

# 24. Section 11 — Voltage Variations

Declare supply type.

Table:

```text
Applied Voltage
Voltage Condition
Load
Indication
Corrected Error
MPE
Operational State
Result
```

---

# 25. Section 12 — Electrical Disturbances

Show subtest summary first:

| Subtest | Applicable | Result |
|---|---|---|
| Voltage dips | Yes | PASS |
| Bursts | Yes | PASS |
| Surges | No | N/A |
| ESD | Yes | PASS |
| Radiated RF | Yes | PASS |
| Conducted RF | Yes | PASS |
| Vehicle supply transients | No | N/A |

Each applicable subtest gets a detailed table.

---

## 25.1 Voltage dips/interruptions

Columns:

```text
Case
Reduction
Duration/Cycles
Reference Indication
Disturbed Indication
Difference
Fault Detected
Fault Response
Result
```

---

## 25.2 Bursts

```text
Line Type
Polarity
Amplitude
Reference
Disturbed
Difference
Fault Response
Result
```

---

## 25.3 Surges

```text
Coupling
Polarity
Surge Voltage
Reference
Disturbed
Difference
Fault Response
Result
```

---

## 25.4 ESD

```text
Mode
Location
Voltage
Polarity
Discharge No.
Reference
Disturbed
Difference
Fault Response
Result
```

---

## 25.5 Radiated RF

```text
Frequency
Field Strength
Modulation
Reference
Disturbed
Difference
Fault Response
Result
```

---

## 25.6 Conducted RF

```text
Frequency
Amplitude
Port
Reference
Disturbed
Difference
Fault Response
Result
```

---

## 25.7 Vehicle supply transients

```text
Pulse
Line
Voltage
Reference
Disturbed
Difference
Fault Response
Result
```

---

# 26. Section 13 — Damp Heat

Use three-stage structure:

```text
Initial Reference
High Temperature / Humidity
Final Reference
```

Table:

```text
Stage
Temperature
RH
Load
Ec
MPE
Functional State
Result
```

---

# 27. Section 14 — Span Stability

Table:

```text
Measurement No.
Date/Time
Temperature
RH
Event
Load
Zero Error
Loaded Error
Corrected Span Error
```

Summary:

```text
minimum
maximum
variation
allowed variation
trend assessment
result
```

Include time-series graph.

---

# 28. Section 15 — Endurance

Include:

```text
target cycling load
required cycles
completed cycles
cycle start
cycle end
equipment
abnormal events
```

Pre/post table:

```text
Load
Initial Ec
Final Ec
Durability Error
Allowed
Result
```

---

# 29. Section 16 — Examination of Construction

This section is not a fake numeric test.

Include structured dossier.

Suggested headings:

```text
16.1 General instrument description
16.2 Load receptor / transmitting system
16.3 Load cells
16.4 Indicator/display
16.5 Printer/peripherals
16.6 Power supply
16.7 Communication interfaces
16.8 Level/tilt devices
16.9 Zero/tare controls
16.10 Sealing/security
16.11 Software
16.12 Photographs/documents
```

Each item:

```text
description
manufacturer/model
certificate/reference
status
remarks
evidence reference
```

---

# 30. Section 17 — Checklist

Group by:

```text
General
Direct Sales
Electronic
Software-Controlled
```

Columns:

```text
Requirement
Clause
Applicability
Result
Remarks
Evidence
```

Possible result values:

```text
PASS
FAIL
NOT_APPLICABLE
NOT_EXAMINED
```

At the end show checklist totals.

---

# 31. Overall evaluation

Include:

```text
workflow_status
evaluation_status
compliance_outcome
failed required sections
review-required items
open remarks
```

Do not invent a simple “certified” statement unless the authority's workflow explicitly requires it.

---

# 32. Remarks

Include a dedicated remarks section for:

```text
technical observations
limitations
deviations
retest notes
```

---

# 33. Approval block

Include:

```text
Tested / Entered By
Technical Reviewer
Approving Officer
```

Fields:

```text
name
role
date/time
optional signature reference
```

Digital signatures can be added later.

---

# 34. Attachments index

List:

```text
instrument photos
construction photos
calibration certificates
supporting documents
additional test evidence
```

Do not embed huge files into DOCX/PDF unnecessarily.

Reference them by attachment number.

---

# 35. Footer/header

Recommended footer:

```text
Report Number
Revision
Page X of Y
```

Header may include lab name/logo.

---

# 36. Report status watermark

Unofficial preview outputs have a conspicuous UNOFFICIAL PREVIEW watermark and no official report number. They may additionally display DRAFT/UNDER_REVIEW as workflow metadata. Official files generated from an approved immutable context are private UNISSUED artifacts until explicit issue; the API/download screen must clearly show UNISSUED. The issued PDF/DOCX use those exact bytes and have no preview watermark. Do not add/remove a watermark by mutating an issued file. A SUPERSEDED report retains its original bytes; supersession is shown in repository metadata and revision history.

---

# 37. File naming

Recommended:

```text
R76_<report-number>_Rev<revision>.pdf
R76_<report-number>_Rev<revision>.docx
```

Sanitize filenames.

---

# 38. Hashing

After generation:

```text
SHA-256
```

Store separate context_hash, SHA-256 for each PDF/DOCX file, and report_hash over the canonical manifest of context_hash plus the format/file hashes. Do not place a file’s own final hash inside the bytes it hashes. Actual issue timestamp belongs to an immutable issuance manifest stored alongside the report.

---

# 39. Report generation constraints

The renderer must:

```text
use stored calculation results
preserve Decimal formatting
avoid recomputing OIML logic
show N/A explicitly
show ruleset version
show failed conditions
```

---

# 40. Report definition of done

A report is complete when:

```text
all 17 sections appear
workflow_status, evaluation_status and compliance_outcome are distinct
applicability is visible
test results are traceable
rule references are visible
equipment/environment data are present
construction and checklist are included
approval is included
PDF and DOCX contain equivalent content
```


# 41. Additional freeze acceptance tests

- Preview of an incomplete/unverified session is labeled unofficial and cannot be issued.
- Official COMPLETE/NONCOMPLIANT evaluation produces equivalent PDF/DOCX with explicit failures.
- Master lab/manufacturer/equipment/user edits leave the persisted report context and regenerated semantic content unchanged.
- Approved snapshot/review revisions are rechecked; stale or unverified required data cannot issue.
- A failure in one renderer leaves generation FAILED/UNISSUED and never supersedes the old report.
- Intended issuer/planned issue date mismatch forces a new unissued generation attempt.
- Concurrent issue/revision attempts preserve one current report and immutable prior bytes.
- Result traces use corrected_error_g=20 for the corrected weighing fixture, with no report-side recomputation.
- Context/template/schema/engine/rule hashes and all evidence identities are retained.
- Retests and superseded failed attempts remain traceable; no selective disappearance of unfavorable history.

Report layouts and clauses in this document are specification candidates, not a claim of authority acceptance; unresolved REG-01/REG-15/REG-17 items are gated by DECISIONS F18.
