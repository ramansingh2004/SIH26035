import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 19 Stage 1 exposes real master-data navigation", async () => {
  const sidebar = await source("src/components/app-shell/sidebar.tsx");
  for (const path of ["/manufacturers", "/instruments", "/equipment"]) {
    assert.match(sidebar, new RegExp(path.replace("/", "\\/")));
  }
  assert.match(sidebar, /implemented:\s*true/);
});

test("instrument decimal measurements remain strings in frontend API types", async () => {
  const types = await source("src/lib/master-data/types.ts");
  assert.match(types, /max_capacity_g:\s*string/);
  assert.match(types, /scale_interval_d_g:\s*string/);
  assert.match(types, /verification_interval_e_g:\s*string/);

  const form = await source("src/app/(protected)/instruments/new/page.tsx");
  assert.doesNotMatch(form, /parseFloat|Number\(/);
  assert.match(form, /inputMode="decimal"/);
});

test("unknown applicability is explicit and regulatory validation is surfaced", async () => {
  const form = await source("src/app/(protected)/instruments/new/page.tsx");
  assert.match(form, /Unknown \/ not established/);
  assert.match(form, /RegulatoryBlocker/);
  assert.match(form, /validateInstrumentConfiguration/);

  const api = await source("src/lib/master-data/api.ts");
  assert.match(api, /\/api\/v1\/instruments\/validate-configuration/);
});

test("master-data creates use selected lab scope and idempotency keys", async () => {
  const api = await source("src/lib/master-data/api.ts");
  assert.match(api, /createIdempotencyKey/);
  assert.match(api, /Idempotency/);

  const manufacturerForm = await source(
    "src/app/(protected)/manufacturers/new/page.tsx",
  );
  const instrumentForm = await source(
    "src/app/(protected)/instruments/new/page.tsx",
  );
  const equipmentForm = await source(
    "src/app/(protected)/equipment/new/page.tsx",
  );

  for (const content of [manufacturerForm, instrumentForm, equipmentForm]) {
    assert.match(content, /selectedLaboratoryId/);
  }
});

test("Phase 19 Stage 1 uses backend list/detail endpoints", async () => {
  const api = await source("src/lib/master-data/api.ts");
  assert.match(api, /\/api\/v1\/manufacturers/);
  assert.match(api, /\/api\/v1\/instruments/);
  assert.match(api, /\/api\/v1\/test-equipment/);
});
