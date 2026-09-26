# Phase 22 — Render backend + Vercel frontend

## Stage 1 — production request topology

Browser: `https://<vercel-app>/api/v1/...`

Next.js rewrite: `https://<render-service>/api/v1/...`

Frontend production variables:

```text
NEXT_PUBLIC_API_BASE_URL=/
BACKEND_API_ORIGIN=https://<render-service>.onrender.com
```

## Stage 2 — managed PostgreSQL and private S3

Completed:
- Render PostgreSQL 17 in Singapore;
- Alembic repository head applied;
- private versioned S3 bucket in `ap-southeast-1`;
- all four Block Public Access controls enabled;
- least-privilege S3 runtime IAM;
- live PostgreSQL and S3 dependency verification.

## Stage 3 — Render backend deployment

Create a Render Web Service:

```text
Repository: ramansingh2004/SIH26035
Branch: main
Name: sih26035-api
Region: Singapore
Language: Python 3
Root Directory: backend
Build Command: uv sync --frozen --no-dev
Start Command: uv run python -m scripts.start_render
Health Check Path: /health
```

`backend/.python-version` pins Render to Python 3.12.

Do not use bare `uvicorn app.main:app`: the dedicated entrypoint converts
`RENDER_DATABASE_URL` before FastAPI settings are imported.

### Environment variables

```text
ENVIRONMENT=production
RENDER_DATABASE_URL=<Render Postgres INTERNAL database URL>
JWT_SECRET=<permanent generated secret>
COOKIE_SECURE=true
ALLOWED_ORIGINS=["https://stage4.invalid"]

STORAGE_PROVIDER=s3
STORAGE_BUCKET=sih26035-production-store
STORAGE_REGION=ap-southeast-1
STORAGE_ACCESS_KEY=<dedicated runtime IAM access key>
STORAGE_SECRET_KEY=<dedicated runtime IAM secret key>
```

Do not set `STORAGE_ENDPOINT` for AWS S3. Render supplies `PORT`.

The `stage4.invalid` origin is deliberately temporary. Stage 4 replaces it with the
stable Vercel production origin.

Generate the permanent JWT secret once and store it only in Render:

```text
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Migration gate

If the selected Render plan supports a pre-deploy command:

```text
uv run python -m scripts.render_predeploy
```

This validates production configuration, applies `alembic upgrade head`, then verifies
PostgreSQL and S3.

Render pre-deploy commands are not available on free web services. On a free service,
leave that field unset. The initial Stage 3 database was already migrated and verified
during Stage 2. For future schema-changing deployments, run migration/dependency checks
explicitly before deploying.

Never run migrations automatically from FastAPI startup.

### Public verification

After deployment:

```text
$env:RENDER_SERVICE_URL="https://<service>.onrender.com"
uv run python -m scripts.check_render_service
Remove-Item Env:RENDER_SERVICE_URL
```

The check verifies `/health`, disabled production docs/OpenAPI, the unauthenticated auth
boundary, and `Cache-Control: no-store`.

### Stage 3 source acceptance

```text
cd backend
uv run ruff check .
uv run pytest tests/test_phase22_stage3_contracts.py -q
```

## Stage 4 — Vercel frontend deployment

Deploy Next.js, replace the temporary Render `ALLOWED_ORIGINS` value with the stable
Vercel production origin, and configure S3 browser-upload CORS with that exact origin.

## Stage 5 — production acceptance

Verify authentication, lab scope, master data, evaluation, review/approval, reports,
evidence upload/download, history, and production security boundaries.
