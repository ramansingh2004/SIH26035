import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("result explanation uses only persisted backend result fields", () => {
  const panel = read("src/components/evaluations/result-panel.tsx");
  assert.match(panel, /How to read this result/);
  assert.match(panel, /calculations_json\.length/);
  assert.match(panel, /acceptance_limits_json\.length/);
  assert.match(panel, /failed_conditions_json\.length/);
  assert.match(panel, /synthetic_fixture/);
  assert.match(panel, /No browser calculation/);
  assert.doesNotMatch(
    panel,
    /calculateMpe|maximum permissible error\s*=|mpe\s*=|compliance_outcome\s*=/i,
  );
});

test("result trace labels persisted evidence without truncating it", () => {
  const panel = read("src/components/evaluations/result-panel.tsx");
  assert.match(panel, /Persisted failed checks/);
  assert.match(panel, /Acceptance limits \(persisted criteria\)/);
  assert.match(panel, /Calculation trace \(persisted\)/);
  assert.match(panel, /Rule references \(persisted\)/);
  assert.doesNotMatch(panel, /\.slice\(0,\s*\d+\)/);
});

test("preview panel explains unofficial downloads and gate reason", () => {
  const panel = read("src/components/reports/report-session-panel.tsx");
  assert.match(panel, /Preview files are unofficial/);
  assert.match(panel, /PDF/);
  assert.match(panel, /DOCX/);
  assert.match(panel, /expires_at/);
  assert.match(panel, /Official generation is blocked because/);
  assert.match(panel, /Generation\s+does not issue/);
});

test("issued report detail explains immutable downloadable artifacts", () => {
  const page = read("src/app/(protected)/reports/[reportId]/page.tsx");
  assert.match(page, /Issued report files/);
  assert.match(page, /same immutable selected generation/);
  assert.match(page, /Download \{format\.toUpperCase\(\)\}/);
});

test("evaluation history exposes an append-only traceability summary", () => {
  const panel = read(
    "src/components/evaluations/evaluation-history-panel.tsx",
  );
  assert.match(panel, /Append-only traceability/);
  assert.match(panel, /Session revisions/);
  assert.match(panel, /Review events/);
  assert.match(panel, /Correction requests/);
  assert.match(panel, /Earlier states remain preserved/);
});

test("Stage 2 remains explanatory presentation only", () => {
  const combined = [
    read("src/components/evaluations/result-panel.tsx"),
    read("src/components/reports/report-session-panel.tsx"),
    read("src/components/evaluations/evaluation-history-panel.tsx"),
  ].join("\\n");

  assert.doesNotMatch(combined, /OpenAI|Groq|LLM|prompt/i);
});
