import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const api = fs.readFileSync("src/lib/reports/api.ts", "utf8");
const panel = fs.readFileSync(
  "src/components/reports/report-session-panel.tsx",
  "utf8",
);

test("demo report API uses the isolated simulation endpoint", () => {
  assert.match(
    api,
    /\/api\/v1\/test-sessions\/\$\{sessionId\}\/report-simulations/,
  );
  assert.match(api, /SIMULATED-APPROVED-DEMO-/);
});

test("reporting UI clearly separates simulation from official generation", () => {
  assert.match(panel, /Generate simulated approved report/);
  assert.match(panel, /DEMONSTRATION ONLY/);
  assert.match(panel, /Generate official report/);
  assert.match(panel, /Official generation gate/);
});
