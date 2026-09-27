# Phase 25 Stage 3A — Source transcript for Sections 6–10

Checked against the pinned official publications:

- OIML R 76-1 Edition 2006 (E)
  - `https://www.oiml.org/en/files/pdf_r/r076-1-e06.pdf`
- OIML R 76-2 Edition 2007 (E)
  - `https://www.oiml.org/en/files/pdf_r/r076-2-e07.pdf`

This document is a developer source transcript and engine-analysis aid. It is
**not independent regulatory verification** and does not authorize activation.

## Section 6 — Time dependence — REG-09

### Applicability

R 76-1 clause 3.9.4 and Annex A.4.11 apply the time-dependence requirements to
classes II, III and IIII.

### 6.1 Zero return

Primary source mapping:

- R 76-1: 3.9.4.2 and A.4.11.2
- R 76-2 report section 6.1

Source-mapped candidate facts:

- use a load close to Max;
- keep the load on the instrument for 30 minutes;
- determine zero before loading and again after unloading as soon as the
  indication has stabilized;
- automatic zero-setting / zero-tracking is not to be in operation during the
  Annex A.4.11.2 test;
- ordinary zero-return deviation limit: 0.5 e;
- multi-interval zero-return deviation uses 0.5 e1;
- on a multiple-range instrument, returning from Maxi uses 0.5 ei;
- after return from a load greater than Max1 and switching immediately to the
  lowest range, the near-zero indication must also satisfy the separate
  five-minute e1 condition.

R 76-2 section 6.1 records the 0-minute and 30-minute zero values and, for
multiple-range instruments, a further 35-minute reading.

### 6.2 Creep

Primary source mapping:

- R 76-1: 3.9.4.1 and A.4.11.1
- R 76-2 report section 6.2

Source-mapped candidate facts:

- test load is close to Max;
- baseline is taken as soon as indication has stabilized;
- extended test duration is four hours;
- temperature should not vary by more than 2 °C during the Annex A test;
- the short-route condition after 30 minutes is:
  - change from the initial reading no greater than 0.5 e; and
  - change from 15 minutes to 30 minutes no greater than 0.2 e;
- if the short-route condition is not satisfied, continue to four hours and
  compare change from the initial indication against the absolute MPE at the
  applied load;
- R 76-2 explicitly provides readings at 0, 5, 15, 30 minutes, then 1, 2, 3
  and 4 hours.

### Current engine gap

The current v1 `ZeroReturnPolicy` has one fixed test load, one fixed hold time
and one fixed limit. It cannot faithfully encode the multi-interval and
multiple-range branches.

The current v1 `CreepPolicy` has a single limit across its selected checkpoint
set. It cannot encode the alternative 30-minute route and four-hour MPE route
as two distinct acceptance branches, and it does not capture the Annex
temperature-variation condition.

## Section 7 — Stability of equilibrium — REG-10

Primary source mapping:

- R 76-1: 4.4.2 and A.4.12
- R 76-2 report section 7

Source-mapped candidate facts:

- manufacturer documentation is checked for stable-equilibrium principle,
  criteria, adjustable/non-adjustable parameters, securing, and the most
  critical/worst-case adjustment;
- printing, storage, zero and tare operations must be inhibited while
  equilibrium is not stable;
- under continuous disturbance, no operation requiring stable equilibrium is
  permitted;
- testing uses about 50 % of Max or a load in the operating range of the
  relevant function;
- for printing/storage, the indication is observed for five seconds after the
  output event;
- stable equilibrium permits no more than two adjacent indicated values and
  one of them is the printed/stored value;
- R 76-1 clause 4.4.2 describes the printed/stored result as not deviating by
  more than 1 e from the final weight value;
- zero-setting and tare-balancing accuracy are tested five times;
- R 76-2 section 7 checks the calculated E0 against 0.25 e.

### Current engine gap

The current `StabilityPolicy` models generic stable/unstable functional
behavior, but it does not encode:

- the worst-case manufacturer adjustment/document review;
- about-50-%-Max load selection;
- the five-second observation window;
- the quantitative 1 e print/storage relationship;
- the five repeated zero/tare accuracy determinations and 0.25 e boundary.

## Section 8 — Tilting — REG-11

