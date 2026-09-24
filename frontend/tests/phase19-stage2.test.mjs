import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 19 Stage 2 adds edit routes for all master-data roots", async () => {
  for (const path of [
    "src/app/(protected)/manufacturers/[id]/edit/page.tsx",
    "src/app/(protected)/instruments/[id]/edit/page.tsx",
    "src/app/(protected)/equipment/[id]/edit/page.tsx",
  ]) {
    await access(new URL(`../${path}`, import.meta.url));
  }
});

test("master-data mutations use optimistic ETags and archive reasons", async () => {
  const api = await source("src/lib/master-data/api.ts");
  assert.match(api, /method:\s*"PATCH"/);
  assert.match(api, /etag/);
  assert.match(api, /\/archive/);
  assert.match(api, /body:\s*\{\s*reason\s*\}/);
});

test("ranges and components use parent and child concurrency contracts", async () => {
  const api = await source("src/lib/master-data/api.ts");
  const types = await source("src/lib/master-data/types.ts");

  assert.match(api, /\/ranges/);
  assert.match(api, /\/components/);
  assert.match(api, /instrumentEtag/);
  assert.match(types, /etagFromVersion/);
  assert.match(types, /max_capacity_g:\s*string/);
  assert.match(types, /rated_capacity_g\?:\s*string/);
});

test("evidence UX hashes locally then uses presign PUT and complete", async () => {
  const evidence = await source("src/lib/evidence/api.ts");

  assert.match(evidence, /crypto\.subtle\.digest\("SHA-256"/);
  assert.match(evidence, /\/api\/v1\/attachments\/presign/);
  assert.match(evidence, /method:\s*presign\.data\.method/);
  assert.match(evidence, /\/api\/v1\/attachments\/complete/);
  assert.match(evidence, /content-length/);
});

test("master detail pages expose evidence without fabricating a target listing", async () => {
  const manufacturer = await source(
    "src/app/(protected)/manufacturers/[id]/page.tsx",
  );
  const instrument = await source(
    "src/app/(protected)/instruments/[id]/page.tsx",
  );
  const equipment = await source("src/app/(protected)/equipment/[id]/page.tsx");
  const uploader = await source(
    "src/components/evidence/evidence-uploader.tsx",
  );

  for (const page of [manufacturer, instrument, equipment]) {
    assert.match(page, /EvidenceUploader/);
  }
  assert.match(uploader, /no\s+target-scoped\s+evidence-list endpoint/i);
});

test("frontend still does not calculate OIML compliance", async () => {
  const files = [
    await source("src/components/master-data/range-manager.tsx"),
    await source("src/components/master-data/component-manager.tsx"),
    await source("src/app/(protected)/instruments/[id]/edit/page.tsx"),
  ].join("\n");

  assert.doesNotMatch(
    files,
    /maximum permissible error|MPE|compliance_outcome\s*=/i,
  );
  assert.doesNotMatch(files, /parseFloat/);
});
