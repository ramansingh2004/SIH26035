import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("laboratory scope displays backend name and code rather than UUID fragments", async () => {
  const topbar = await source("src/components/app-shell/topbar.tsx");

  assert.match(topbar, /laboratory\.name/);
  assert.match(topbar, /laboratory\.code/);
  assert.doesNotMatch(topbar, /laboratory_id\.slice/);
  assert.doesNotMatch(topbar, /Lab ·/);
});

test("laboratory metadata uses the scoped paginated backend endpoint", async () => {
  const query = await source("src/lib/laboratories/queries.ts");

  assert.match(query, /\/api\/v1\/laboratories/);
  assert.match(query, /page_size/);
  assert.match(query, /grantedLaboratoryIds/);
  assert.doesNotMatch(query, /\/laboratories\/\$\{/);
});

test("session restoration tolerates backend network unavailability", async () => {
  const client = await source("src/lib/api/client.ts");

  assert.match(client, /async function rawRefresh/);
  assert.match(client, /try\s*\{/);
  assert.match(client, /catch\s*\{/);
  assert.match(client, /setAccessToken\(null\)/);
  assert.match(client, /Unable to reach the SIH26035 API/);
});
