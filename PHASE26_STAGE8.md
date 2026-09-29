# Phase 26 Stage 8 — Final SIH Demo Reset & Acceptance

Stage 8 is the operational closeout of Phase 26. It adds no new compliance
logic, no regulatory bypass, and no database migration.

The operator uses the existing public API and preserves all completed history.

## Required credentials

The command prompts securely when environment variables are absent.

Recommended PowerShell session variables:

```powershell
$env:PHASE26_ADMIN_EMAIL = "your-admin@example.com"
$env:PHASE26_ADMIN_PASSWORD = "<admin-password>"
$env:PHASE26_ENGINEER_PASSWORD = "<demo-engineer-password>"
```

For deployed Vercel:

```powershell
$env:PHASE26_DEMO_API_ORIGIN = "https://<your-vercel-origin>"
$env:PHASE26_DEMO_UI_ORIGIN = "https://<your-vercel-origin>"
```

For local development:

```powershell
$env:PHASE26_DEMO_API_ORIGIN = "http://127.0.0.1:8000"
$env:PHASE26_DEMO_UI_ORIGIN = "http://127.0.0.1:3000"
```

Passwords are never printed or written to disk.

## 1. Reset / seed

From `backend/`:

```powershell
uv run python -m scripts.phase26_demo reset
```

This command:

1. ensures `SIH26035-DEMO`;
2. ensures the demo engineer and resets only that demo user's password;
3. ensures the V3 synthetic ruleset remains `DRAFT`;
4. ensures a V3-aligned synthetic master instrument;
5. cancels only unfinished previous `SIH26035-FULL-DEMO-LIVE-*` sessions;
6. preserves every completed prior demo as history;
7. creates a fresh uniquely named V3 session;
8. configures the canonical V3 instrument snapshot;
9. confirms all 28 REQUIRED applicability slots;
10. creates 23 selected typed runs;
11. starts `TESTING`;
12. prints the exact judge URL.

The fresh session is intentionally stopped at `TESTING`.

## 2. Judge walkthrough

Log in as:

```text
demo.engineer@example.com
```

Use the password supplied to `PHASE26_ENGINEER_PASSWORD`.

Open the judge URL printed by the reset command.

Recommended demonstration sequence:

1. Show the evaluation header and the separate Workflow / Evaluation / Outcome axes.
2. Show that all 17 sections are represented.
3. Explain that Sections 1–15 use typed deterministic evaluators and Sections
   16–17 use specialized construction/checklist workflows.
4. Click **Complete all 17 synthetic demo sections**.
5. Show:
   - Workflow = `EXAMINATION`
   - Evaluation = `COMPLETE`
   - Outcome = `COMPLIANT`
   - 17/17 sections complete.
6. Open representative run history/result details to show persisted deterministic
   calculations, traceability and evidence.
7. Scroll to Reporting.
8. Click **Generate complete 17-section demo report**.
9. Download PDF and DOCX.
10. Point out the permanent document boundary:
    **SIMULATED / DEMONSTRATION REPORT - NOT AN OFFICIAL OIML CERTIFICATE**.
11. Explain that the report contains:
    - 17 sections;
    - 23 typed runs;
    - 92 observations;
    - 23 environment readings;
    - 24 equipment links;
    - 8 construction items;
    - 27 checklist rows;
    - 85 immutable evidence links representing 60 unique synthetic attachments.
12. Explain that synthetic sessions cannot enter technical review, final approval,
    official report generation or official report issue.

## 3. Automated final acceptance

Before the event, run the complete automated proof once:

```powershell
uv run python -m scripts.phase26_demo accept
```

It performs a fresh reset and then verifies the complete chain through the public
API:

```text
V3 seed/reset
  -> 28 REQUIRED applicability slots
  -> 23 typed runs
  -> Stage 6 one-click execution
  -> 17/17 COMPLETE + COMPLIANT
  -> Section 16
  -> Section 17
  -> Stage 7 full report
  -> PDF download + SHA-256
  -> DOCX download + SHA-256
  -> review BLOCKED
  -> official report generation BLOCKED
  -> no synthetic record in official report repository
```

## 4. Emergency re-reset

If somebody changes the demo immediately before judging, run:

```powershell
uv run python -m scripts.phase26_demo reset
```

Again.

The operator cancels only unfinished Stage 8 live-demo sessions. Completed
demonstrations remain intact in history.

To inspect the newest live-demo session:

```powershell
uv run python -m scripts.phase26_demo status
```

## Final integrity statement

Stage 8 does not claim independent human regulatory review. It does not activate
the synthetic V3 ruleset and does not create or issue an official report.

All Stage 8 evaluation/report data remain explicitly synthetic demonstration
fixtures.
