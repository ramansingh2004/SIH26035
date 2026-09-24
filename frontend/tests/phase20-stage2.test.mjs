import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Phase 20 Stage 2 adds a selected-run workspace", async () => {
  await access(
    new URL(
      "../src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
      import.meta.url,
    ),
  );

  const section = await source(
    "src/app/(protected)/evaluations/[sessionId]/sections/[sectionNumber]/page.tsx",
  );
  assert.match(section, /Open selected run/);
  assert.match(section, /\/runs\/\$\{requirement\.selected_run_id\}/);
});

test("run API uses dedicated procedure observation environment equipment and evaluation endpoints", async () => {
  const api = await source("src/lib/evaluations/run-api.ts");

  for (const fragment of [
    "/procedure-context",
    "/observations",
    "/environment",
    "/equipment/",
    "/evaluate",
    "/complete",
    "/start",
  ]) {
    assert.match(api, new RegExp(fragment.replaceAll("/", "\\/")));
  }
});

test("typed schemas cover non-disturbance implemented evaluator families", async () => {
  const schemas = await source("src/lib/evaluations/test-schemas.ts");

  for (const code of [
    "WEIGHING_PERFORMANCE",
    "TEMPERATURE_ZERO",
    "ECCENTRICITY",
    "REPEATABILITY",
    "DISCRIMINATION",
    "SENSITIVITY",
    "ZERO_RETURN",
    "CREEP",
    "STABILITY_EQUILIBRIUM",
    "TILTING",
    "TARE",
    "WARM_UP",
    "VOLTAGE_VARIATION",
    "DAMP_HEAT",
    "SPAN_STABILITY",
    "ENDURANCE",
  ]) {
    assert.match(schemas, new RegExp(`${code}:`));
  }
});

test("metrological observation fields remain strings and no frontend MPE logic exists", async () => {
  const schemas = await source("src/lib/evaluations/test-schemas.ts");
  const manager = await source(
    "src/components/evaluations/observation-manager.tsx",
  );

  assert.doesNotMatch(schemas, /parseFloat|Number\(/);
  assert.doesNotMatch(
    manager,
    /parseFloat|calculateMpe|maximum permissible error|mpe\s*=/i,
  );
  assert.match(manager, /decimal strings/);
});

test("procedure context leaves server-owned associations empty", async () => {
  const schemas = await source("src/lib/evaluations/test-schemas.ts");

  assert.match(schemas, /environment:\s*\[\]/);
  assert.match(schemas, /equipment:\s*\[\]/);
  assert.match(schemas, /evidence_hashes:\s*\[\]/);
});

test("child source mutations refetch run version instead of deriving a new run ETag", async () => {
  const page = await source(
    "src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
  );

  assert.match(page, /refreshRunSources/);
  assert.match(page, /\["test-run", runId\]/);
  assert.doesNotMatch(page, /run\.lock_version\s*\+\s*1/);
});

test("environment and equipment use dedicated traceability controls", async () => {
  const environment = await source(
    "src/components/evaluations/environment-manager.tsx",
  );
  const equipment = await source(
    "src/components/evaluations/equipment-manager.tsx",
  );
  const page = await source(
    "src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
  );

  assert.match(
    environment,
    /Record at least one measured environmental quantity/,
  );
  assert.match(equipment, /immutable calibration snapshot/);
  assert.match(page, /uploadEvidence/);
  assert.match(page, /purpose:\s*"calibration"/);
});

test("Stage 2 does not expose a free-form procedure payload editor", async () => {
  const procedure = await source(
    "src/components/evaluations/procedure-form.tsx",
  );
  const field = await source("src/components/evaluations/typed-field.tsx");

  assert.doesNotMatch(procedure, /JSON\.stringify|JSON\.parse/);
  assert.doesNotMatch(field, /application\/json/);
  assert.match(field, /field\.kind === "positions"/);
  assert.match(field, /field\.kind === "tare-scenarios"/);
  assert.match(field, /Add position/);
  assert.match(field, /Add scenario/);
});
