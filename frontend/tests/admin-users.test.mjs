import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Admin Users navigation remains enabled as later admin modules are added", () => {
  const sidebar = read("src/components/app-shell/sidebar.tsx");
  const users = sidebar.indexOf('href: "/admin/users"');
  const labs = sidebar.indexOf('href: "/admin/laboratories"');
  const audit = sidebar.indexOf('href: "/admin/audit"');

  assert.ok(users >= 0);
  assert.match(sidebar.slice(users, users + 130), /implemented:\s*true/);
  assert.match(sidebar.slice(labs, labs + 150), /implemented:\s*true/);
  assert.match(sidebar.slice(audit, audit + 130), /implemented:\s*false/);
});

test("Admin Users API uses the existing administration backend contracts", () => {
  const api = read("src/lib/admin-users/api.ts");

  for (const route of [
    "/api/v1/users",
    "/reset-password",
    "/role-assignments",
    "/api/v1/roles",
    "/api/v1/laboratories",
  ]) {
    assert.ok(api.includes(route), `missing admin route ${route}`);
  }

  assert.match(api, /If-Match|etag/);
  assert.match(api, /lockVersionEtag/);
});

test("user provisioning remains controlled rather than public registration", () => {
  const list = read("src/app/(protected)/admin/users/page.tsx");
  const create = read("src/app/(protected)/admin/users/new/page.tsx");

  assert.match(list, /does not expose public self-registration/);
  assert.match(create, /This is not public registration/);
  assert.match(create, /initial_assignment/);
  assert.doesNotMatch(create, /\/register/);
});

test("new user form preserves global versus laboratory role constraints", () => {
  const create = read("src/app/(protected)/admin/users/new/page.tsx");

  assert.match(create, /Only ADMIN can be assigned globally/);
  assert.match(create, /scope_type/);
  assert.match(create, /laboratory_id/);
  assert.match(create, /user:manage_roles/);
  assert.match(create, /min\(12/);
});

test("user detail supports identity, password reset, roles and role revocation", () => {
  const detail = read(
    "src/app/(protected)/admin/users/[userId]/page.tsx",
  );

  assert.match(detail, /updateUser/);
  assert.match(detail, /resetUserPassword/);
  assert.match(detail, /grantAssignment/);
  assert.match(detail, /revokeAssignment/);
  assert.match(detail, /Reason for revoking this role assignment/);
  assert.match(detail, /optimistic concurrency/i);
});

test("Admin Users UI remains permission-aware", () => {
  const list = read("src/app/(protected)/admin/users/page.tsx");
  const detail = read(
    "src/app/(protected)/admin/users/[userId]/page.tsx",
  );

  for (const permission of [
    "user:read",
    "user:create",
  ]) {
    assert.ok(list.includes(permission));
  }

  for (const permission of [
    "user:read",
    "user:update",
    "user:deactivate",
    "user:manage_roles",
  ]) {
    assert.ok(detail.includes(permission));
  }
});

test("Admin Users does not add regulatory calculation logic", () => {
  const combined = [
    read("src/lib/admin-users/api.ts"),
    read("src/app/(protected)/admin/users/page.tsx"),
    read("src/app/(protected)/admin/users/new/page.tsx"),
    read("src/app/(protected)/admin/users/[userId]/page.tsx"),
  ].join("\n");

  assert.doesNotMatch(
    combined,
    /maximum permissible error|calculateMpe|compliance_outcome\s*=|OpenAI|Groq|LLM/i,
  );
});
