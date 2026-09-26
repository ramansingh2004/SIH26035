# Phase 25 Stage 2A â€” Source transcript: common rules + Sections 1â€“5

Checked against the official OIML English publications on 2026-09-27.

Pinned regulatory editions for this verification work:

- OIML R 76-1:2006 (E) — metrological and technical requirements and tests.
- OIML R 76-2:2007 (E) — type evaluation report format.

This document is a **paraphrased engineering transcript** for implementation
planning. It is not a substitute for the normative publications and it is not
an independent metrology-expert sign-off.

## Common classification â€” R 76-1 clauses 3.1â€“3.2

The source defines four accuracy classes: I, II, III and IIII.

Clause 3.2 / Table 3 relates each accuracy class to:
- verification scale interval `e`;
- minimum and maximum number of verification scale intervals `n = Max/e`;
- minimum capacity `Min`.

Important implementation consequence:
classification cannot be represented by one fixed Class III demo profile. The
authoritative ruleset needs class-dependent validation of `e`, `n` and `Min`,
including special cases and multi-range handling.

## Initial-verification MPE â€” R 76-1 clause 3.5.1 / Table 6

Table 6 defines three absolute MPE levels: 0.5 e, 1.0 e and 1.5 e, with
class-dependent load-band boundaries.

Source-mapped bands:

| Class | 0.5 e band | 1.0 e band | 1.5 e band |
|---|---|---|---|
| I | 0..50 000 e | >50 000..200 000 e | >200 000 e |
| II | 0..5 000 e | >5 000..20 000 e | >20 000..100 000 e |
| III | 0..500 e | >500..2 000 e | >2 000..10 000 e |
| IIII | 0..50 e | >50..200 e | >200..1 000 e |

Clause 3.5.2 separately states that in-service MPE is twice the
initial-verification MPE. Therefore the software must not silently apply the
initial-verification profile to every evaluation context.

Clause 3.5.3.2 requires digital rounding error to be eliminated when the actual
scale interval is greater than 0.2 e. The existing pre-rounding mechanism is
compatible in principle, but the exact applicability of that calculation must
remain tied to the verified procedure context.

## Section 1 â€” Weighing performance

Primary source:
- R 76-1 A.4.4;
- R 76-1 3.5;
- R 76-2 test-report Section 1.

A.4.4.1 requires loading from zero through Max and unloading back to zero.

For initial intrinsic error:
- at least 10 distinct test loads.

For other weighing tests:
- at least 5 distinct test loads.

The selected set includes:
- Max;
- Min when Min is at least 100 mg;
- points at or near MPE transitions.

Implementation gap:
the current `WeighingPolicy.required_loads` stores absolute gram values. A
generic official policy must derive load points from the instrument snapshot,
`e`, Min/Max and MPE transitions instead of baking in one instrument's values.

## Section 2 â€” Temperature effect on no-load indication

Primary source:
- R 76-1 3.9.2;
- R 76-1 A.5.3.1 and A.5.3.2;
- R 76-2 Section 2.

If an instrument has no special declared working range, the source prescribes
-10 Â°C to +40 Â°C.

Minimum declared spans:
- Class I: 5 Â°C;
- Class II: 15 Â°C;
- Classes III and IIII: 30 Â°C.

For no-load indication:
- Class I is normalized over a 1 Â°C temperature difference;
- other classes over 5 Â°C;
- the permitted change is one verification scale interval.

A.5.3.1 describes static-temperature exposure and the temperature sequence.
A.5.3.2 requires the highest and lowest prescribed temperatures and 5 Â°C where
applicable, after stabilization.

Implementation gap:
`TemperatureZeroPolicy` currently stores one fixed class and one fixed
temperature sequence. A reusable official rule must derive the sequence and
normalization from the instrument class and declared temperature range.

## Section 3 â€” Eccentricity

Primary source:
- R 76-1 3.6.2;
- R 76-1 A.4.7;
- R 76-2 Sections 3.1 and 3.2.

The load amount depends on receptor construction:
- general case: a fraction of Max plus applicable additive tare effect;
- more than four supports: fraction depends on support count;
- tank/hopper/minimal off-centre case: a smaller fraction per support;
- rolling-load instruments: the usual/heaviest concentrated rolling load,
  subject to the stated maximum fraction.

A.4.7 defines where the load is placed and distinguishes:
- up to four support points;
- more than four support points;
- special receptors;
- rolling loads;
- mobile instruments.

Implementation gap:
the current `EccentricityPolicy` contains a fixed `test_load_g`,
`required_positions` and optional fixed support count. These need formula-driven
resolution from the instrument snapshot before an official generic ruleset can
be encoded.

## Section 4 â€” Discrimination and sensitivity

### Discrimination

Primary source:
- R 76-1 3.8;
- R 76-1 A.4.8;
- R 76-2 Section 4.1.

A.4.8 uses three representative loads (examples are Min, half Max and Max).

For digital indication, the type-examination procedure applies only when
`d >= 5 mg`. The procedure uses an additional load of 1.4 d and requires an
unambiguous one-scale-interval indication change.

For analog/self-indicating and non-self-indicating instruments, different
acceptance semantics apply. Therefore the digital rule must not be reused for
all indication modes.

### Sensitivity

Primary source:
- R 76-1 6.1;
- R 76-1 A.4.9;
- R 76-2 Section 4.2.

Sensitivity applies to non-self-indicating instruments. A.4.9 uses at least two
loads and ties the extra load to the MPE at the applied load, subject to the
source minimum.

Implementation gap:
official applicability and load generation are mode- and instrument-dependent;
a universal fixed policy would be wrong.

## Section 5 â€” Repeatability

Primary source:
- R 76-1 3.6.1;
- R 76-1 A.4.10;
- R 76-2 Section 5.

The fundamental acceptance rule is that the spread among repeated results for
the same load must not exceed the absolute MPE for that load.

Type approval:
- two series;
- one around 50 % Max;
- one close to 100 % Max;
- if Max < 1 000 kg, 10 weighings per series;
- otherwise at least 3 per series.

Verification:
- one series around 0.8 Max;
- three weighings for classes III/IIII;
- six for classes I/II.

Implementation gap:
the current `RepeatabilityPolicy` stores fixed absolute `load_g` values and
fixed minimum repetitions. A reusable official rule must resolve series from
Max, class and evaluation context.

## Stage 2A conclusion

The official publications support the rule families above, but the project
must first generalize the policy schemas so that rules are parameterized by the
instrument/evaluation context.

No active regulatory rule should be populated with demo-scale absolute values.

