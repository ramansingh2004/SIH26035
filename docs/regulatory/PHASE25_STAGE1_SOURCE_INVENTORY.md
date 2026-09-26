# Phase 25 Stage 1 — Official source inventory

Checked: 2026-09-27

This inventory identifies the source set for regulatory verification. It is
**not** itself regulatory verification. Source URLs and publication identities
must still be captured through the controlled acquisition procedure before any
encoded rule can be marked VERIFIED.

## Source classes

### SRC-R76-1-2006-E — Primary normative OIML source

- Publisher: International Organization of Legal Metrology (OIML)
- Publication: **OIML R 76-1 Edition 2006 (E)**
- Title: *Non-automatic weighing instruments — Part 1: Metrological and
  technical requirements — Tests*
- Official URL:
  `https://www.oiml.org/en/files/pdf_r/r076-1-e06.pdf`
- Observed official PDF length: 144 pages.
- Role in SIH26035:
  - instrument classification and metrological requirements;
  - technical requirements;
  - Annex A test procedures;
  - Annex B additional tests for electronic instruments;
  - source clauses for deterministic rule parameters.
- Repository target edition:
  `R76-1:2006`
- Controlled SHA-256: **PENDING_CONTROLLED_ACQUISITION**
- Independent verifier: **PENDING**
- Verification status: **NOT_INDEPENDENTLY_VERIFIED**

R 76-1 states that it specifies requirements for non-automatic weighing
instruments subject to official metrological control and that its testing
procedures should be applied with the R 76-2 Test Report Format.

### SRC-R76-2-2007-E — Primary OIML report/cross-reference source

- Publisher: OIML
- Publication: **OIML R 76-2 Edition 2007 (E)**
- Title: *Non-automatic weighing instruments — Part 2: Test report format*
- Official URL:
  `https://www.oiml.org/en/files/pdf_r/r076-2-e07.pdf`
- Observed official PDF length: 62 pages.
- Role in SIH26035:
  - canonical 17-section type-evaluation report organization;
  - official test-form names;
  - cross-check of Annex A/B test references;
  - report data fields and checklist organization.
- Repository target edition:
  `R76-2:2007`
- Controlled SHA-256: **PENDING_CONTROLLED_ACQUISITION**
- Independent verifier: **PENDING**
- Verification status: **NOT_INDEPENDENTLY_VERIFIED**

R 76-2 says its type-evaluation report presents the results of tests described
in Annexes A and B of R 76-1.

### SRC-OIML-R76-REVISION-PROJECT — Change-watch source only

- Publisher: OIML
- Project: **TC9/SC1/p1 — Revision of R 76:2006 Non-automatic weighing
  instruments**
- Official project URL:
  `https://www.oiml.org/en/structure/members/projectedit_view?idproject=427`
- Status observed 2026-09-27:
  - 1.1 Committee Draft circulated to the Project Group on 2024-04-30;
  - core team processing comments.
- Use in SIH26035: **CHANGE WATCH ONLY**.
- Prohibition: committee-draft text or proposed requirements must not be merged
  into the pinned `R76-1:2006 / R76-2:2007` ruleset.

### SRC-INDIA-APPROVAL-MODELS-2011 — National legal-context source

- Publisher: Department of Consumer Affairs, Government of India.
- Source: *The Legal Metrology (Approval of Models) Rules, 2011*
- Official page:
  `https://consumeraffairs.nic.in/legalmetrology/legal-metrologyapproval-models-rules2011`
- Use in Stage 1: identify the Indian model-approval context.
- Status: **NATIONAL_MAPPING_PENDING_EXPERT_REVIEW**.
- Prohibition: this source is not used as a silent replacement for OIML
  numerical/test parameters.

### SRC-INDIA-LM-GENERAL — National legal-context source

- Publisher: Department of Consumer Affairs, Government of India.
- Source family: Legal Metrology (General) Rules, 2011 and applicable
  amendments.
- Official Department source index:
  `https://consumeraffairs.nic.in/acts-and-rules/legal-metrology/the-legal-metrology-act-2009`
- Use in Stage 1: establish that Indian supplemental requirements and
  amendments must be mapped separately under REG-01/REG-17.
- Status: **NATIONAL_MAPPING_PENDING_EXPERT_REVIEW**.

### SRC-INDIA-GATC — Testing-authority context

- Publisher: Department of Consumer Affairs, Government of India.
- Source: Government Approved Test Centre information/rules.
- Official page:
  `https://consumeraffairs.nic.in/`
- Relevant current Department statement: the GATC scope includes
  non-automatic weighing instruments of Accuracy Class III up to 150 kg and
  Class IIII, among other instruments.
- Use in SIH26035: authority/laboratory context only.
- Status: **AUTHORITY_SCOPE_MAPPING_PENDING**.

## Controlled source-acquisition procedure for Stage 2+

For every normative PDF used to encode a verified rule:

1. download from the official publisher domain;
2. retain the original filename and acquisition date;
3. compute SHA-256 over the exact bytes;
4. record publication identity, edition, language and URL;
5. record exact page/clause evidence for each encoded rule;
6. have a second person independently compare source wording to the encoded
   condition, numeric value, unit, boundary operator and applicability;
7. store verifier identity, verification timestamp and evidence reference;
8. only then replace `TODO_REGULATORY_VALIDATION` for that dependency.

Screenshots, search snippets, AI summaries and developer notes can aid navigation
but are not sufficient verification evidence.

## Edition isolation rule

The authoritative artifact being prepared is explicitly versioned around
`R76-1:2006 / R76-2:2007`. If OIML later publishes a revised R 76, it must
become a **new immutable ruleset edition**. Historical sessions must continue
to resolve against the ruleset snapshot they pinned at creation.
