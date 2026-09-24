import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 18 keeps the application light-theme only", async () => {
  const css = await source("src/app/globals.css");
  assert.match(css, /color-scheme:\s*light/);
  assert.doesNotMatch(css, /prefers-color-scheme:\s*dark/);
});

test("access tokens stay in memory while refresh uses the HttpOnly session cookie", async () => {
  const client = await source("src/lib/api/client.ts");
  assert.match(client, /let accessToken: string \| null = null/);
  assert.match(client, /credentials:\s*"include"/);
  assert.match(client, /\/api\/v1\/auth\/refresh/);
  assert.match(client, /X-CSRF-Token/);
  assert.doesNotMatch(client, /localStorage/);
  assert.doesNotMatch(client, /sessionStorage.*access/i);
});

test("typed API foundation carries concurrency and idempotency headers", async () => {
  const client = await source("src/lib/api/client.ts");
  assert.match(client, /If-Match/);
  assert.match(client, /Idempotency-Key/);
  assert.match(client, /Authorization/);

  const key = await source("src/lib/api/idempotency.ts");
  assert.match(key, /crypto\.randomUUID/);
});

test("frontend authorization derives from backend permissions and lab scope", async () => {
  const permissions = await source("src/lib/auth/permissions.ts");
  const sidebar = await source("src/components/app-shell/sidebar.tsx");

  assert.match(permissions, /global_permissions/);
  assert.match(permissions, /laboratory_id/);
  assert.match(sidebar, /dashboard:read/);
  assert.match(sidebar, /session:read/);
  assert.match(sidebar, /report:read/);
  assert.match(sidebar, /audit:read/);
});

test("Phase 18 establishes TanStack Query, React Hook Form and Zod", async () => {
  const packageJson = JSON.parse(await source("package.json"));
  for (const dependency of [
    "@tanstack/react-query",
    "react-hook-form",
    "zod",
    "@hookform/resolvers",
  ]) {
    assert.ok(packageJson.dependencies[dependency], `${dependency} missing`);
  }

  const login = await source("src/app/login/page.tsx");
  assert.match(login, /useForm/);
  assert.match(login, /zodResolver/);
});

test("regulatory compliance is not calculated by the dashboard foundation", async () => {
  const dashboard = await source("src/app/(protected)/dashboard/page.tsx");
  assert.match(dashboard, /compliance_outcomes|Compliance outcomes/i);
  assert.doesNotMatch(
    dashboard,
    /permissible.*error|maximum.*permissible.*error/i,
  );

  const blocker = await source("src/components/ui/regulatory-blocker.tsx");
  assert.match(blocker, /TODO_REGULATORY_VALIDATION/);
});
