import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 21 Stage 1 exposes technical review and final approval routes", async () => {
  for (const path of [
    "src/app/(protected)/reviews/page.tsx",
    "src/app/(protected)/reviews/[sessionId]/page.tsx",
    "src/app/(protected)/approvals/page.tsx",
    "src/app/(protected)/approvals/[sessionId]/page.tsx",
  ]) {
    await access(new URL(`../${path}`, import.meta.url));
  }

  const sidebar = await source("src/components/app-shell/sidebar.tsx");
  assert.match(sidebar, /href:\s*"\/reviews"[\s\S]*?implemented:\s*true/);
  assert.match(sidebar, /href:\s*"\/approvals"[\s\S]*?implemented:\s*true/);
});

test("review API uses backend governance endpoints and final approval idempotency", async () => {
  const api = await source("src/lib/review/api.ts");
  for (const fragment of [
    "/submit-for-review",
    "/reviews",
    "/return-for-correction",
    "/corrections/",
    "/approve",
    "/reject",
  ]) {
    assert.match(api, new RegExp(fragment.replaceAll("/", "\\/")));
  }
  assert.match(api, /createIdempotencyKey\(\)/);
});

test("technical review references current regulatory revision", async () => {
  const review = await source("src/components/review/review-case.tsx");
  assert.match(review, /reviewed_regulatory_revision/);
  assert.match(review, /detail\.data\.item\.regulatory_revision/);
});

test("correction scope is generated from real entities and a fixed field allow-list", async () => {
  const targets = await source("src/lib/review/correction-targets.ts");
  const builder = await source(
    "src/components/review/correction-scope-builder.tsx",
  );

  assert.match(targets, /test_sessions/);
  assert.match(targets, /session_test_requirements/);
  assert.match(targets, /test_runs/);
  assert.match(targets, /construction_items/);
  assert.match(targets, /checklist_responses/);
  assert.doesNotMatch(builder, /entity_type.*<input|field_paths.*<input/i);
});

test("evaluation workspace includes review submission and correction resolution", async () => {
  const page = await source(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );
  const lifecycle = await source(
    "src/components/review/review-lifecycle-panel.tsx",
  );

  assert.match(page, /ReviewLifecyclePanel/);
  assert.match(lifecycle, /Submit for technical review/);
  assert.match(lifecycle, /Resolve correction/);
  assert.match(lifecycle, /session\.regulatory_revision > returnRevision/);
});

test("final approval explicitly remains separate from compliance outcome", async () => {
  const review = await source("src/components/review/review-case.tsx");
  assert.match(review, /Approval and compliance are separate/);
  assert.match(review, /COMPLETE \+ NONCOMPLIANT/);
  assert.doesNotMatch(review, /compliance_outcome\s*=/);
});
