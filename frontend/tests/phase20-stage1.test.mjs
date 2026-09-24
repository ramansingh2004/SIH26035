import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 20 Stage 1 exposes evaluation registry and workspace routes", async () => {
  for (const path of [
    "src/app/(protected)/evaluations/page.tsx",
    "src/app/(protected)/evaluations/new/page.tsx",
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
    "src/app/(protected)/evaluations/[sessionId]/sections/[sectionNumber]/page.tsx",
  ]) {
    await access(new URL(`../${path}`, import.meta.url));
  }

  const sidebar = await source("src/components/app-shell/sidebar.tsx");
  assert.match(sidebar, /href:\s*"\/evaluations"/);
  assert.match(sidebar, /label:\s*"Evaluations"[\s\S]*?implemented:\s*true/);
});

test("evaluation UI preserves workflow evaluation and outcome as separate axes", async () => {
  const axes = await source("src/components/evaluations/status-axes.tsx");
  assert.match(axes, /Workflow/);
  assert.match(axes, /Evaluation/);
  assert.match(axes, /Outcome/);

  const types = await source("src/lib/evaluations/types.ts");
  assert.match(types, /workflow_status:\s*WorkflowStatus/);
  assert.match(types, /evaluation_status:\s*EvaluationStatus/);
  assert.match(types, /compliance_outcome:\s*ComplianceOutcome/);
});

test("session setup uses backend snapshots and applicability endpoints", async () => {
  const api = await source("src/lib/evaluations/api.ts");
  const workspace = await source(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );

  assert.match(api, /\/api\/v1\/test-sessions\/\$\{id\}\/configure/);
  assert.match(api, /\/api\/v1\/test-sessions\/\$\{id\}\/applicability/);
  assert.match(
    api,
    /\/api\/v1\/test-sessions\/\$\{id\}\/confirm-applicability/,
  );
  assert.match(api, /\/api\/v1\/test-sessions\/\$\{id\}\/start-testing/);
  assert.match(workspace, /detail\.data\.item\.instrument_snapshot/);
});

test("optional applicability identity is never reconstructed in React", async () => {
  const applicability = await source(
    "src/components/evaluations/applicability-panel.tsx",
  );

  assert.match(applicability, /Election identity unavailable/);
  assert.match(applicability, /will not recreate canonical regulatory/);
  assert.doesNotMatch(
    applicability,
    /canonical_bytes|crypto\.subtle|JSON\.stringify.*slot/,
  );
});

test("412 source conflicts are surfaced rather than overwritten", async () => {
  const workspace = await source(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );
  const applicability = await source(
    "src/components/evaluations/applicability-panel.tsx",
  );

  for (const content of [workspace, applicability]) {
    assert.match(content, /VERSION_CONFLICT/);
    assert.match(content, /412/);
  }
  assert.match(workspace, /will not overwrite|never overwritten/i);
});

test("Phase 20 Stage 1 provides no universal JSON editor or frontend compliance calculation", async () => {
  const combined = [
    await source("src/app/(protected)/evaluations/[sessionId]/page.tsx"),
    await source(
      "src/app/(protected)/evaluations/[sessionId]/sections/[sectionNumber]/page.tsx",
    ),
    await source("src/components/evaluations/applicability-panel.tsx"),
  ].join("\n");

  assert.doesNotMatch(combined, /JSON editor|textarea[^>]*procedure_context/i);
  assert.doesNotMatch(
    combined,
    /maximum permissible error|calculateMpe|mpe\s*=|compliance_outcome\s*=/i,
  );
});