Primary source mapping:

- R 76-1: 3.9.1.1 and A.5.1 through A.5.1.3
- R 76-2 report section 8

Source-mapped candidate facts:

- Annex A.5.1 applies to classes II, III and IIII;
- the instrument is tested longitudinally forwards/backwards and transversely
  side-to-side;
- no-load and loaded behavior are checked between reference and tilted
  positions;
- the unloaded difference is limited to 2 e, subject to the class-II
  qualification in the report form;
- loaded comparisons use the absolute MPE;
- Annex A.5.1.1.2 selects a load close to the lowest load where MPE changes
  and another close to Max;
- a level indicator uses its marked limiting tilt;
- an automatic tilt sensor uses the manufacturer-defined limiting tilt and
  must trigger the specified protection behavior when exceeded;
- an instrument without a level indicator or automatic tilt sensor uses
  50/1000;
- mobile instruments used outside have the automatic-sensor/Cardanic
  provisions of 3.9.1.1d/A.5.1.3;
- automatic zero-setting / zero-tracking is not to be in operation during the
  Annex tilt test.

### Current engine gap

The v1 `TiltingPolicy` can represent explicit directions, explicit loads and
explicit tilt values, but does not derive:

- the first MPE-transition load;
- class/applicability exclusions;
- all limiting-tilt branches from instrument facts;
- the exact class-II unloaded exception.

## Section 9 — Tare — REG-12

Primary source mapping:

- R 76-1: 3.5.3.3, 4.6.3, A.4.6.1 and A.4.6.2
- R 76-2 report section 9

Source-mapped candidate facts for the weighing test:

- loading and unloading follows A.4.4.1;
- different tare values are used;
- at least five load steps are selected;
- load steps include values close to Min when the Min condition applies,
  points at/near MPE changes, and a point close to maximum possible net load;
- subtractive tare uses one tare value between one-third and two-thirds of
  maximum tare;
- additive tare uses two tare values approximately one-third and full maximum
  tare effect;
- corrected error is compared against MPE in the R 76-2 section-9 form.

Separate tare-setting accuracy mapping:

- R 76-1 clause 4.6.3 gives the tare-setting accuracy requirement;
- A.4.6.2 establishes accuracy in a manner similar to the zero-setting test;
- the electronic/analog and mechanical-digital branches use different
  interval bases, with e1 used for multi-interval instruments.

### Current engine gap

The v1 `TarePolicy` accepts explicit scenarios and explicit net-load lists, but
does not derive the source-required tare values and load points. The evaluator
also needs the compatible v1/v2 MPE path and a separate representation for
tare-setting accuracy if Section 9 is to cover A.4.6.2 rather than only the
weighing test.

## Section 10 — Warm-up time — REG-12

Primary source mapping:

- R 76-1: 5.3.5 and A.5.2
- R 76-2 report section 10

Source-mapped candidate facts:

- applies to an instrument using electric power;
- disconnect from the supply for at least eight hours before the test;
- connect and switch on;
- as soon as indication stabilizes, set to zero and determine zero error;
- load close to Max;
- repeat observations after 5, 15 and 30 minutes;
- each measurement after 5, 15 and 30 minutes is corrected for the zero error
  at that time;
- R 76-2 also records the initial 0-minute loaded/unloaded measurement;
- each corrected loaded error is checked against MPE;
- class-I operation follows the operating-manual provisions for the period
  after connection to the mains;
- clause 5.3.5 separately prohibits indication or transmission of the weighing
  result during the instrument's warm-up time.

### Current engine gap

The v1 `WarmUpPolicy` can encode a fixed power-off duration, explicit
checkpoints and a fixed test load, but it does not derive close-to-Max, does not
represent class-I manual provisions, and does not test the separate 5.3.5
no-indication/no-transmission behavior before the instrument becomes ready.

## Stage 3A safety conclusion

The existing evaluator mechanics are useful deterministic foundations, but
their synthetic v1 policies are not a substitute for the source branches
above.

Stage 3A therefore makes **no runtime regulatory change**. All extracted facts
remain `SOURCE_MAPPED_NOT_VERIFIED`, controlled PDF SHA-256 acquisition remains
pending, and independent verification remains mandatory.
