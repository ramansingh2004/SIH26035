# SIH26035 — Seventeen R76 Section Worksheets

Specification Freeze v1 — 2026-09-20. Architectural contracts are frozen in [DECISIONS.md](../DECISIONS.md); exact normative rules remain subject to verification.

## Regulatory status and source candidates

The draft references OIML R76-1:2006 (requirements/tests) and R76-2:2007 (report format). Candidate official source links are [R76-1](https://www.oiml.org/en/files/pdf_r/r076-1-e06.pdf) and [R76-2](https://www.oiml.org/en/files/pdf_r/r076-2-e07.pdf). Their contents/editions were not independently verified during this architectural freeze. All inherited numerical constants, boundary operators, clause interpretations and applicability statements below carry TODO_REGULATORY_VALIDATION. Keeping a candidate worksheet is not asserting that it is a verified regulatory rule.

An unverified/missing dependency returns evaluation_status REVIEW_REQUIRED and compliance_outcome UNDETERMINED with unresolved rule IDs. Never convert missing knowledge to FAIL or N/A, invent a tolerance or activate a required unverified rule. Production evaluation and official issue are gated as specified in DECISIONS F09. Synthetic examples are isolated, labeled fixtures only.

## Frozen workflow and status conventions

Every session has all 17 top-level sections. Sections 1–15 use numerical/functional evaluators, 16 a construction service, 17 a checklist engine. Section 4 has discrimination/sensitivity, Section 6 zero-return/creep, Section 12 seven subtest families. Physical laboratory equipment supplies observations; software records procedure/evidence and evaluates only verified rules.

Workflow approval is distinct from compliance. The worksheet labels PASS/FAIL mean COMPLIANT/NONCOMPLIANT in canonical domain/API output. Procedurally complete failed tests are COMPLETE/NONCOMPLIANT and can appear in approved official failure reports. Incomplete/unverified work cannot issue. Applicable required/elected optional slots, range/scenario identity and retests follow 04/05; no failed run is overwritten.

Every evaluation stores exact raw inputs, typed procedure_context, environment/calibration evidence, calculation trace, acceptance operator/limit, clause/source, versions, hashes and responsible actors in the application record. A nonempty observation list alone never establishes completion. Full required load coverage, timings/stages and functional behavior must be validated.

## Regulatory register mapping

| Worksheet area | Unresolved register entries in DECISIONS F18 |
|---|---|
| Standards and common classification/formulas | REG-01, REG-02, REG-03 |
| Section 1 | REG-04 |
| Section 2 | REG-05 |
| Section 3 | REG-06 |
| Section 4 | REG-07 |
| Section 5 | REG-08 |
| Section 6 | REG-09 |
| Section 7 | REG-10 |
| Section 8 | REG-11 |
| Sections 9–11 | REG-12 |
| Section 12 | REG-13 |
| Sections 13–15 | REG-14 |
| Sections 16–17 | REG-15 |
| Equipment/environment/retests | REG-16 |
| Official report/authority conventions | REG-17 |

# 1. Shared terminology and formulas

## 1.1 Core symbols

| Symbol | Meaning |
|---|---|
| `Max` | Maximum capacity |
| `Min` | Minimum capacity |
| `d` | Actual scale interval |
| `e` | Verification scale interval |
| `n` | Number of verification scale intervals (`Max / e`) |
| `L` | Applied/reference load |
| `I` | Displayed indication |
| `ΔL` | Additional load to the next digital changeover point |
| `P` | Indication before rounding |
| `E` | Error of indication |
| `E0` | Error at/near zero |
| `Ec` | Corrected error |
| `mpe` | Maximum permissible error |
| `T` | Tare value |
| `Unom` | Nominal supply voltage |
| `Umin/Umax` | Declared supply range |
| `EUT` | Equipment under test |

Use one canonical mass unit internally, e.g. **grams**, and convert only for display.

---

## 1.2 Accuracy classes

| Class | Name |
|---|---|
| I | Special accuracy |
| II | High accuracy |
| III | Medium accuracy |
| IIII | Ordinary accuracy |

The prototype should support all four classes even if demo data mainly uses Class III.

---

## 1.3 Verification scale intervals

```text
n = Max / e
```

The backend should validate class, `Max`, `Min`, `d`, `e`, and `n` against the applicable R 76 classification rules before tests begin.

---

## 1.4 Maximum permissible error (initial verification)

### Class I

| Load range | MPE |
|---|---:|
| `0 ... 50 000 e` | `±0.5 e` |
| `>50 000 ... 200 000 e` | `±1.0 e` |
| `>200 000 e` | `±1.5 e` |

### Class II

| Load range | MPE |
|---|---:|
| `0 ... 5 000 e` | `±0.5 e` |
| `>5 000 ... 20 000 e` | `±1.0 e` |
| `>20 000 ... 100 000 e` | `±1.5 e` |

### Class III

| Load range | MPE |
|---|---:|
| `0 ... 500 e` | `±0.5 e` |
| `>500 ... 2 000 e` | `±1.0 e` |
| `>2 000 ... 10 000 e` | `±1.5 e` |

### Class IIII

| Load range | MPE |
|---|---:|
| `0 ... 50 e` | `±0.5 e` |
| `>50 ... 200 e` | `±1.0 e` |
| `>200 ... 1 000 e` | `±1.5 e` |

Backend primitive:

The shared calculate_mpe primitive receives accuracy class, exact load/e, evaluation context and the pinned verified ruleset. No evaluator owns a copied threshold table.

Do not copy these thresholds into individual test services.

---

## 1.5 Digital changeover-point calculation

For a digital indication:

```text
P = I + 0.5e - ΔL

E = P - L

Ec = E - E0
```

General MPE-based decision:

```text
PASS  if |Ec| <= |mpe|
FAIL  if |Ec| >  |mpe|
```

This shared calculation is reused by weighing, eccentricity, tare, warm-up, voltage, damp heat, endurance, etc.

---

# TEST 1 — WEIGHING PERFORMANCE

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 A.4.4, A.5.3.1; R 76-2 Section 1.

## Purpose

Verify that the instrument's error remains within the applicable MPE across the weighing range.

This is the most important numerical test in the system and the basis for several later tests.

## Applicability

Generally applicable to all instruments.

Multiple-range instruments should be handled range-by-range unless a valid combined procedure applies.

## Preconditions

- instrument registered;
- `Max`, `Min`, `e`, `d`, class known;
- instrument at reference position;
- warm-up complete where applicable;
- preloading performed where R 76 requires it;
- test standards identified;
- zero condition known.

## Test loads

For **initial intrinsic error**:

```text
at least 10 different test loads
```

For other weighing-performance runs:

```text
at least 5 test loads
```

Include:

- `Max`;
- `Min` where applicable;
- loads at or near MPE transition points.

Example for Class III:

```text
near 500 e
near 2 000 e
Max
```

Perform:

```text
loading:   0 → Max
unloading: Max → 0
```

## Inputs per point

```text
load L
indication I
additional load ΔL
direction (UP/DOWN)
zero error E0
temperature
relative humidity
barometric pressure if applicable
```

## Calculation

```text
P  = I + 0.5e - ΔL
E  = P - L
Ec = E - E0
mpe = calculate_mpe(class, L, e)
```

## Acceptance criterion

Each required point:

```text
|Ec| <= |mpe|
```

If one required observation fails, the test is failed unless the applicable procedure explicitly allows further investigation/retest.

## Prototype UI

```text
WEIGHING PERFORMANCE

Load        Indication      ΔL      E      Ec      MPE      Result
0 kg
5 kg
10 kg
20 kg
30 kg
...
```

Include an error-vs-load chart.

## Backend evaluator

The evaluator is dispatched through R76Engine.evaluate(test_code, instrument_snapshot, procedure_context, observations, ruleset).

Output must include every point calculation and the overall result.

---

# TEST 2 — TEMPERATURE EFFECT ON NO-LOAD INDICATION

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.9.2.3, A.5.3.2; R 76-2 Section 2.

## Purpose

Determine whether the zero indication drifts excessively with temperature.

## Applicability

Applicable subject to the instrument/category requirements in R 76.

## Temperature range

If no special range is declared, R 76 gives the normal range:

```text
-10 °C to +40 °C
```

Minimum declared spans:

```text
Class I     5 °C
Class II   15 °C
Class III  30 °C
Class IIII 30 °C
```

## Procedure

Set instrument to zero, then expose it to the specified temperature sequence, including high and low declared temperatures and 5 °C when applicable.

After stabilization, determine zero indication error.

Automatic zero-setting / zero-tracking must not mask this result when the prescribed procedure requires it to be inactive.

## Inputs

For each stabilized temperature:

```text
temperature T
zero indication I0
additional load ΔL0
pre-rounding value P0
timestamp
environment
```

## Calculation

```text
P0 = I0 + 0.5e - ΔL0
```

Between consecutive temperature points:

```text
zero_change = |P2 - P1|
temperature_change = |T2 - T1|
```

Normalize:

```text
Class I:
change per 1 °C

Classes II, III, IIII:
change per 5 °C
```

## Acceptance criterion

R 76-2 checks:

```text
Class I:
zero change per 1 °C < e

Class II / III / IIII:
zero change per 5 °C < e
```

## Prototype UI

Show:

```text
T1    P1
T2    P2
ΔT
ΔP
normalized zero drift
allowed drift
PASS / FAIL
```

---

# TEST 3 — ECCENTRICITY

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.6.2, A.4.7; R 76-2 Sections 3.1 and 3.2.

## Purpose

Check whether the same load produces acceptable results when placed at different positions on the load receptor.

## Applicability

Applicable when eccentric loading can occur.

If operating conditions make eccentric loading impossible, record `NOT_APPLICABLE` with justification.

## Variants

```text
3.1 Eccentricity using weights
3.2 Eccentricity using a rolling load
```

## Load-position rules

### Up to four support points

Divide receptor into approximately four quarter segments and load the eccentric segments.

### More than four support points

Apply load over each support area.

### Tank/hopper/special receptor

Apply at each support point using the applicable special-receptor procedure.

### Rolling load

For vehicle/rolling-load applications, test positions include:

```text
beginning
middle
end
```

and reverse direction where operation permits.

## Required stored geometry

```text
load_receptor_type
support_count
receptor_sections
test_position_code
position_coordinates/sketch
display_location
```

The frontend should allow a simple receptor diagram with clickable positions.

## Inputs

```text
L
position
I
ΔL
E0
direction if rolling
```

## Calculation

```text
E  = I + 0.5e - ΔL - L
Ec = E - E0
mpe = calculate_mpe(...)
```

## Acceptance criterion

Every required position:

```text
|Ec| <= |mpe|
```

## Prototype differentiation

Store position coordinates so the report can regenerate the same eccentricity layout diagram.

---

# TEST 4 — DISCRIMINATION AND SENSITIVITY

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.8, 6.1, A.4.8, A.4.9; R 76-2 Sections 4.1 and 4.2.

This top-level section contains two related tests.

---

## TEST 4.1 — Discrimination

### Purpose

Verify that a sufficiently small load change produces a detectable indication change.

### Typical test loads

Perform at three loads such as:

```text
Min
0.5 Max
Max
```

### Digital indication

The R 76 procedure applies during type examination for the relevant digital instruments.

After establishing the specified starting point, an additional load of:

```text
1.4 d
```

is used.

Expected digital response:

```text
indication increases by one actual scale interval d
```

A backend-friendly condition is:

```text
I_after - I_before >= d
```

when the official prescribed preparation has been followed.

### Non-self-indicating / analog

Record:

```text
base load
extra load
initial equilibrium position
final equilibrium position
permanent displacement
```

The acceptance rule depends on the instrument indication type and R 76 3.8.

### Backend design

Use an explicit mode:

```text
DIGITAL
ANALOG_SELF_INDICATING
NON_SELF_INDICATING
```

Never apply the digital `1.4 d` rule to all instrument types.

---

## TEST 4.2 — Sensitivity

### Applicability

For **non-self-indicating instruments**.

### Purpose

Check that the indicating mechanism moves sufficiently when a small prescribed load change is applied.

### Procedure

Use at least two loads, e.g.:

```text
zero
Max
```

and apply the prescribed extra load while the mechanism is in its normal oscillating/damped behavior.

### Stored values

```text
base_load
mpe_at_base_load
extra_load
initial_reading_position
final_reading_position
permanent_displacement
```

### Decision

The evaluator must use the R 76 sensitivity requirement applicable to the instrument construction.

For the prototype, do not invent a universal displacement conversion. Store the procedure parameters and apply the corresponding configured ruleset.

---

# TEST 5 — REPEATABILITY

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.6.1, A.4.10; R 76-2 Section 5.

## Purpose

Verify that repeated measurements of the same load are sufficiently consistent.

## Type-evaluation procedure

Two series:

```text
approximately 50 % Max
close to 100 % Max
```

If:

```text
Max < 1 000 kg
```

use:

```text
10 weighings in each series
```

Otherwise:

```text
at least 3 weighings per series
```

## Inputs per repetition

```text
series
repetition_no
L
I
ΔL
E or Ec
zero_reset_performed
```

## Calculation

For each series:

```text
Emax = max(errors)
Emin = min(errors)

repeatability_range = Emax - Emin
```

## Acceptance criteria

1. Each weighing must satisfy the applicable MPE.
2. The difference between extreme results must satisfy the R 76 repeatability limit.

Backend:

The repeatability range is max(errors) − min(errors), using exact Decimal values and the verified selected error definition.

Return:

```text
individual_result_ok
repeatability_range
allowed_repeatability
overall_result
```

## UI

Display individual readings plus:

```text
Minimum error
Maximum error
Range
Allowed range
```

---

# TEST 6 — TIME DEPENDENCE

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.9.4, A.4.11; R 76-2 Sections 6.1 and 6.2.

This consists of **zero return** and **creep**.

---

## TEST 6.1 — Zero return

### Purpose

Determine how well the instrument returns to zero after a high load remains on it.

### Applicability

R 76 A.4.11 addresses Classes II, III and IIII.

### Procedure

```text
determine zero before loading
apply load close to Max
hold for about 30 minutes
remove load
wait for stable indication
determine zero
```

For multiple-range instruments, continue observing zero for the additional prescribed period.

## Inputs

```text
P_before
load
loading_start_time
loading_end_time
P_after
P_after_plus_5min if applicable
e / e1
```

## Calculation

```text
zero_return_change = |P_after - P_before|
```

## Acceptance

Evaluate against the corresponding R 76 zero-return requirement configured for the instrument/range.

The report should store both the numerical deviation and the rule reference.

---

## TEST 6.2 — Creep

### Purpose

Measure indication drift while a constant high load remains applied.

### Procedure

Load near `Max`.

Take stabilized reading at start and continue for up to four hours.

Important checkpoints:

```text
0 min
15 min
30 min
then continue to 4 h if required
```

Temperature should remain controlled according to the procedure.

## Short-test condition

The test may end at 30 minutes if both conditions are met:

```text
|P30 - P0| <= 0.5 e
```

and:

```text
|P30 - P15| <= 0.2 e
```

## Extended condition

If short condition is not met, continue for four hours.

Acceptance:

```text
maximum deviation during 4 h <= |mpe|
```

## Overall decision

```text
PASS if short_condition
OR
PASS if extended_condition
ELSE FAIL
```

## UI

Use a time-series chart:

```text
time → indication drift
```

---

# TEST 7 — STABILITY OF EQUILIBRIUM

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 4.4.2, A.4.12; R 76-2 Section 7.

## Purpose

Ensure operations that require a stable weight cannot occur while equilibrium is unstable.

This is both:

- a behavioral function test;
- a documentation/configuration examination.

## Part A — Printing / data storage

### Procedure

Use a load around:

```text
50 % Max
```

Disturb equilibrium and immediately command print/store.

Perform repeated observations.

## Inputs

```text
trial_no
load
disturbance_applied
command_time
first_printed_or_stored_value
readings_for_next_5_seconds
```

## Acceptance criterion

R 76-2 checks that:

```text
first printed/stored value differs by no more than 1 e
from readings during the following 5 seconds
```

with only two adjacent indicated values in the relevant condition.

Also verify that printing/storage is inhibited when stable equilibrium is not reached as required.

---

## Part B — Zero / tare operations

Disturb equilibrium and immediately activate zero or tare.

Perform the prescribed sequence five times.

Store:

```text
trial_no
operation ZERO/TARE
error_after_operation
```

R 76-2 evaluates:

```text
E0 <= 0.25 e
```

for the prescribed stability test condition.

## Backend representation

```text
PRINT_STORAGE_RESULT
ZERO_RESULT
TARE_RESULT
```

All applicable subparts must pass.

---

# TEST 8 — TILTING

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.9.1.1, A.5.1; R 76-2 Section 8.

## Purpose

Verify that inclination does not create unacceptable measurement error and that tilt protection works where provided.

## Applicability

Mainly Classes II, III and IIII and instruments liable to tilt.

## Instrument modes

```text
LEVEL_INDICATOR
AUTOMATIC_TILT_SENSOR
NO_LEVEL_DEVICE
MOBILE_AUTOMATIC_TILT_SENSOR
MOBILE_CARDANIC
```

## Directions

Test:

```text
forward
backward
left
right
```

## Procedure

Determine reference-position values at:

```text
no load
load near first applicable MPE transition
load near Max
```

Tilt to limiting value and repeat without inappropriate re-zeroing.

For an instrument without a level indicator/tilt sensor, the OIML procedure specifies:

```text
50 / 1000
```

unless another applicable case in R 76 applies.

## Inputs

```text
tilt_mode
direction
tilt_value
L
I
ΔL
zero_deviation
Ec
```

## Acceptance criteria

R 76-2 records:

### Unloaded

```text
difference <= 2 e
```

except the stated Class II case not used for direct sales to the public.

### Loaded

```text
difference <= |mpe|
```

## Mobile protection behavior

Where a tilt sensor exists, also test:

```text
warning/error generated
display behavior
printing inhibited
data transmission inhibited where required
```

Store both numerical and functional results.

---

# TEST 9 — TARE (WEIGHING TEST)

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.5.3.3, 4.6, A.4.6.1; R 76-2 Section 9.

## Purpose

Verify weighing accuracy while tare is active.

## Tare modes

Record whether instrument uses:

```text
subtractive tare
additive tare
tare balancing
tare weighing
preset tare
```

## Procedure

Perform loading/unloading weighing tests with different tare values.

Use at least:

```text
5 load steps
```

selected to cover:

- low load;
- MPE transition areas;
- maximum achievable net load.

## Inputs

```text
tare_type
tare_value
net_load L
gross_load
I
ΔL
E0
```

## Calculation

```text
E  = I + 0.5e - ΔL - L
Ec = E - E0
mpe = applicable MPE for the tested net value
```

## Acceptance

```text
|Ec| <= |mpe|
```

for every required point.

## UI

Allow several tare scenarios inside one Section 9 test run.

---

# TEST 10 — WARM-UP TIME

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 5.3.5, A.5.2; R 76-2 Section 10.

## Purpose

Verify acceptable performance after electrical power-up.

## Preconditions

Disconnect instrument from supply for:

```text
at least 8 hours
```

unless an applicable instrument-specific instruction in R 76 must be followed.

## Procedure

After switching on:

1. wait for first stable indication;
2. set to zero;
3. determine zero error;
4. apply load close to `Max`;
5. repeat observations at approximately:

```text
0 min
5 min
15 min
30 min
```

## Inputs per time point

```text
elapsed_time
zero I0 / ΔL0 / E0
load L
loaded I / ΔL / EL
temperature
```

## Calculation

```text
corrected_loaded_error = EL - E0
```

## Acceptance

At every required time:

```text
|EL - E0| <= |mpe|
```

## UI

Show a timeline and automatic pass/fail per checkpoint.

---

# TEST 11 — VOLTAGE VARIATIONS

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.9.3, A.5.4; R 76-2 Section 11.

## Purpose

Verify correct operation under permitted supply-voltage variation.

## Test loads

R 76 specifies:

```text
10 e
```

and another load between:

```text
0.5 Max and Max
```

## Power categories

### A. AC mains

Limits:

```text
lower = 0.85 × Unom or 0.85 × Umin
upper = 1.10 × Unom or 1.10 × Umax
```

### B. External / plug-in AC or DC supply

Lower:

```text
minimum operating voltage
```

Upper:

```text
1.20 × Unom or 1.20 × Umax
```

### C. Battery where charging during operation is not possible

Lower:

```text
minimum operating voltage
```

Upper:

```text
Unom or Umax
```

### D. 12 V / 24 V road-vehicle battery

Lower:

```text
minimum operating voltage
```

Upper:

```text
12 V system → 16 V
24 V system → 32 V
```

## Inputs

```text
power_supply_type
reference_voltage
applied_voltage
L
I
ΔL
E0
Ec
instrument_operational_state
```

## Acceptance

At each required voltage:

```text
all functions operate as designed
OR permitted switch-off behavior occurs
```

and when indication is available:

```text
|Ec| <= |mpe|
```

---

# TEST 12 — ELECTRICAL DISTURBANCES

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 5.1–5.4, Annex B.3; R 76-2 Section 12.

## Purpose

Verify that an electronic instrument either:

1. remains within the allowed disturbance effect; or
2. detects/reacts correctly to a significant fault.

This top-level test contains several separate subtests.

## Shared setup

- warm up EUT;
- stabilize environmental conditions;
- use a small test load;
- record no-load deviation;
- connect relevant peripheral/interface equipment;
- capture state before, during and after disturbance.

## Shared decision pattern

For most B.3 disturbance tests:

```text
|indication_during_disturbance - indication_without_disturbance| <= e
```

**OR**

```text
instrument detects and reacts to a significant fault
```

The website should therefore store both:

```text
numerical deviation
fault_detection_response
```

---

## TEST 12.1 — AC mains voltage dips and short interruptions

**Reference:** B.3.1.

The voltage reductions are repeated as prescribed, using one small test load.

Severity cases from R 76-1:

| Case | Amplitude reduced to | Duration / cycles |
|---|---:|---:|
| dip a | 0 % | 0.5 |
| dip b | 0 % | 1 |
| dip c | 40 % | 10 |
| dip d | 70 % | 25 |
| dip e | 80 % | 250 |
| short interruption | 0 % | 250 |

Store:

```text
case
reduction_percent
cycles
reference_indication
disturbed_indication
fault_detected
fault_response
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.2 — Electrical bursts

**Reference:** B.3.2.

Apply separately to:

```text
power supply lines
I/O / communication lines
```

Use both polarities.

R 76-1 specifies Level 2:

```text
power supply lines: 1 kV peak
I/O, signal, data, control lines: 0.5 kV peak
```

Store:

```text
line_type
polarity
amplitude
duration
reference_value
disturbed_value
fault_response
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.3 — Surges

**Reference:** B.3.3.

### Applicability

Only where surge influence is realistically expected, especially relevant to outdoor installations or long/external lines.

### Severity

R 76-1 Level 2:

```text
line-to-line: 0.5 kV
line-to-earth: 1 kV
```

Apply positive and negative surges according to the prescribed procedure.

Store:

```text
line_type
coupling_mode
polarity
surge_voltage
phase_angle_if_ac
reference_indication
disturbed_indication
fault_response
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.4 — Electrostatic discharge (ESD)

**Reference:** B.3.4.

Use direct and indirect discharge as applicable.

R 76-1 Level 3:

```text
contact discharge: up to 6 kV
air discharge: up to 8 kV
```

At least the prescribed number of discharges and interval must be respected by the lab.

Store:

```text
application_type DIRECT/INDIRECT
discharge_mode CONTACT/AIR
location
voltage_kV
polarity
discharge_no
reference_indication
disturbed_indication
fault_response
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.5 — Immunity to radiated electromagnetic fields

**Reference:** B.3.5.

R 76-1 test severity:

```text
frequency: 80 MHz to 2 000 MHz
field strength: 10 V/m
modulation: 80 % AM, 1 kHz sine
```

For the special no-port situation described by R 76, the lower frequency may be extended as required.

Store:

```text
frequency
field_strength
modulation
reference_indication
disturbed_indication
significant_fault
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.6 — Immunity to conducted radio-frequency fields

**Reference:** B.3.6.

Severity:

```text
frequency: 0.15 MHz to 80 MHz
RF amplitude (50 Ω): 10 V emf
modulation: 80 % AM, 1 kHz sine
```

Store:

```text
frequency
amplitude
injection_port
modulation
reference_indication
disturbed_indication
fault_response
```

Acceptance uses the shared disturbance rule.

---

## TEST 12.7 — Road-vehicle power-supply transients

Only for applicable vehicle-powered instruments.

### 12.7A Supply-line transient conduction

**Reference:** B.3.7.1.

R 76 references ISO 7637-2 and includes pulses:

```text
2a
2b
3a
3b
4
```

The software should store:

```text
battery_voltage
test_pulse
conducted_voltage
reference_indication
disturbed_indication
fault_response
```

Do not calculate the laboratory pulse waveform in the web app; record the configured severity and observed behavior.

### 12.7B Capacitive/inductive coupling via non-supply lines

**Reference:** B.3.7.2.

R 76 references ISO 7637-3, pulses `a` and `b`.

Store:

```text
battery_voltage
pulse
line
conducted_voltage
reference_indication
disturbed_indication
fault_response
```

Acceptance again follows the significant-fault/deviation rule.

---

## Storage contract for Section 12

Use generic test_runs and schema-validated test_observations JSONB. A typed procedure_context stores subtest variant, severity, ports, timing and fault-response requirements. Separate requirement slots support seven families and vehicle subvariants. All use versioned test_run_results and result freshness events. The earlier dedicated electrical-disturbance table proposal is retired. See 04 and 05 for the canonical contract.

---

# TEST 13 — DAMP HEAT, STEADY STATE

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 B.2; R 76-2 Section 13.

## Purpose

Verify measurement performance after exposure to high humidity and temperature.

## Applicability

R 76-1 states this test is not applicable to:

```text
Class I
Class II where e < 1 g
```

## Test sequence

At least five test loads (or simulated loads) are used.

### Stage A — Initial/reference

At reference temperature:

```text
normally 20 °C
```

or mean of declared range if 20 °C lies outside it.

Relative humidity:

```text
50 %
```

after conditioning.

### Stage B — Damp heat

At the declared high temperature and:

```text
85 % RH
```

after the prescribed stabilization/exposure period (R 76 describes two days after temperature/humidity stabilization).

### Stage C — Final/reference

Return to reference temperature and:

```text
50 % RH
```

## Inputs

For every load and stage:

```text
stage INITIAL/HIGH_HUMIDITY/FINAL
temperature
RH
L
I
ΔL
E0
Ec
mpe
```

## Calculation

Use normal corrected error calculation:

```text
E  = I + 0.5e - ΔL - L
Ec = E - E0
```

## Acceptance

R 76 states:

```text
all functions operate as designed
```

and:

```text
all indications remain within applicable MPE
```

## UI

Provide three tabs:

```text
Initial
85 % RH
Final
```

and automatically compare the same test loads across stages.

---

# TEST 14 — SPAN STABILITY

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 5.4.4, B.4; R 76-2 Section 14.

## Purpose

Detect long-term changes in span/error during the type-evaluation period.

## Applicability

R 76-1 states:

```text
not applicable to Class I
```

## Test duration

```text
28 days
```

or the shorter period needed for the applicable performance tests, as specified by R 76.

## Required measurements

At least:

```text
8 measurements
```

with reasonably even spacing:

```text
between 0.5 day and 10 days
```

## Test load

```text
near Max
```

Use the same weights throughout.

## Power interruptions

R 76 requires two disconnections from power for at least:

```text
8 hours
```

during the test period, subject to the detailed procedure.

## Initial measurement

At the first measurement, repeat zeroing/loading to obtain the initial average as prescribed.

## Stored values

```text
measurement_no
date_time
temperature
relative_humidity
barometric_pressure
location
event_since_previous_measurement
power_disconnection_event
temperature_test_event
damp_heat_event
L
E0
EL
Ec
corrected_value
```

## Calculation

Calculate variation among corrected span errors.

Define:

```text
variation = maximum corrected error - minimum corrected error
```

after required influence corrections.

## Acceptance

Maximum allowable variation is the greater of:

```text
0.5 e
```

or:

```text
0.5 × |initial-verification MPE at test load|
```

If results show a trend exceeding the specified trend condition, continue as required until the trend stops/reverses or failure is established.

## UI

A time-series chart is essential:

```text
date → corrected span error
```

Mark events:

```text
T = temperature test
D = damp heat test
P = power disconnection
```

---

# TEST 15 — ENDURANCE

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML references:** R 76-1 3.9.4.3, A.6; R 76-2 Section 15.

## Purpose

Check durability after repeated mechanical loading.

## Applicability

R 76-1:

```text
Classes II, III and IIII
Max <= 100 kg
```

The endurance test is performed after the other tests.

## Procedure

Repeatedly load/unload approximately:

```text
50 % Max
```

Number of cycles:

```text
100 000
```

The physical cycling is performed by laboratory equipment. The website records the test.

## Phases

### Initial performance test

Record corrected errors before endurance cycling.

### Cycling

Store:

```text
target_load
number_of_cycles
actual_completed_cycles
cycle_start
cycle_end
equipment_used
abnormal_events
```

### Final performance test

Repeat the relevant weighing measurements.

## Calculation

For corresponding points:

```text
durability_error =
|Ec_initial - Ec_final|
```

## Acceptance

R 76-2 checks:

```text
durability_error <= applicable mpe
```

## UI

Show:

```text
Initial result
100 000-cycle completion
Final result
Difference
Allowed difference
```

---

# TEST 16 — EXAMINATION OF THE CONSTRUCTION OF THE INSTRUMENT

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML reference:** R 76-2 Section 16.

## Important distinction

This is **not a load/measurement test**.

It is a structured technical examination of the submitted instrument type.

The prototype must therefore implement it as an **examination record**, not fabricate a formula-based PASS/FAIL test.

## Purpose

Capture construction information useful for type approval and later verification.

## Information to capture

### Whole instrument

```text
photos
overall dimensions
model/type designation
manufacturer
serial/type plate
intended use
installation type
```

### Main components

```text
load receptor
load transmitting system
load cells
indicator
terminal/display
power supply
printer
communication modules
peripheral devices
level/tilt devices
zero/tare controls
sealing points
```

### Module identification

For each component:

```text
manufacturer
model
serial/type
OIML certificate if applicable
technical specification
photo
```

### Security / access points

Capture:

```text
physical seals
software access
calibration access
protected switches
parameter access
service mode
```

### Additional description

Allow rich text and attachments for facts useful to authorities during initial/subsequent verification.

## Result logic

Use evaluation_status NOT_STARTED/IN_PROGRESS/INCOMPLETE/REVIEW_REQUIRED/COMPLETE and compliance_outcome UNDETERMINED/COMPLIANT/NONCOMPLIANT/NOT_APPLICABLE. Complete data entry alone does not prove conformance: required verified checks need explicit examiner determinations. The item-level examination_state and conformance_result contracts are defined in 05-database-schema.md.

## UI

Create an instrument-construction dossier:

```text
Overview
Components
Photos
Sealing/security
Interfaces
Software
Documents
Remarks
```

---

# TEST 17 — CHECKLIST

> Regulatory validation: **TODO_REGULATORY_VALIDATION**. All thresholds, applicability, procedures and acceptance wording in this worksheet are inherited candidate interpretations. They are not authorized production rules until source verification resolves the linked REG item.

**OIML reference:** R 76-2 Section 17.

## Important distinction

The official checklist summarizes requirements that:

- are not fully covered by Tests 1–15;
- need visual/functional examination;
- include prohibitions or configuration requirements.

It is not a substitute for R 76-1.

For the prototype, implement this as a **rules-driven checklist engine**.

## Checklist result values

Each row:

```text
PASS
FAIL
NOT_APPLICABLE
NOT_EXAMINED
```

plus:

```text
remarks
evidence
photo/document
examiner
timestamp
```

---

## TEST 17.1 — General checklist for weighing instruments

Implement configurable checklist rows covering at least these domains:

### A. Descriptive markings

Check presence/correctness of applicable markings such as:

```text
manufacturer identification
accuracy class
Max
Min
e
range information
tare information where required
temperature limits where declared
power information where applicable
type/serial information
```

### B. Verification/sealing provisions

Check:

```text
space/support for verification marks
visibility
durability
sealing points
protection of adjustable components
```

### C. Technical documentation

Check availability of:

```text
instrument characteristics
module specifications
drawings
component descriptions
operating information
security information
software information where applicable
```

### D. Indicating device

Check:

```text
readability
unambiguous indication
units
decimal indication
scale interval format
consistency among indication/printing/tare devices
zero display behavior
```

### E. Printing / data output

Check:

```text
printed result identification
units
gross/net/tare labeling
stable-equilibrium restrictions
consistency with displayed result
```

### F. Zero-setting / zero-tracking

Check:

```text
device existence
operating range
accuracy
protection against unintended operation
zero indication
automatic behavior
```

### G. Tare devices

Check:

```text
tare operating range
tare indication
net indication
restrictions
accuracy
interaction with zero setting
preset tare where applicable
```

### H. Range selection / multiple-range behavior

Check:

```text
selected range identification
automatic transition behavior
scale intervals per range
return to lower range conditions
```

### I. Auxiliary / extended indication

Check applicable restrictions on high-resolution/extended display and printing.

### J. Peripheral/interface behavior

Check that connected devices and interfaces cannot corrupt legally relevant results.

---

## TEST 17.2 — Direct-sales, price-computing and labeling instruments

Only show this checklist group if the instrument category requires it.

Cover:

```text
visibility to customer
simultaneous display requirements
unit price
price-to-pay calculation/display
tare restrictions
prohibited automatic functions
printing/labeling information
price and weight consistency
clear identification of transactions
```

Store each requirement as a configurable row tied to its R 76 clause.

---

## TEST 17.3 — Electronic weighing instruments

Applicable where:

```text
electronic = true
```

Checklist areas include:

```text
fault detection/reaction
power-up behavior
display test where applicable
interfaces
peripheral equipment
battery behavior
significant fault handling
functional integrity
```

The exact row wording should be stored as versioned rule data, not hard-coded in frontend components.

---

## TEST 17.4 — Software-controlled digital devices and instruments

Applicable where:

```text
software_controlled = true
```

This should be a substantial module.

### Embedded software

Store/check:

```text
legally relevant functions documented
software identification
means of protection/securing
means of detecting intervention
method for checking actual software identity
```

### Loadable/programmable software

Check:

```text
legally relevant software separated/protected
unauthorized changes prevented or detectable
device-specific parameters protected
audit trail present
software interfaces controlled
```

### Software identification

Store:

```text
approved_reference_software_id
observed_software_id
checksum/signature if used
match_result
```

### Data-storage device (DSD)

Where present, check:

```text
sufficient capacity
correct storage/retrieval
data-loss protection
complete reconstruction of weighing result
gross/net/tare where applicable
unit/decimal information
instrument/data-set identification
integrity checksum/signature
protection against modification
automatic storage where required
ability to display/print stored legal data
```

## Checklist persistence contract

Use versioned checklist_rules and checklist_responses as defined in 05-database-schema.md. Preserve row wording/clause/applicability in report snapshots, evidence through attachment_links, and examiner/time only for examined rows. Instantiate editable applicable rows and retain N/A applicability decisions for consistent catalog totals. Use response_result PASS/FAIL/NOT_APPLICABLE/NOT_EXAMINED; a failed examined row counts as complete but contributes NONCOMPLIANT. Unverified requirements remain REVIEW_REQUIRED/UNDETERMINED.

---


# Canonical implementation references

Use [04-r76-rule-engine.md](04-r76-rule-engine.md) for typed inputs, validation, exact comparisons, status aggregation and one input hash. Use [05-database-schema.md](05-database-schema.md) for generic runs/requirements/observations/result versions. Use [06-api-spec.md](06-api-spec.md) for lifecycle endpoints, [07-rbac-workflow.md](07-rbac-workflow.md) for approval of both outcomes and [08-report-spec.md](08-report-spec.md) for all-17-section reporting. BUILD_PLAN.md is the only implementation sequence; earlier alternative phase/migration lists are retired.

## Correct weighing arithmetic fixture

I=10020 g, e=10 g, ΔL=5 g, L=10000 g and E0=0 g yield P=10020 g, E=20 g and Ec=20 g. For the candidate 10 g MPE fixture the outcome is NONCOMPLIANT (display FAIL). No 15 g result is valid for these inputs. Regulatory verification of the MPE/mode/procedure is separate from checking this arithmetic.

## Information still required

The worksheets deliberately retain candidate details and omissions rather than inventing missing law. Exact class limits, e-versus-d/analog/range behavior, sensitivity/zero-return/repeatability/eccentricity limits, complete span trend rules, significant-fault response criteria, clause-level construction/checklist catalogs, calibration acceptance and Indian supplements remain TODO_REGULATORY_VALIDATION. Verification must produce versioned rule configuration and authoritative test vectors, not just a prose claim.

The final prototype covers all applicable sections; an early-phase unsupported section is visibly unfinished/REVIEW_REQUIRED and blocks official completeness. Reports may show verified completed failures; they must never claim certification merely because workflow approval succeeded.
