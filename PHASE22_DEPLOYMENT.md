# Phase 22 — Render backend + Vercel frontend

## Stage 1 — production request topology

Stage 1 prepares the codebase for production deployment without weakening authentication.

Browser:
`https://<vercel-app>/api/v1/...`

Next.js rewrite:
`https://<render-service>/api/v1/...`

The browser remains on the Vercel origin. This preserves the existing host-only
`HttpOnly` refresh cookie, readable CSRF cookie, `SameSite=Strict`, and
`credentials: include` behavior.

### Frontend production variables

Set in the Vercel project:

```text
NEXT_PUBLIC_API_BASE_URL=/
BACKEND_API_ORIGIN=https://<render-service>.onrender.com
```

`BACKEND_API_ORIGIN` is intentionally not public.

Local development remains:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Stage 2 — managed PostgreSQL and private S3 contract

Stage 2 prepares the production data dependencies. It does not create or deploy the
Render web service or Vercel project.

### Render PostgreSQL

Create a managed Render PostgreSQL database in the same Render region that will host
the backend. Use its internal/private connection string for the backend service.

Render supplies a standard PostgreSQL URL. The application intentionally continues to
require SQLAlchemy's asyncpg driver URL. Therefore Render's URL is configured as:

```text
RENDER_DATABASE_URL=postgresql://...
```

`scripts.render_environment` converts it at the deployment boundary to:

```text
DATABASE_URL=postgresql+asyncpg://...
```

The adapter never prints the connection string.

Do not change `app.core.config.Settings` to accept arbitrary synchronous PostgreSQL
drivers. The core application invariant remains asyncpg-only.

### Production migration command

Migrations remain separate from FastAPI startup:

```text
uv run python -m scripts.run_production_migrations
```

The command:

1. normalizes `RENDER_DATABASE_URL` when present;
2. requires `ENVIRONMENT=production`;
3. runs `alembic upgrade head`;
4. does not print database credentials.

Stage 3 will attach this command to the Render deployment mechanism appropriate for the
selected Render plan.

### Private S3 bucket

Use a dedicated production bucket. Required bucket properties:

- bucket versioning enabled;
- all four S3 Block Public Access controls enabled;
- no public bucket policy;
- runtime credentials scoped only to this bucket;
- no storage credentials exposed to the frontend.

The backend's `S3Storage.ready()` rejects a bucket that is not versioned or does not
have all four bucket-level public access blocks enabled.

A least-privilege runtime policy template is committed at:

```text
deploy/aws/s3-runtime-policy.json.example
```

Replace only `REPLACE_BUCKET_NAME` before creating the IAM policy.

### Browser upload CORS

Evidence upload is intentionally direct-to-storage using a backend-generated presigned
PUT URL. Therefore the S3 bucket needs a CORS rule for the final Vercel production
origin.

Template:

```text
deploy/aws/s3-cors.json.example
```

Do not use `*` for the production origin. Stage 4 will supply the exact stable Vercel
origin and the CORS rule will be finalized then.

### Render backend environment values

The eventual Render web service will receive:

```text
ENVIRONMENT=production
RENDER_DATABASE_URL=<from managed Render Postgres>
JWT_SECRET=<secret>
COOKIE_SECURE=true
ALLOWED_ORIGINS=["https://<stable-vercel-production-origin>"]

STORAGE_PROVIDER=s3
STORAGE_BUCKET=<bucket>
STORAGE_REGION=<region>
STORAGE_ACCESS_KEY=<runtime IAM access key>
STORAGE_SECRET_KEY=<runtime IAM secret key>
```

Do not commit actual values.

### Production configuration preflight

After environment variables are populated:

```text
uv run python -m scripts.check_production_config
```

This checks presence and security shape only.

### Live dependency verification

After the production database has been migrated and S3 credentials are configured:

```text
uv run python -m scripts.check_production_dependencies
```

It verifies:

- PostgreSQL connectivity;
- database Alembic revision equals repository head;
- S3 versioning;
- S3 bucket-level Block Public Access.

It does not print credentials or presigned URLs.

### Stage 2 local acceptance

No live cloud credentials are required for source acceptance.

From `backend/`:

```text
uv run ruff check .
uv run pytest tests/test_phase22_stage2_contracts.py -q
```

Full backend regression remains available with the existing isolated
`TEST_DATABASE_URL` ending in `_test`.

## Stage 3 — Render backend deployment

Stage 3 will create/configure the Render web service, connect it to the managed
PostgreSQL database, apply migrations through the Stage 2 migration command, configure
the health check, and verify the public backend service.

## Stage 4 — Vercel frontend deployment

Stage 4 will deploy Next.js, set the same-origin API rewrite variables, then finalize
`ALLOWED_ORIGINS` and S3 browser-upload CORS with the stable production Vercel origin.

## Stage 5 — production acceptance

Stage 5 will verify authentication, laboratory scope, master data, evaluation,
review/approval, report lifecycle, evidence upload/download, history, and production
security boundaries.
