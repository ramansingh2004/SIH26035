# Phase 25 Stage 2B — Parameterized policy schema foundation

Stage 2A showed that Sections 1–5 cannot safely be represented by
instrument-specific absolute demo values. Stage 2B therefore introduces a
pure, exact, regulatory-neutral parameterization layer.

## Added implementation

`backend/app/compliance/parameterized.py`

The module introduces:

- `PolicySelector`
  - accuracy class;
  - evaluation context;
  - indication type;
  - range type;
  - self/non-self-indicating status.

- `MassExpression`
  - absolute mass;
  - Min;
  - Max;
  - multiples of `e`;
  - multiples of `d`;
  - `(Max + declared tare fact)` ratios;
  - MPE-derived mass.

- `TemperatureExpression`
  - explicit temperature;
  - declared minimum;
  - declared maximum.

- `MpeProfileSetV2`
  - multiple class/evaluation-context profiles in one closed immutable policy.

- v2 policy containers for:
  - Section 1 weighing;
  - Section 2 temperature-zero;
  - Section 3 eccentricity;
  - Section 4 discrimination;
  - Section 4 sensitivity;
  - Section 5 repeatability.

## Safety properties

The Stage 2B resolver:

- uses Decimal-only exact arithmetic;
- rejects binary floats;
- fails if required instrument facts are unknown;
- fails if policy selectors overlap;
- fails if no policy case covers the instrument/context;
- does not silently convert unknown regulatory knowledge to N/A or FAIL;
- contains no OIML numerical constants or default regulatory thresholds.

## Deliberate boundary

Stage 2B does **not yet switch existing v1 evaluators to v2**.

That is intentional. Existing synthetic regression fixtures continue using the
stable v1 schemas while Stage 2C will:

1. wire v2 policy kinds into evaluator dispatch;
2. add controlled verified-source artifacts for common rules + Sections 1–5;
3. cross-check official test vectors;
4. keep activation blocked until independent verification evidence is present.

## Regulatory state

Unchanged:

- candidate-v1 remains DRAFT;
- runtime OIML YAML is untouched;
- no rule becomes VERIFIED;
- no source digest is fabricated;
- no DB migration/API change;
- no official report/activation gate is weakened.
