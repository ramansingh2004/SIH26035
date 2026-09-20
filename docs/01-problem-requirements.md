# SIH26035 — Requirements Analysis

Specification Freeze v1 — 2026-09-20. Product requirements below are preserved; architecture and lifecycle contracts are frozen in [DECISIONS.md](../DECISIONS.md) and [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md).

## 1. Problem Statement

**PS ID:** SIH26035

**Title:**  
Development of a Software Program/Application for Generation of Test
Reports for Non-Automatic Weighing Instruments (NAWI) as per
OIML Recommendation R-76

**Organization:**  
Ministry of Consumer Affairs, Food & Public Distribution

**Department:**  
Department of Consumer Affairs

**Category:**  
Software


---

# 2. Problem Background

Non-Automatic Weighing Instruments (NAWIs) include instruments such as:

- Electronic weighing scales
- Platform scales
- Weighbridges

These instruments are used in areas such as trade, commerce,
healthcare, agriculture and industry.

Because incorrect weighing can affect transactions and consumers,
these instruments are regulated under the Indian Legal Metrology
framework.

The supplied problem analysis describes designated laboratories evaluating NAWI models according to:

OIML Recommendation R 76
— Non-Automatic Weighing Instruments.

The evaluation involves multiple metrological and functional tests.

Currently, test observations and reports are largely handled using:

- Spreadsheets
- Document templates
- Manual calculations
- Manual report preparation

This creates problems such as:

- Time-consuming report preparation
- Possibility of calculation errors
- Lack of uniformity between reports
- Repetitive manual data entry


---

# 3. Core Objective

Develop software that automates the NAWI type-evaluation
test-report workflow.

The system must allow laboratory personnel to:

Record test data
        ↓
Validate entered observations
        ↓
Perform OIML R76 calculations
        ↓
Determine compliance
        ↓
Determine PASS / FAIL
        ↓
Generate standardized test report
        ↓
Store completed reports digitally


---

# 4. Primary Users

The problem statement clearly requires secure access with
role-based permissions.

Therefore, the system must support multiple authorized users.

The exact role names are NOT specified by SIH.

Possible roles will have to be designed by the implementation team.


---

# 5. Instrument Information Requirements

The application must allow entry and storage of:

### Manufacturer Information

- Manufacturer details

### Instrument Information

- Instrument specifications
- Model information
- Technical parameters

The exact set of technical fields must be derived from
OIML R76 and the applicable Legal Metrology requirements.


---

# 6. Laboratory Information Requirements

The system must record:

- Laboratory details
- Laboratory/test conditions
- Environmental conditions relevant to testing

These details should later be automatically populated
into the generated test report where applicable.


---

# 7. OIML R76 Test Data Entry

The system must provide digital data-entry forms for
applicable OIML R76 tests.

The application must support:

- Entry of observations for prescribed tests
- Test-specific input fields
- Storage of observations
- Validation of entered observations

The exact tests, test procedures, formulas and required
observations must be obtained from OIML R76.

The SIH problem statement does NOT provide the formulas itself.


---

# 8. Automatic Validation

The system must automatically validate entered test data.

Validation must occur before incorrect/incomplete values
are allowed to affect calculations or reports.

Required capability:

Input
    ↓
Validation
    ↓
Valid → Continue calculation

Invalid → Show validation problem


The exact validation rules must be derived from OIML R76
and applicable instrument/test requirements.


---

# 9. Automatic Calculations

The software must perform calculations required for
OIML R76 compliance evaluation.

The problem statement specifically requires:

- Automatic calculation of permissible errors
- Automatic calculation of related test values
- Automatic compliance verification

The user should not need to manually calculate these values
using spreadsheets.


---

# 10. Compliance Determination

One of the core requirements is:

Compliance determination according to OIML R76.

Conceptual flow:

Instrument specifications
        +
Test observations
        ↓
OIML R76 requirements
        ↓
Required calculations
        ↓
Permissible limits
        ↓
Compliance determination


The compliance rules must come from OIML R76.

They must NOT be guessed by the application.


---

# 11. Automatic PASS / FAIL Determination

The software must automatically determine whether
the applicable test satisfies OIML R76 requirements.

Conceptual example:

Observed Result
        ↓
Compare with
Applicable R76 requirement
        ↓

Within permissible limit
        → PASS

Outside permissible limit
        → FAIL


This decision should be made automatically by the software.


---

# 12. Test Report Generation

The software must automatically prepare standardized
test reports.

Reports must automatically populate information such as:

- Laboratory information
- Manufacturer information
- Instrument information
- Technical specifications
- Entered test observations
- Calculated values
- Compliance results

The system should reduce repetitive manual report preparation.


---

# 13. Required Export Formats

The problem statement explicitly requires standardized
reports in:

### PDF

