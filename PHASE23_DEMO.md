# Phase 23 — SIH demo data

Phase 23 follows the frozen `BUILD_PLAN.md` requirement to provide an SIH-ready
demonstration dataset without weakening regulatory controls.

## Safety rule

The repository OIML R76 artifact is still a candidate with
`TODO_REGULATORY_VALIDATION` blockers.

Therefore:

- candidate production sessions may be demonstrated;
- unofficial previews may be demonstrated;
- candidate records must remain visibly unofficial/undetermined;
- synthetic complete scenarios must be explicitly labelled;
- synthetic scenarios must not be issuable as official reports;
- no direct database state editing is used as a production shortcut.

## Stage plan

### Stage 1 — Demo foundation

Creates through the deployed API:

- dedicated `SIH26035-DEMO` laboratory;
- separate Demo Engineer, Reviewer and Approving Officer users;
- a visibly synthetic manufacturer;
- a Class III, 30 kg single-range digital scale;
- explicit range;
- load-cell and indicator components;
- reference masses, environmental logger and programmable AC-source equipment;
- two candidate scenario shells:
  - `SIH26035-DEMO-NOMINAL`;
  - `SIH26035-DEMO-ADVERSE`.

Both Stage 1 scenarios intentionally remain `UNDETERMINED` because the candidate
ruleset is not authoritative.

### Stage 2 — Complete positive/negative demo scenarios

Next stage.

It will add deterministic synthetic demo fixtures for one positive and one negative
workflow while adding an explicit application-level non-issuance guard for synthetic
demo rules/data. Reviewer and approving-officer actions will use distinct users.

No official report will be generated or issued from synthetic demo records.

### Stage 3 — Judge walkthrough and reset

Final Phase 23 stage.

It will verify the intended SIH walkthrough, dashboard/history/repository presentation,
unofficial preview download and repeatable/resettable demo state.

## Stage 1 setup

From `backend/`, set the production admin identity:

```powershell
$env:VERCEL_FRONTEND_URL = "https://sih26035.vercel.app"
$env:PRODUCTION_ADMIN_EMAIL = "YOUR_ADMIN_EMAIL"
$securePassword = Read-Host "Production admin password" -AsSecureString
$env:PRODUCTION_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
```

The Stage 1 script also needs passwords for the three demonstration users. You can set
them as temporary environment variables:

```powershell
$engineer = Read-Host "Demo Engineer password" -AsSecureString
$reviewer = Read-Host "Demo Reviewer password" -AsSecureString
$approver = Read-Host "Demo Approver password" -AsSecureString

$env:PHASE23_ENGINEER_PASSWORD = [System.Net.NetworkCredential]::new("", $engineer).Password
$env:PHASE23_REVIEWER_PASSWORD = [System.Net.NetworkCredential]::new("", $reviewer).Password
$env:PHASE23_APPROVER_PASSWORD = [System.Net.NetworkCredential]::new("", $approver).Password
```

Each password must be 12-128 characters.

Run:

```powershell
uv run python -m scripts.seed_phase23_demo_foundation
```

The script is retry-safe for the named Stage 1 demo resources and never prints the
passwords.

## Source validation

```powershell
uv run ruff check .
uv run pytest tests/test_phase23_stage1_contracts.py -q
```

## Clean temporary shell secrets

```powershell
Remove-Item Env:VERCEL_FRONTEND_URL -ErrorAction SilentlyContinue
Remove-Item Env:PRODUCTION_ADMIN_EMAIL -ErrorAction SilentlyContinue
Remove-Item Env:PRODUCTION_ADMIN_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_ENGINEER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_REVIEWER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:PHASE23_APPROVER_PASSWORD -ErrorAction SilentlyContinue

Remove-Variable securePassword -ErrorAction SilentlyContinue
Remove-Variable engineer -ErrorAction SilentlyContinue
Remove-Variable reviewer -ErrorAction SilentlyContinue
Remove-Variable approver -ErrorAction SilentlyContinue
```

Do not commit any credential values.
