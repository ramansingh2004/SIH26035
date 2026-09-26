# Phase 22 — Render backend + Vercel frontend

## Stage 1 contract

Stage 1 prepares the codebase for production deployment without deploying infrastructure,
changing database schema, or weakening authentication.

### Production request topology

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

If `BACKEND_API_ORIGIN` is absent, no Next.js API rewrite is installed.

### Backend production variables

The Render service will use:

```text
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET=<secret>
COOKIE_SECURE=true
ALLOWED_ORIGINS=["https://<vercel-app>.vercel.app"]

STORAGE_PROVIDER=s3
STORAGE_BUCKET=<bucket>
STORAGE_REGION=<region>
STORAGE_ACCESS_KEY=<secret>
STORAGE_SECRET_KEY=<secret>
```

Do not commit any real values.

Before production startup, validate the environment:

```text
uv run python -m scripts.check_production_config
```

### Render process contract

The FastAPI service must bind to all interfaces and Render's assigned port:

```text
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Render health-check path:

```text
/health
```

Database migration execution and managed PostgreSQL/S3 provisioning are Stage 2.

### Preview deployments

For the first production deployment, use the stable Vercel production origin in
`ALLOWED_ORIGINS`. A Vercel preview URL is a different origin and must be explicitly
authorized before using authenticated preview deployments. Do not replace the explicit
origin list with a permissive wildcard.

### Stage 1 acceptance

From `frontend/`:

```text
npm run lint
npm run typecheck
npm test
```

From `backend/`:

```text
uv run ruff check .
uv run pytest
```

The full backend suite requires the existing isolated `TEST_DATABASE_URL` ending in
`_test`.