Printable final report.

### Editable Format

Examples given by the PS include:

Microsoft Word or another editable document format.


Therefore, supporting only PDF would NOT fully satisfy
the expected solution.


---

# 14. Supporting Documents

The application must allow users to attach:

- Photographs
- Supporting documents

These attachments should be associated with the
relevant instrument/test/report.


---

# 15. Digital Signatures

Digital signatures are mentioned as:

**Optional**

Therefore:

Digital signature support is NOT mandatory for the core solution.

It can be implemented as an additional feature.


---

# 16. Digital Report Repository

The application must maintain a digital repository
of completed test reports.

Reports should remain linked to the relevant instrument.


Required concept:

Instrument
    ↓
Test / Evaluation
    ↓
Generated Report
    ↓
Stored in Repository


---

# 17. Instrument-Wise Test History

The system must maintain test history for individual instruments.

A user should therefore be able to select an instrument
and access its previous test/report records.

Conceptually:

Instrument A

    Test / Report 1
    Test / Report 2
    Test / Report 3
    ...


---

# 18. Search and Retrieval

The application must provide a mechanism for finding
previously generated reports.

The PS requires:

- Search
- Retrieval of old/generated reports

The exact search filters are not specified by the PS
and can be designed by the implementation team.


---

# 19. Dashboard

The application must provide a dashboard for monitoring
testing and report activity.

The PS specifically mentions information such as:

- Completed reports
- Reports/tests in process
- Historical access
- Report status

The precise visual design and metrics are left to the team.


---

# 20. User Access and Security

The software must provide:

- Secure user access
- Role-based permissions

Therefore, authentication and authorization are
required components.

The problem statement does NOT prescribe a specific
authentication mechanism or technology.


---

# 21. Future OIML Revision Support

The application must support future updates when
OIML recommendations are revised.

This means the software architecture should not make
future standards changes unnecessarily difficult.

The PS requires the capability but does NOT prescribe
how it must technically be implemented.


---

# 22. Technical Documentation

The expected solution explicitly requires technical documentation.

The documentation should describe:

### Software Architecture

How the system and its components are structured.

### Calculation Methodology

How OIML R76 calculations and compliance determination
are implemented.

### Deployment Framework

How the application is deployed and operated.


---

# 23. Application Type

The expected solution specifies:

**Desktop and/or web-based application**

Therefore a mobile application is NOT required.

For our implementation we can choose:

Web Application

which satisfies this requirement.


---

# 24. Mandatory Functional Requirements Summary

| ID | Requirement | Mandatory |
|---|---|---|
| FR-01 | Manufacturer details entry | Yes |
| FR-02 | Instrument specifications entry | Yes |
| FR-03 | Model information entry | Yes |
| FR-04 | Technical parameters entry | Yes |
| FR-05 | Laboratory conditions entry | Yes |
| FR-06 | Environmental conditions entry | Yes |
| FR-07 | OIML R76 test observation entry | Yes |
| FR-08 | Automatic input validation | Yes |
| FR-09 | Automatic calculations | Yes |
| FR-10 | Permissible error calculation | Yes |
| FR-11 | OIML R76 compliance determination | Yes |
| FR-12 | Automatic PASS / FAIL determination | Yes |
| FR-13 | Automatic standardized report generation | Yes |
| FR-14 | PDF export | Yes |
| FR-15 | Editable report export such as Word | Yes |
| FR-16 | Photograph attachment | Yes |
| FR-17 | Supporting document attachment | Yes |
| FR-18 | Digital report repository | Yes |
| FR-19 | Instrument-wise test history | Yes |
| FR-20 | Search and retrieval | Yes |
| FR-21 | Dashboard | Yes |
| FR-22 | Secure user access | Yes |
| FR-23 | Role-based permissions | Yes |
| FR-24 | Future OIML revision support | Yes |
| FR-25 | Technical documentation | Yes |
| FR-26 | Digital signature | Optional |


---

# 25. What the PS Does NOT Explicitly Require

The following are NOT explicit requirements of SIH26035:

AI / ML
LLM chatbot
OCR
Blockchain
QR verification
Mobile application
Real-time IoT integration
Cloud deployment
AWS
Redis
Microservices
Predictive analytics

These may be added only if they genuinely improve the solution.

They should not replace the mandatory OIML R76 functionality.


---

# 26. External Knowledge Required Before Implementation

The PS tells us WHAT the software should do.

It does NOT give us the complete technical testing logic.

Before implementing the compliance engine, we still need to study:

OIML Recommendation R76

Legal Metrology Act, 2009

Legal Metrology (General) Rules, 2011


From OIML R76 we need to extract:

Applicable instrument classifications

Required tests

Required observations

Formulas

Maximum permissible errors

PASS / FAIL conditions

Test-specific validation rules


---

