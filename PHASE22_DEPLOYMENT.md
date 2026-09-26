# Phase 22 — Render backend + Vercel frontend

## Stage 1 — production topology

Production browser traffic stays same-origin on Vercel and `/api/v1/*` is rewritten to
Render. This preserves the strict refresh/CSRF cookie architecture.

## Stage 2 — managed infrastructure

Completed:

- Render PostgreSQL 17 in Singapore;
- Alembic repository head applied;
- private versioned S3 in `ap-southeast-1`;
- all S3 Block Public Access controls enabled;
- least-privilege runtime IAM;
- live PostgreSQL/S3 verification.

## Stage 3 — Render backend

Production backend:

```text
https://sih26035-h3s9.onrender.com
```

Public backend verification passed.

## Stage 4 — Vercel frontend

Production frontend:

```text
https://sih26035.vercel.app
```

The same-origin Vercel -> Render rewrite is verified. Render `ALLOWED_ORIGINS` and S3
CORS must both contain exactly:

```text
https://sih26035.vercel.app
```

## Stage 5 — production acceptance

Stage 5 accepts the deployed system without weakening the frozen regulatory safety
model.

The trusted repository artifact is still the candidate OIML R76 configuration and has
regulatory blockers. Therefore Stage 5 MUST NOT activate it synthetically or fabricate a
COMPLIANT/NONCOMPLIANT outcome merely to produce an official report. Acceptance verifies
that those gates remain enforced.

### 1. One-time production administrator bootstrap

A fresh migrated production database contains no administrator. Run the bootstrap from a
trusted local machine using Render's temporary EXTERNAL database URL.

Set only temporary shell variables. Do not write credentials to `.env` or Git:

```text
RENDER_DATABASE_URL=<Render EXTERNAL database URL>
PRODUCTION_ADMIN_EMAIL=<administrator email>
PRODUCTION_ADMIN_NAME=<administrator display name>
```

Then:

```text
uv run python -m scripts.bootstrap_production_admin
```

The password is prompted twice without echo.

After bootstrap, remove the temporary environment variables and restrict Render
PostgreSQL external access again. The deployed backend continues using the INTERNAL
database URL.

### 2. Production acceptance credentials

Set temporary local shell variables:

```text
VERCEL_FRONTEND_URL=https://sih26035.vercel.app
PRODUCTION_ADMIN_EMAIL=<same administrator email>
PRODUCTION_ADMIN_PASSWORD=<same administrator password>
```

Run:

```text
uv run python -m scripts.check_production_acceptance
```

The acceptance script:

1. logs in through the stable Vercel origin;
2. verifies `Secure`, `HttpOnly` refresh, readable CSRF, and `SameSite=Strict`;
3. verifies refresh-token rotation;
4. creates/reuses `SIH26035-PROD` laboratory;
5. explicitly grants the administrator laboratory roles needed for acceptance;
6. verifies the scoped dashboard;
7. registers/reuses the trusted candidate OIML R76 artifact without activating it;
8. creates/reuses manufacturer/instrument master data;
9. performs a real S3 CORS preflight from the exact Vercel origin;
10. uploads, finalizes, downloads and hashes versioned evidence;
11. creates a 17-section candidate evaluation session;
12. verifies `TODO_REGULATORY_VALIDATION`;
13. verifies revision/review/correction/instrument/report repository surfaces;
14. verifies incomplete review/report progression is blocked;
15. verifies refresh rotation and logout.

The synthetic acceptance records are visibly named `Stage 5 Acceptance ...` and
`STAGE5-*`. They are not regulatory evidence of compliance.

### Why Stage 5 does not issue an official report

Official report generation requires the frozen Phase 16/21 governance gates: approved,
complete, determined evaluation data backed by a regulatory configuration that is
eligible for use. The production candidate artifact intentionally fails authoritative
regulatory validation. Stage 5 therefore accepts the report repository and its blocking
behavior, not a fabricated official report.

A future authoritative ruleset can unlock genuine report generation without changing
the workflow architecture.

### Stage 5 source acceptance

From `backend/`:

```text
uv run ruff check .
uv run pytest tests/test_phase22_stage5_contracts.py -q
```

After live acceptance passes, Phase 22 deployment is complete.
