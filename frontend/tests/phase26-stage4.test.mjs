import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("phase26 stage4 exposes guarded Section16 demo completion API", () => {
  const api = read("src/lib/evaluations/special-api.ts");
  assert.match(api, /construction\/demo-complete/);
  assert.match(api, /completeConstructionDemo/);
});

test("phase26 stage4 construction workspace exposes one-click V3 demo action", () => {
  const workspace = read(
    "src/components/evaluations/construction-workspace.tsx",
  );
  assert.match(
    workspace,
    /SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3/,
  );
  assert.match(
    workspace,
    /Populate & complete synthetic Section 16/,
  );
  assert.match(workspace, /Synthetic demo only/);
});
