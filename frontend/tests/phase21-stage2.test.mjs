import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relative) =>
  fs.readFileSync(path.join(root, relative), "utf8");

test("Phase 21 Stage 2 uses canonical report lifecycle routes", () => {
  const api = read("src/lib/reports/api.ts");
  for (const value of [
    "/report-previews",
    "/reports",
    "/regenerate",
    "/issue",
    "/revisions",
    "/history",
  ]) {
    assert.ok(api.includes(value));
  }
});

test("official generation is gated on approved complete determined evaluation", () => {
  const panel = read("src/components/reports/report-session-panel.tsx");
  assert.ok(panel.includes('workflow_status === "APPROVED"'));
  assert.ok(panel.includes('evaluation_status === "COMPLETE"'));
  assert.ok(panel.includes('"COMPLIANT"'));
  assert.ok(panel.includes('"NONCOMPLIANT"'));
});

test("issue requires reserved issuer and current UTC planned date", () => {
  const page = read("src/app/(protected)/reports/[reportId]/page.tsx");
  assert.ok(page.includes("intended_issuer_id === user?.id"));
  assert.ok(page.includes("planned_issue_date === utcDate()"));
});

test("report revision candidates come from approved complete instrument history", () => {
  const page = read("src/app/(protected)/reports/[reportId]/page.tsx");
  assert.ok(page.includes("instrumentHistory"));
  assert.ok(page.includes('workflow_status === "APPROVED"'));
  assert.ok(page.includes('evaluation_status === "COMPLETE"'));
  assert.ok(page.includes("!item.report_id"));
});
