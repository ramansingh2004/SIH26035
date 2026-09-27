# Phase 25 Stage 4A — source transcript and engine-gap analysis

## Source identity

Pinned source editions:

- OIML R 76-1 Edition 2006 (E)
  - https://www.oiml.org/en/files/pdf_r/r076-1-e06.pdf
- OIML R 76-2 Edition 2007 (E)
  - https://www.oiml.org/en/files/pdf_r/r076-2-e07.pdf

This Stage 4A artifact is **source-mapped, not independently verified**.
Controlled source acquisition and approved SHA-256 digests remain pending.

## Section 11 — Voltage variations

R76-1 A.5.4 maps four source branches.

### A.5.4.1 AC mains

Source-mapped candidate facts:

- lower test voltage: 0.85 × Unom, or 0.85 × Umin where a range is specified;
- upper test voltage: 1.10 × Unom, or 1.10 × Umax;
- all functions operate as designed;
- indications remain within MPE;
- for three-phase supply, variations are applied to each phase successively.

### A.5.4.2 External / plug-in AC or DC, including rechargeable supply
where charging during operation is possible

Candidate facts:

- lower limit: minimum operating voltage;
- upper limit: 1.20 × Unom or 1.20 × Umax;
- functions operate as designed or indication switches off;
- any indication that remains available is within MPE.

### A.5.4.3 Battery supply where charging during operation is not possible

Candidate facts:

- lower limit: minimum operating voltage;
- upper limit: Unom or Umax;
- functions operate as designed or indication switches off;
- available indications remain within MPE.

### A.5.4.4 12 V / 24 V road-vehicle battery supply

Candidate facts:

- lower limit: minimum operating voltage;
- upper limit: 16 V for nominal 12 V systems;
- upper limit: 32 V for nominal 24 V systems;
- functions operate as designed or indication switches off;
- available indications remain within MPE.

R76-2 Section 11 provides separate report-form selection for the same source
branches.

### Existing engine gap

`VoltageVariationPolicy` already models explicit voltage/load lists, power
profile, switch-off permission and functional behavior. It does not derive
the source branch voltages from Unom/Umin/Umax/minimum operating voltage, does
not encode successive three-phase application, and still uses v1-only policy,
context and observation registration.

## Section 12 — Electrical disturbances

Common R76-1 Annex B.3 source-mapped requirements include:

- warm-up before testing;
- sufficiently constant environmental conditions;
- interface/peripheral setup where applicable;
- zero/no-load deviation handling;
- one small test load for the disturbance procedures;
- disturbance acceptance based on either:
  - indication difference not exceeding e, or
  - detection of and reaction to a significant fault.

### B.3.1 AC mains voltage dips and short interruptions

Candidate severity facts:

- reductions repeated 10 times;
- interval at least 10 s;
- voltage dips:
  - 0 % for 0.5 cycle;
  - 0 % for 1 cycle;
  - 40 % for 10 cycles;
  - 70 % for 25 cycles;
  - 80 % for 250 cycles;
- short interruption:
  - 0 % for 250 cycles.

### B.3.2 Electrical bursts

Candidate facts:

- power lines and I/O/communication lines treated separately;
- positive and negative polarity;
- at least 1 min for each amplitude/polarity;
- Level 2;
- 1 kV on power-supply lines;
- 0.5 kV on I/O, signal, data and control lines.

### B.3.3 Surge

Candidate facts:

- applies where installation risk makes surge testing relevant;
- power-supply lines;
- AC mains: at least 3 positive and 3 negative surges, synchronous at
  0°, 90°, 180° and 270°;
- other power supplies: at least 3 positive and 3 negative surges;
- Level 2;
- 0.5 kV line-to-line;
- 1 kV line-to-earth.

### B.3.4 Electrostatic discharge

Candidate facts:

- direct and indirect application;
- at least 10 discharges;
- at least 10 s between successive discharges;
- Level 3;
- up to 6 kV contact discharge;
- up to 8 kV air discharge.

### B.3.5 Radiated RF immunity

Candidate facts:

- 80 MHz to 2 000 MHz;
- if B.3.6 cannot be applied because suitable ports are absent, lower
  radiated limit becomes 26 MHz;
- field strength 10 V/m;
- 80 % AM, 1 kHz sine-wave modulation.

### B.3.6 Conducted RF immunity

Candidate facts:

- 0.15 MHz to 80 MHz;
- RF amplitude 10 V emf into the specified system;
- 80 % AM, 1 kHz sine-wave modulation.

### B.3.7 Road-vehicle supply EMC

Candidate source mappings:

