import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("phase26 stage6 exposes full 17-section demo API", () => {
  const api = read("src/lib/evaluations/api.ts");
  assert.match(api, /demo-complete-evaluation/);
  assert.match(api, /completeFullDemoEvaluation/);
});

test("phase26 stage6 evaluation workspace exposes guarded full-demo action", () => {
  const page = read(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );
  assert.match(page, /SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3/);
  assert.match(page, /Complete all 17 synthetic demo sections/);
  assert.match(page, /23\s+typed\s+evaluator\s+runs/);
  assert.match(page, /Sections 16 and 17/);
  assert.match(page, /does not submit for review or approve/);
});