# 27. Core System Flow Derived From the PS

User Authentication
        ↓
Manufacturer Registration
        ↓
Instrument / Model Registration
        ↓
Technical Specifications
        ↓
Laboratory & Environmental Conditions
        ↓
Select / Perform OIML R76 Test
        ↓
Enter Observations
        ↓
Automatic Input Validation
        ↓
Automatic Calculations
        ↓
Determine Permissible Error
        ↓
OIML R76 Compliance Evaluation
        ↓
PASS / FAIL
        ↓
Complete Evaluation
        ↓
Generate Standardized Report
        ↓
PDF + Editable Document
        ↓
Store in Report Repository
        ↓
Search / Retrieve / View History


---

# 28. Minimum Solution That Satisfies the PS

A minimum compliant prototype should demonstrate:

Authentication with role-based access

Instrument and manufacturer registration

Instrument technical specifications

Laboratory/environmental conditions

Digital forms for implemented OIML R76 tests

Automatic test-data validation

Automatic OIML R76 calculations

Automatic permissible-error calculation

Automatic COMPLIANT / NONCOMPLIANT outcome (display PASS / FAIL)

Standardized report generation

PDF export

Editable report export

Photo/document attachment

Report repository

Instrument test history

Dashboard

Search/retrieval

Architecture/calculation/deployment documentation


---

# 29. Central Technical Requirement

The heart of SIH26035 is NOT the dashboard.

It is NOT AI.

It is NOT report styling.

The core system is:

          Test Observations
                 ↓
         OIML R76 Logic
                 ↓
       Automatic Calculations
                 ↓
       Compliance Evaluation
                 ↓
            PASS / FAIL
                 ↓
        Standardized Report


If this calculation and compliance layer is incorrect,
the solution does not correctly solve SIH26035.


---

# 30. Definition of Done

The core solution can be considered complete when a laboratory
user can:

1. Log into the system.
2. Register a manufacturer and NAWI model.
3. Enter the required technical specifications.
4. Record laboratory and environmental conditions.
5. Enter observations for applicable OIML R76 tests.
6. Have the system validate the observations.
7. Have the system automatically calculate required values.
8. Have the system determine permissible errors.
9. Have the system automatically determine compliance/pass-fail.
10. Generate a standardized report.
11. Export the report to PDF.
12. Export an editable report.
13. Attach photographs/supporting documents.
14. Retrieve previous reports.
15. View instrument test history.
16. Monitor reports/tests through a dashboard.

# 31. Frozen architectural acceptance contracts

- All 17 sections are first-class; Sections 16/17 are examination/checklist workflows.
- workflow_status, evaluation_status and compliance_outcome are independent. Approval attests to an evaluation record; a COMPLETE/NONCOMPLIANT evaluation may be approved and reported.
- A negative observed result is different from incomplete evidence or an unverified rule. Missing rules produce TODO_REGULATORY_VALIDATION, REVIEW_REQUIRED and UNDETERMINED, never an invented threshold or N/A.
- Every inherited regulatory assertion is a candidate until verified with exact edition/clause/source evidence and competent sign-off. This document states product intent, not independent legal verification. DECISIONS F18 lists REG-01 through REG-17.
- Exact Decimal arithmetic and canonical snapshots/hashes preserve calculation identity. No display rounding before comparison unless a verified rule requires it.
- User access uses UUID-based user_role_assignments with explicit GLOBAL/LABORATORY scope. ADMIN has no automatic final approval or report issue authority. Manufacturers are lab-owned in v1.
- Mutable sources use concurrency versions; changed inputs invalidate current results and relevant review approval. Retests/results are versioned and retain prior failures. Approved corrections create a new session revision.
- Unofficial previews are watermarked and separate from official reports. Issued PDF/DOCX use an immutable report_context_snapshot, a revision chain, private evidence and file/context hashes.
- Required infrastructure includes persistent refresh sessions, transactional audit and idempotency; audit ownership begins with the first mutations, not at the end of the build.
- Phase 0 is bootstrap only and still requires an explicit user request. Regulatory TODOs do not block bootstrap but block affected authoritative evaluation and official issue.

# 32. Traceability of requirements to specifications

| Requirement family | Detailed contract |
|---|---|
| Instrument/manufacturer/laboratory data and history | 05 schema, 06 API |
| Applicable tests, validation, calculations and outcomes | 02 worksheets, 04 engine |
| Roles, tenant isolation, approval and revisions | 07 RBAC/workflow |
| Photos, evidence, calibration and environment | 03 architecture, 05 schema, 06 API |
| Standardized PDF/DOCX, repository and search | 08 reports, 06 API |
| Future standards and reproducibility | DECISIONS F08–F12, 04 engine |
| Verification and delivery phases | 09 test plan, BUILD_PLAN |
