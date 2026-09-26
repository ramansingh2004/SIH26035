import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("topbar exposes Account & Security for every authenticated user", () => {
  const topbar = read("src/components/app-shell/topbar.tsx");

  assert.match(topbar, /href="\/account"/);
  assert.match(topbar, /Open account and security settings/);
  assert.match(topbar, /Sign out/);
});

test("account API uses canonical self-service authentication endpoints", () => {
  const api = read("src/lib/account/api.ts");

  for (const route of [
    "/api/v1/auth/me",
    "/api/v1/auth/sessions",
    "/api/v1/auth/password",
  ]) {
    assert.ok(api.includes(route), `missing ${route}`);
  }

  assert.match(api, /method:\s*"DELETE"/);
  assert.match(api, /etag/);
  assert.match(api, /current_password/);
  assert.match(api, /new_password/);
});

test("logout-all clears authenticated frontend state only after backend success", () => {
  const auth = read("src/lib/auth/auth-context.tsx");

  assert.match(auth, /\/api\/v1\/auth\/logout-all/);
  assert.match(auth, /clearAuthentication/);
  assert.match(auth, /await apiRequest<void>\("\/api\/v1\/auth\/logout-all"/);
  assert.doesNotMatch(auth, /localStorage\.setItem\([^)]*access/i);
});

test("password change validates backend password length and confirmation", () => {
  const page = read("src/app/(protected)/account/page.tsx");

  assert.match(page, /newPassword\.length < 12/);
  assert.match(page, /newPassword\.length > 128/);
  assert.match(page, /newPassword !== confirmPassword/);
  assert.match(page, /Change password and sign out/);
});

test("session families expose backend metadata and optimistic revocation", () => {
  const page = read("src/app/(protected)/account/page.tsx");
  const api = read("src/lib/account/api.ts");

  for (const field of [
    "family_id",
    "created_at",
    "expires_at",
    "family_expires_at",
    "client_ip",
    "user_agent",
    "is_active",
  ]) {
    assert.ok(page.includes(field), `missing ${field}`);
  }

  assert.match(api, /revokeAccountSession/);
  assert.match(api, /etag/);
  assert.match(page, /current API does not identify which family belongs/);
});

test("account identity remains read-only rather than inventing self-profile mutation", () => {
  const page = read("src/app/(protected)/account/page.tsx");
  const api = read("src/lib/account/api.ts");

  assert.match(page, /account identity is read-only here/i);
  assert.match(page, /Administration → Users/);
  assert.doesNotMatch(api, /method:\s*"PATCH"/);
  assert.doesNotMatch(api, /updateProfile|updateAccountIdentity/);
});

test("authorization summary preserves global and laboratory scopes", () => {
  const page = read("src/app/(protected)/account/page.tsx");

  assert.match(page, /global_roles/);
  assert.match(page, /global_permissions/);
  assert.match(page, /user\.laboratories/);
  assert.match(page, /grant\.roles/);
  assert.match(page, /grant\.permissions/);
  assert.match(
    page,
    /Global ADMIN status does not automatically create\s+laboratory operational or regulatory roles/,
  );
});

test("account security adds no compliance or regulatory decision logic", () => {
  const combined = [
    read("src/lib/account/api.ts"),
    read("src/app/(protected)/account/page.tsx"),
    read("src/lib/auth/auth-context.tsx"),
  ].join("\n");

  assert.doesNotMatch(
    combined,
    /maximum permissible error|calculateMpe|compliance_outcome\s*=|OpenAI|Groq|LLM/i,
  );
});

