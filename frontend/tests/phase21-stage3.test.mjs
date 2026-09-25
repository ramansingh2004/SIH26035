import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Phase 21 Stage 3 uses canonical append-only history endpoints", () => {
  const api = read("src/lib/history/api.ts");
  assert.match(api, /test-sessions\/\$\{sessionId\}\/revisions/);
  assert.match(api, /test-sessions\/\$\{sessionId\}\/reviews/);
  assert.match(api, /test-sessions\/\$\{sessionId\}\/corrections/);
  assert.match(api, /instruments\/\$\{instrumentId\}\/history/);
});

test("evaluation history preserves separate status axes and links session revisions", () => {
  const panel = read(
    "src/components/evaluations/evaluation-history-panel.tsx",
  );
  assert.match(panel, /<StatusAxes/);
  assert.match(panel, /regulatory_revision/);
  assert.match(panel, /\/evaluations\/\$\{revision\.id\}/);
  assert.match(panel, /approval:read/);
});

test("instrument history exposes evaluation and report traceability", () => {
  const panel = read(
    "src/components/master-data/instrument-history-panel.tsx",
  );
  assert.match(panel, /retest_count/);
  assert.match(panel, /\/evaluations\/\$\{item\.session_id\}/);
  assert.match(panel, /\/reports\/\$\{item\.report_id\}/);
  assert.match(panel, /report_status/);
});

test("Stage 3 remains read-only and performs no frontend compliance calculation", () => {
  const api = read("src/lib/history/api.ts");
  assert.doesNotMatch(api, /method:\s*"(POST|PATCH|DELETE)"/);
  const combined =
    read("src/components/evaluations/evaluation-history-panel.tsx") +
    read("src/components/master-data/instrument-history-panel.tsx");
  assert.doesNotMatch(combined, /\bMPE\b|acceptance[_ ]limit|calculateCompliance/i);
});
