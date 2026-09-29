import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("phase26 stage5 exposes guarded Section17 demo completion API", () => {
  const api = read("src/lib/evaluations/special-api.ts");
  assert.match(api, /checklist\/demo-complete/);
  assert.match(api, /completeChecklistDemo/);
});

test("phase26 stage5 checklist workspace exposes one-click V3 demo action", () => {
  const workspace = read(
    "src/components/evaluations/checklist-workspace.tsx",
  );
  assert.match(
    workspace,
    /SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3/,
  );
  assert.match(
    workspace,
    /Populate & complete synthetic Section 17/,
  );
  assert.match(workspace, /Complete Section 16 first/);
  assert.match(workspace, /Synthetic demo only/);
});
