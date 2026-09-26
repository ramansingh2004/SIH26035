# Phase 23 Stage 3 — SIH judge walkthrough and final demo acceptance

Stage 3 validates the deployed Phase 23 demonstration as a judge-ready, repeatable
walkthrough without weakening any regulatory control.

## What Stage 3 proves

The final acceptance verifies:

- the dedicated `SIH26035-DEMO` laboratory and three independent lab-scoped identities;
- the two candidate Stage 1 shells remain `UNDETERMINED` because the candidate OIML
  artifact still has regulatory-validation blockers;
- `SIH26035-DEMO-POSITIVE` is `COMPLETE / COMPLIANT` only as an explicitly synthetic
  software demonstration;
- `SIH26035-DEMO-NEGATIVE` is `COMPLETE / NONCOMPLIANT` only as an explicitly synthetic
  software demonstration;
- all 17 sections remain visible, with only Section 1 required by the synthetic fixture;
- the selected run, versioned deterministic result, calculation trace and negative failed
  condition are preserved in history;
- the lab dashboard reflects the seeded demo state;
- an `UNOFFICIAL_PREVIEW` can be rendered and both PDF and DOCX bytes can be downloaded
  from private object storage with matching SHA-256 hashes;
- synthetic sessions remain blocked from regulatory review, final approval and official
  report generation;
- the report repository contains no official report generated from either synthetic
  complete demo scenario;
- canonical named demo sessions are unique, making the demo repeatable without deleting
  or rewriting append-only audit/regulatory history.

No Stage 3 check changes an evaluation outcome or activates a ruleset. The only new
record created by the live verifier is a normal unofficial preview and its private files.

## Final judge walkthrough

Use `https://sih26035.vercel.app`.

### 1. Login and select the demo laboratory

Login as the Demo Engineer and select:

`SIH26035 Demonstration Laboratory` (`SIH26035-DEMO`)

Explain:

> The demonstration lab is isolated from normal data. The demo accounts are explicitly
> lab-scoped, and the system does not grant approval authority merely because a user is
> an administrator.

### 2. Dashboard

Open the dashboard.

Show that the lab contains both determined synthetic scenarios and the candidate
undetermined shells. Point out that the UI keeps workflow, evaluation status and
compliance outcome as separate axes.

Suggested judge explanation:

> A result being complete does not automatically mean it is approved or officially
> reportable. Workflow state, evaluation completeness and compliance outcome are
> deliberately independent.

### 3. Candidate regulatory-blocker demonstration

Search Evaluations for:

- `SIH26035-DEMO-NOMINAL`
- `SIH26035-DEMO-ADVERSE`

These use the repository's candidate OIML artifact. Their outcome remains
`UNDETERMINED`, and applicability cannot be authoritatively confirmed.

Suggested explanation:

> Where verified regulatory rules are missing, the platform refuses to invent a
> threshold or compliance conclusion. That is an explicit safety boundary.

### 4. Positive deterministic scenario

Search for:

`SIH26035-DEMO-POSITIVE`

Show:

- evaluation `COMPLETE`;
- outcome `COMPLIANT`;
- synthetic/demo-only labelling;
- 17-section navigator;
- Section 1 as the only required demonstration assessment;
- Sections 2–17 explicitly not applicable to this synthetic fixture;
- stored procedure context, four observations and deterministic calculation trace;
- lifecycle/history panel.

Say clearly:

> This COMPLIANT label demonstrates the deterministic software path against a synthetic
> fixture. It is not an OIML regulatory conclusion.

### 5. Negative deterministic scenario

Search for:

`SIH26035-DEMO-NEGATIVE`

Show:

- evaluation `COMPLETE`;
- outcome `NONCOMPLIANT`;
- the same deterministic path;
- the failed-condition trace caused by the deliberately adverse synthetic observation.

Suggested explanation:

> The same engine and traceability path produces the opposite outcome when the input
> crosses the synthetic demonstration limit. Nothing is decided by an LLM.

### 6. Unofficial report preview

From either complete synthetic scenario, create an unofficial preview.

Show the `UNOFFICIAL_PREVIEW` labelling and download PDF or DOCX.

Explain:

> Preview is intentionally available for review and presentation. Official generation is
> a different gate and remains blocked for synthetic/unverified data.

### 7. Official-workflow guard

Show that the synthetic scenario never enters regulatory approval and cannot create an
official report.

The backend independently enforces `SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN`; this is not only
a disabled frontend button.

### 8. Report repository

Open Reports for the demo laboratory.

The synthetic complete scenarios must not appear as official report records. This is an
important positive demonstration: a complete synthetic result is still not an official
regulatory report.

## Safe repeat/reset before a judge demo

Do **not** delete production rows, rewrite history or manually edit PostgreSQL.

The safe reset is deterministic and idempotent:

1. Re-run `seed_phase23_demo_foundation` if the canonical lab/master-data foundation
   needs to be re-verified.
2. Re-run `seed_phase23_demo_scenarios`; completed canonical positive/negative scenarios
   are detected and preserved instead of duplicated.
3. Run `verify_phase23_demo_walkthrough`.
4. Log out of the browser, log back in as the desired demo role and select
   `SIH26035-DEMO`.

Append-only history is deliberately preserved. "Reset" means restoring/verifying the
known canonical presentation state, not erasing regulatory/audit history.

## Local source validation

From `backend/`:

```powershell
uv run ruff check .
uv run pytest tests/test_phase23_stage3_contracts.py -q
```

## Live production acceptance

Set the three demo-user passwords in the shell:

```powershell
$engineer = Read-Host "Demo Engineer password" -AsSecureString
$reviewer = Read-Host "Demo Reviewer password" -AsSecureString
$approver = Read-Host "Demo Approver password" -AsSecureString

$env:PHASE23_ENGINEER_PASSWORD = [System.Net.NetworkCredential]::new("", $engineer).Password
$env:PHASE23_REVIEWER_PASSWORD = [System.Net.NetworkCredential]::new("", $reviewer).Password
$env:PHASE23_APPROVER_PASSWORD = [System.Net.NetworkCredential]::new("", $approver).Password
```

Optional override:

```powershell
$env:VERCEL_FRONTEND_URL = "https://sih26035.vercel.app"
```

Run:

```powershell
uv run python -m scripts.verify_phase23_demo_walkthrough
```

Then clear secrets:

```powershell
Remove-Item Env:VERCEL_FRONTEND_URL -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_ENGINEER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_REVIEWER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_APPROVER_PASSWORD -ErrorAction SilentlyContinue

Remove-Variable engineer -ErrorAction SilentlyContinue
Remove-Variable reviewer -ErrorAction SilentlyContinue
Remove-Variable approver -ErrorAction SilentlyContinue
```

Do not commit any password values.
