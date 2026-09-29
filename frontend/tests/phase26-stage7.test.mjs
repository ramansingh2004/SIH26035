import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("phase26 stage7 exposes a distinct full demo report preview API", () => {
  const api = read("src/lib/reports/api.ts");
  assert.match(api, /full-demo-report-previews/);
  assert.match(api, /createFullDemoReport/);
});

test("phase26 stage7 completed V3 UI requests the full evidence-rich report", () => {
  const panel = read("src/components/reports/report-session-panel.tsx");
  assert.match(panel, /SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3/);
  assert.match(panel, /Generate complete 17-section demo report/);
  assert.match(panel, /23 typed runs/);
  assert.match(panel, /60 unique synthetic evidence files/);
  assert.match(panel, /85 immutable evidence links/);
  assert.match(panel, /NOT AN OFFICIAL OIML CERTIFICATE/);
});
