# SIH26035 — Phase 0

Repository bootstrap for the NAWI laboratory platform. The authoritative design is
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), [DECISIONS.md](DECISIONS.md), and
[BUILD_PLAN.md](BUILD_PLAN.md), Specification Freeze v1.

## What is available

- FastAPI application with public process health at `GET /health`.
- Environment-backed Pydantic settings and explicit async SQLAlchemy factories.
- Alembic configuration with empty metadata and no feature migrations.
- Minimal Next.js / React / TypeScript startup page, ESLint, and formatting tools.
- Backend bootstrap tests and a frontend build/start/HTTP smoke test.

Phase 1 and later functionality is not implemented. There are no domain tables,
authentication, regulatory evaluators, report generation, or external API integrations.
The compliance engine is deferred to its phase and must remain independent of
FastAPI/SQLAlchemy. All future metrological calculations must use exact `Decimal`
under the frozen decisions. REG-01 through REG-17 remain
`TODO_REGULATORY_VALIDATION`; this bootstrap does not resolve them.

## Prerequisites

- Python 3.12 (the default in `backend/.python-version`; project supports 3.12–3.14).
- uv for Python dependency management.
- Node.js 24 and npm (Node 22.14+ through 24 is supported by this bootstrap).
- PostgreSQL is not required to start or test Phase 0. It is needed only if you
  intentionally invoke an online Alembic command against your own database.

`backend/uv.lock` and `frontend/package-lock.json` pin the resolved dependency trees.
The project does not depend on runtime packages preinstalled in this workspace.

## Backend startup

From the repository root, in PowerShell or a Unix shell:

```sh
cd backend
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/health`: expected HTTP 200 and `{"status":"ok"}`.
The route is **not** `/api/v1/health`. API documentation is available at `/docs`.
Stop the development server with Ctrl+C.

Optional configuration: copy `backend/.env.example` to `backend/.env` using
`Copy-Item .env.example .env` (PowerShell) or `cp .env.example .env` (Unix).
Settings load that file by its backend path. Never commit `.env` or real credentials.

`DATABASE_URL` is optional for the API bootstrap. When supplied it must use
`postgresql+asyncpg://...`. Neither application startup nor `/health` creates an
engine or opens a database connection. Health checks process availability only.

## Frontend startup

In a separate terminal, from the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. Stop with Ctrl+C. The frontend uses system fonts and
does not require an external font service or a running backend. It is a static
bootstrap page, not a laboratory dashboard.

For a production startup check:

```sh
npm run build
npm start
```

## Formatting, lint and tests

From `backend/`:

```sh
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run alembic heads
```

`alembic heads` intentionally prints no revisions. Do not create tables with
`Base.metadata.create_all()`. Feature migrations begin in their authorized phases.
The async Alembic environment is prepared for PostgreSQL; Phase 0 does not claim
live database connectivity or a migrated database.

From `frontend/`:

```sh
npm run format
npm run format:check
npm run lint
npm run typecheck
npm test
```

`npm test` builds the app, then uses Node's built-in test runner to start the built
server on a temporary loopback port, fetch the page, verify HTTP 200/content, and
stop the server. It requires no browser downloads or additional test framework.
Do not run a separate build/dev process in the same frontend directory during
this test; Next.js writes generated types/build output under `.next/`.

Formatting commands are scoped to code directories so the frozen specifications
remain unchanged. `PHASE0_REPORT.md` records the actual verification results and
file inventory for this delivery. The next implementation phase requires a
separate user instruction.
