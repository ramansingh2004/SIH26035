import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("phase26 stage8 judge flow exposes the Stage6 completion action", () => {
  const page = read(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );
  assert.match(page, /Complete all 17 synthetic demo sections/);
  assert.match(page, /SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3/);
});

test("phase26 stage8 judge flow exposes the Stage7 full report action", () => {
  const panel = read(
    "src/components/reports/report-session-panel.tsx",
  );
  assert.match(panel, /Generate complete 17-section demo report/);
  assert.match(panel, /NOT AN OFFICIAL OIML CERTIFICATE/);
  assert.match(panel, /85 immutable evidence links/);
});
