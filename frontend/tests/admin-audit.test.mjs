import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("all three Administration navigation modules are enabled", () => {
  const sidebar = read("src/components/app-shell/sidebar.tsx");

  for (const href of [
    "/admin/users",
    "/admin/laboratories",
    "/admin/audit",
  ]) {
    const position = sidebar.indexOf(`href: "${href}"`);
    assert.ok(position >= 0, `missing ${href}`);
    assert.match(
      sidebar.slice(position, position + 150),
      /implemented:\s*true/,
    );
  }
});

test("Audit Events uses only backend-supported filters", () => {
  const api = read("src/lib/admin-audit/api.ts");

  assert.match(api, /\/api\/v1\/audit-events/);
  for (const parameter of [
    "laboratory_id",
    "entity_type",
    "entity_id",
    "since",
    "until",
  ]) {
    assert.ok(api.includes(parameter), `missing ${parameter}`);
  }

  assert.doesNotMatch(api, /action:/);
  assert.doesNotMatch(api, /actor_id:/);
});

test("datetime-local filters are converted to aware ISO timestamps", () => {
  const api = read("src/lib/admin-audit/api.ts");

  assert.match(api, /new Date\(value\)\.toISOString\(\)/);
  assert.match(api, /awareDateTime/);
});

test("Audit Events presents complete backend traceability fields", () => {
  const page = read("src/app/(protected)/admin/audit/page.tsx");

  for (const field of [
    "actor_type",
    "actor_id",
    "entity_type",
    "entity_id",
    "source_revision",
    "target_revision",
    "request_id",
    "correlation_id",
    "reason",
    "before_json",
    "after_json",
    "ip_address",
    "user_agent",
    "created_at",
  ]) {
    assert.ok(page.includes(field), `missing ${field}`);
  }
});

test("Audit Events is read-only and append-only in the frontend", () => {
  const combined = [
    read("src/lib/admin-audit/api.ts"),
    read("src/app/(protected)/admin/audit/page.tsx"),
  ].join("\n");

  assert.match(combined, /Read-only append-only traceability/);
  assert.doesNotMatch(combined, /method:\s*"(POST|PATCH|DELETE)"/);
  assert.doesNotMatch(combined, /updateAudit|deleteAudit|createAudit/);
});

test("Audit Events remains permission-aware", () => {
  const page = read("src/app/(protected)/admin/audit/page.tsx");

  assert.match(page, /audit:read/);
  assert.match(page, /global_permissions/);
  assert.match(page, /No audit access/);
});

test("Audit Events validates entity UUID and date range before querying", () => {
  const page = read("src/app/(protected)/admin/audit/page.tsx");

  assert.match(page, /UUID_PATTERN/);
  assert.match(page, /Entity ID must be a valid UUID/);
  assert.match(page, /From date\/time must be before To date\/time/);
});

test("Audit Events contains no regulatory calculation or decision path", () => {
  const combined = [
    read("src/lib/admin-audit/api.ts"),
    read("src/app/(protected)/admin/audit/page.tsx"),
  ].join("\n");

  assert.doesNotMatch(
    combined,
    /maximum permissible error|calculateMpe|compliance_outcome\s*=|OpenAI|Groq|LLM/i,
  );
});
