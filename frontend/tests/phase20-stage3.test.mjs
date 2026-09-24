import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Stage 3 adds all seven typed disturbance families", async () => {
  const disturbance = await source(
    "src/lib/evaluations/disturbance-schemas.ts",
  );
  for (const code of [
    "DISTURBANCE_VOLTAGE_DIP",
    "DISTURBANCE_BURST",
    "DISTURBANCE_SURGE",
    "DISTURBANCE_ESD",
    "DISTURBANCE_RADIATED_RF",
    "DISTURBANCE_CONDUCTED_RF",
    "DISTURBANCE_VEHICLE_SUPPLY",
  ]) {
    assert.match(disturbance, new RegExp(`${code}:`));
  }
  assert.match(disturbance, /severity_cases/);
  assert.match(disturbance, /DISTURBANCE_V1/);
});

test("disturbance severity capture is typed", async () => {
  const field = await source("src/components/evaluations/typed-field.tsx");
  assert.match(field, /field\.kind === "severity-cases"/);
  assert.match(field, /Severity ID/);
  assert.match(field, /Waveform reference/);
});

test("Stage 3 implements reasoned retests and selected-run history", async () => {
  const api = await source("src/lib/evaluations/run-api.ts");
  const panel = await source(
    "src/components/evaluations/run-history-panel.tsx",
  );
  assert.match(api, /\/history/);
  assert.match(api, /\/retests/);
  assert.match(api, /\/select-run/);
  assert.match(panel, /Retests preserve the original run/);
  assert.match(panel, /Selection reason/);
});

test("construction fields derive from pinned POLICY_JSON required keys", async () => {
  const types = await source("src/lib/evaluations/special-types.ts");
  const ui = await source(
    "src/components/evaluations/construction-workspace.tsx",
  );
  assert.match(types, /POLICY_JSON/);
  assert.match(types, /required_value_keys/);
  assert.match(ui, /policy\.required_value_keys/);
  assert.doesNotMatch(ui, /Add field|Add key|JSON editor/i);
});

test("construction and checklist use backend start and completion endpoints", async () => {
  const api = await source("src/lib/evaluations/special-api.ts");
  assert.match(api, /\/start-examination/);
  assert.match(api, /\/construction\/complete/);
  assert.match(api, /\/checklist\/complete/);
  assert.match(api, /\/construction\/items\//);
});

test("checklist does not offer N/A for required editable rows", async () => {
  const ui = await source("src/components/evaluations/checklist-workspace.tsx");
  assert.match(ui, /row\.applicability_status === "REQUIRED"/);
  assert.doesNotMatch(
    ui,
    /<option value="NOT_APPLICABLE">Not applicable<\/option>/,
  );
});

test("Sections 16 and 17 use specialized examination workspaces", async () => {
  const page = await source(
    "src/app/(protected)/evaluations/[sessionId]/sections/[sectionNumber]/page.tsx",
  );
  assert.match(page, /ConstructionWorkspace/);
  assert.match(page, /ChecklistWorkspace/);
  assert.match(page, /ExaminationStartGate/);
});

test("specialized evidence uses versioned child targets", async () => {
  const construction = await source(
    "src/components/evaluations/construction-workspace.tsx",
  );
  const checklist = await source(
    "src/components/evaluations/checklist-workspace.tsx",
  );
  assert.match(construction, /entityType="construction_items"/);
  assert.match(checklist, /entityType="checklist_responses"/);
  assert.match(construction, /etagFromVersion\(item\.lock_version\)/);
  assert.match(checklist, /etagFromVersion\(row\.lock_version\)/);
});

test("result trace is complete rather than truncated", async () => {
  const result = await source("src/components/evaluations/result-panel.tsx");
  assert.match(result, /Acceptance limits/);
  assert.match(result, /Calculation trace/);
  assert.match(result, /Rule references/);
  assert.doesNotMatch(result, /\.slice\(0,\s*12\)/);
});

test("Stage 3 still performs no frontend compliance or MPE calculation", async () => {
  const combined = [
    await source("src/lib/evaluations/disturbance-schemas.ts"),
    await source("src/components/evaluations/construction-workspace.tsx"),
    await source("src/components/evaluations/checklist-workspace.tsx"),
    await source("src/components/evaluations/run-history-panel.tsx"),
  ].join("\n");
  assert.doesNotMatch(
    combined,
    /calculateMpe|maximum permissible error|mpe\s*=|compliance_outcome\s*=/i,
  );
});
