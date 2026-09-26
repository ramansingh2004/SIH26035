import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Admin Laboratories navigation is enabled while Audit Events remains upcoming", () => {
  const sidebar = read("src/components/app-shell/sidebar.tsx");
  const users = sidebar.indexOf('href: "/admin/users"');
  const labs = sidebar.indexOf('href: "/admin/laboratories"');
  const audit = sidebar.indexOf('href: "/admin/audit"');

  assert.match(sidebar.slice(users, users + 130), /implemented:\s*true/);
  assert.match(sidebar.slice(labs, labs + 150), /implemented:\s*true/);
  assert.match(sidebar.slice(audit, audit + 130), /implemented:\s*false/);
});

test("Admin Laboratories uses the existing administration API contracts", () => {
  const api = read("src/lib/admin-laboratories/api.ts");

  assert.match(api, /\/api\/v1\/laboratories/);
  assert.match(api, /method:\s*"POST"/);
  assert.match(api, /method:\s*"PATCH"/);
  assert.match(api, /etag/);
});

test("laboratory creation is global-admin controlled and preserves backend schema", () => {
  const page = read(
    "src/app/(protected)/admin/laboratories/new/page.tsx",
  );

  assert.match(page, /laboratory:create/);
  assert.match(page, /global_permissions/);
  assert.match(page, /accreditation_no/);
  assert.match(page, /timezone/);
  assert.match(page, /\^\[A-Za-z0-9_-\]\+\$/);
});

test("laboratory detail exposes administrative identity without regulatory decisions", () => {
  const page = read(
    "src/app/(protected)/admin/laboratories/[laboratoryId]/page.tsx",
  );

  assert.match(page, /Accreditation number/);
  assert.match(page, /Record version/);
  assert.match(page, /Logo attachment/);
  assert.match(page, /Administrative scope, not regulatory outcome/);
});

test("laboratory editing preserves immutable code and optimistic concurrency", () => {
  const page = read(
    "src/app/(protected)/admin/laboratories/[laboratoryId]/edit/page.tsx",
  );

  assert.match(page, /readOnly/);
  assert.match(page, /immutable after creation/);
  assert.match(page, /backend ETag/);
  assert.match(page, /updateLaboratory/);
});

test("laboratory active state explains its authorization consequence", () => {
  const page = read(
    "src/app/(protected)/admin/laboratories/[laboratoryId]/edit/page.tsx",
  );

  assert.match(page, /Inactive/);
  assert.match(page, /laboratory-scoped grants/);
  assert.match(page, /historical evaluation and report records are not rewritten/);
});

test("Admin Laboratories remains permission-aware and contains no compliance calculation", () => {
  const combined = [
    read("src/app/(protected)/admin/laboratories/page.tsx"),
    read("src/app/(protected)/admin/laboratories/new/page.tsx"),
    read("src/app/(protected)/admin/laboratories/[laboratoryId]/page.tsx"),
    read(
      "src/app/(protected)/admin/laboratories/[laboratoryId]/edit/page.tsx",
    ),
    read("src/lib/admin-laboratories/api.ts"),
  ].join("\n");

  for (const permission of [
    "laboratory:read",
    "laboratory:create",
    "laboratory:update",
  ]) {
    assert.ok(combined.includes(permission));
  }

  assert.doesNotMatch(
    combined,
    /maximum permissible error|calculateMpe|compliance_outcome\s*=|OpenAI|Groq|LLM/i,
  );
});
