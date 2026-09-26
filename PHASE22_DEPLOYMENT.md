# Phase 22 — Render backend + Vercel frontend

## Stage 1 — production request topology

Browser:
`https://<vercel-app>/api/v1/...`

Next.js rewrite:
`https://<render-service>/api/v1/...`

Frontend production variables:

```text
NEXT_PUBLIC_API_BASE_URL=/
BACKEND_API_ORIGIN=https://<render-service>.onrender.com
```

The browser therefore stays on the Vercel origin while API traffic is transparently
proxied to Render. The existing strict refresh/CSRF cookie design remains same-site.

## Stage 2 — managed infrastructure

Completed:

- Render PostgreSQL 17 in Singapore;
- repository Alembic head applied;
- private versioned S3 bucket in `ap-southeast-1`;
- all four Block Public Access controls enabled;
- least-privilege S3 runtime IAM;
- live PostgreSQL/S3 verification.

## Stage 3 — Render backend

Production backend:

```text
https://sih26035-h3s9.onrender.com
```

Render service contract:

```text
Root Directory: backend
Build: uv sync --frozen --no-dev
Start: uv run python -m scripts.start_render
Health: /health
```

Public Stage 3 verification passed for health, disabled docs/OpenAPI, protected API
authentication boundary, and no-store policy.

Until Stage 4 is complete, Render may use the temporary origin:

```text
ALLOWED_ORIGINS=["https://stage4.invalid"]
```

## Stage 4 — Vercel frontend deployment

### 1. Create/import the Vercel project

Import the GitHub repository:

```text
ramansingh2004/SIH26035
```

Configure:

```text
Project Name: sih26035
Framework Preset: Next.js
Root Directory: frontend
Production Branch: main
```

Keep the framework-provided build/output defaults unless Vercel reports a concrete
reason to override them.

### 2. Production environment variables

Add these to the Vercel Production environment:

```text
NEXT_PUBLIC_API_BASE_URL=/
BACKEND_API_ORIGIN=https://sih26035-h3s9.onrender.com
```

`BACKEND_API_ORIGIN` intentionally has no `NEXT_PUBLIC_` prefix.

Environment-variable changes require a new Vercel deployment before the build uses
them.

### 3. Deploy and capture the stable production origin

Deploy `main`. After success, note the stable production URL, for example:

```text
https://sih26035.vercel.app
```

Use the exact origin shown by Vercel. Do not include a trailing slash.

### 4. Replace the temporary Render allowed origin

In Render -> `sih26035-api` -> Environment, change:

```text
ALLOWED_ORIGINS=["https://stage4.invalid"]
```

to:

```text
ALLOWED_ORIGINS=["https://<exact-vercel-production-origin>"]
```

Save and allow Render to redeploy/restart.

Do not use `*` with credentialed authentication.

### 5. Configure S3 browser-upload CORS

Open AWS S3:

```text
sih26035-production-store
-> Permissions
-> Cross-origin resource sharing (CORS)
```

Use:

```json
[
  {
    "AllowedHeaders": [
      "content-type"
    ],
    "AllowedMethods": [
      "PUT"
    ],
    "AllowedOrigins": [
      "https://<exact-vercel-production-origin>"
    ],
    "ExposeHeaders": [],
    "MaxAgeSeconds": 300
  }
]
```

Use the exact same Vercel origin as Render `ALLOWED_ORIGINS`. Do not use `*`.

This CORS rule is required because evidence files are uploaded directly from the browser
to a backend-generated presigned S3 PUT URL.

### 6. Public Stage 4 verification

From `backend/`:

```text
$env:VERCEL_FRONTEND_URL="https://<exact-vercel-production-origin>"
uv run python -m scripts.check_vercel_frontend
Remove-Item Env:VERCEL_FRONTEND_URL
```

The check requires:

- Vercel `/login` is reachable over HTTPS;
- `/api/v1/auth/me` on the Vercel origin reaches Render through the Next.js rewrite;
- the unauthenticated API boundary remains HTTP 401;
- the proxied backend response retains `Cache-Control: no-store`.

Full login/session/evidence behavior is tested in Stage 5.

### Stage 4 source acceptance

From `frontend/`:

```text
npm run lint
npm run typecheck
npm test
```

From `backend/`:

```text
uv run ruff check .
uv run pytest tests/test_phase22_stage4_contracts.py -q
```

## Stage 5 — production acceptance

Verify end-to-end login/refresh/logout, lab scope, master data, evaluations,
review/approval, reports, PDF/DOCX downloads, evidence upload/download, history, CORS,
cookies, and security boundaries.