- B.3.7.1 uses ISO 7637-2:2004 Level IV pulse families 2a, 2b, 3a, 3b and 4
  with different source values for 12 V and 24 V systems;
- B.3.7.2 uses ISO 7637-3 Level IV pulses a and b on non-supply lines;
- acceptance remains ≤ e indication difference or significant-fault response.

R76-2 Sections 12.1–12.7 provide dedicated report sections for these
disturbance families.

### Existing engine gap

`phase10.py` already has a reusable disturbance profile, typed severity cases,
repetition order, evidence requirements and fault-response representation.
Remaining source-to-engine gaps include exact source-standard identity/version,
port-specific applicability, frequency sweep semantics, phase-angle
requirements, direct/indirect ESD application semantics, and complete road-
vehicle pulse-family representation.

## Section 13 — Damp heat, steady state

R76-1 B.2 candidate facts:

- not applicable to class I;
- not applicable to class II where e < 1 g;
- at least five different test loads or simulated loads;
- initial/reference stage:
  - 20 °C, or mean of declared range where 20 °C is outside it;
  - 50 % relative humidity after conditioning;
- high-humidity stage:
  - high temperature of the declared range;
  - 85 % RH;
  - two days following temperature/humidity stabilization;
- final stage:
  - reference temperature;
  - 50 % RH;
- all functions operate as designed;
- all indications remain within MPE.

R76-2 Section 13 reports initial, high-temperature/high-humidity and final
measurements.

### Existing engine gap

The v1 damp-heat engine is already strong: stage-specific temperature/humidity
bounds, stabilization/exposure duration, load coverage, function state,
environment/equipment/evidence and MPE evaluation exist. Missing source-native
semantics are mainly applicability derivation, reference-temperature
derivation, high-temperature derivation, exact minimum-five-load selection,
and source-native two-day-after-stabilization representation.

## Section 14 — Span stability

R76-1 B.4 candidate facts:

- not applicable to class I;
- automatic span adjustment is activated before each measurement when fitted;
- performance-test period includes temperature test and, where applicable,
  damp heat, but excludes endurance;
- two power disconnections of at least 8 h during the period;
- stabilization after switch-on:
  - at least 5 h normally;
  - at least 16 h after temperature/damp-heat tests;
- duration: 28 days or time needed for performance tests, whichever is shorter;
- spacing between measurements: 0.5 day to 10 days, fairly evenly distributed;
- load near Max;
- same test weights throughout;
- at least 8 measurements;
- automatic zero tracking off;
- automatic built-in span adjustment on;
- first measurement repeats zeroing/loading four additional times to determine
  an average;
- subsequent measurements normally one reading unless source-defined
  extension conditions apply;
- allowable variation is the greater of:
  - 0.5 e;
  - 0.5 × absolute initial-verification MPE at the applied load;
- trend beyond half the allowable variation extends the test until the trend
  rests/reverses or the error exceeds the maximum allowable variation.

### Existing engine gap

`SpanStabilityPolicy` already represents duration, interval bounds, near-Max as
an explicit load, reference weights, power disconnections, correction mode,
max-of-e-and-MPE limit construction and trend-extension mechanics. The current
v1 contract cannot source-derive near-Max, distinguish 5 h vs 16 h recovery
branches, encode first-measurement five-reading averaging explicitly, or
express the source trend trigger without a precomputed absolute trend limit.

## Section 15 — Endurance

R76-1 A.6 candidate facts:

- applies only to classes II, III and IIII with Max ≤ 100 kg;
- performed after all other Annex A/B tests;
- repetitive loading/unloading approximately 50 % of Max;
- 100 000 load applications;
- loading frequency/speed permits equilibrium loaded and unloaded;
- loading force does not exceed normal loading force;
- weighing test before cycling establishes intrinsic error;
- weighing test after cycling determines durability error.

R76-2 Section 15 separately records the initial and final performance tests.

### Existing engine gap

`EndurancePolicy` already models cycle count, cycling-load fraction/tolerance,
cycle timing, initial/final points, same weights, evidence and absolute
corrected-error change. Remaining source-native gaps are applicability
derivation, explicit after-all-tests ordering, equilibrium-at-each-cycle
evidence, normal-loading-force evidence and verified durability-limit
semantics.

## Stage 4A conclusion

Sections 11–15 already have substantial deterministic v1 mechanics. Stage 4
should therefore avoid rewriting working mechanics. Stage 4B will add only the
parameterized/native-v2 data needed to preserve source semantics, a controlled
candidate bundle, explicit non-authoritative vector coverage and a safe
fail-closed compatibility boundary.
