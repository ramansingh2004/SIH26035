import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const repo = path.resolve(root, "..");

function readFrontend(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

function readRepo(relative) {
  return fs.readFileSync(path.join(repo, relative), "utf8");
}

test("Phase 24 final acceptance documents the complete judge walkthrough", () => {
  const doc = readRepo("PHASE24_ACCEPTANCE.md");
  for (const value of [
    "SIH26035-DEMO-NOMINAL",
    "SIH26035-DEMO-ADVERSE",
    "SIH26035-DEMO-POSITIVE",
    "SIH26035-DEMO-NEGATIVE",
    "Guided onboarding",
    "17-section",
    "unofficial PDF preview",
    "append-only traceability",
  ]) {
    assert.ok(doc.includes(value), `missing walkthrough item: ${value}`);
  }
});

test("Phase 24 keeps the three status axes semantically separate", () => {
  const guide = readFrontend(
    "src/components/polish/guided-workflow.tsx",
  );
  const progress = readFrontend(
    "src/components/polish/evaluation-progress-overview.tsx",
  );

  assert.match(guide, /Workflow = lifecycle/);
  assert.match(guide, /Evaluation = readiness\/completeness/);
  assert.match(guide, /Outcome = deterministic result/);
  assert.match(progress, /not a compliance score/);
});

test("Phase 24 result explanation remains downstream of persisted backend facts", () => {
  const result = readFrontend(
    "src/components/evaluations/result-panel.tsx",
  );

  for (const field of [
    "calculations_json",
    "acceptance_limits_json",
    "failed_conditions_json",
    "rule_references_json",
    "unresolved_rule_ids",
    "input_hash",
    "result_hash",
    "ruleset_configuration_hash",
  ]) {
    assert.ok(result.includes(field), `missing persisted result field: ${field}`);
  }

  assert.match(result, /No browser calculation/);
  assert.doesNotMatch(
    result,
    /calculateMpe|maximum permissible error\s*=|mpe\s*=|compliance_outcome\s*=/i,
  );
});

test("Phase 24 report polish preserves preview versus official separation", () => {
  const panel = readFrontend(
    "src/components/reports/report-session-panel.tsx",
  );

  assert.match(panel, /Preview files are unofficial/);
  assert.match(panel, /Official generation gate/);
  assert.match(panel, /workflow_status === "APPROVED"/);
  assert.match(panel, /evaluation_status === "COMPLETE"/);
  assert.match(panel, /COMPLIANT/);
  assert.match(panel, /NONCOMPLIANT/);
});

test("Phase 24 traceability still presents append-only revision and review history", () => {
  const history = readFrontend(
    "src/components/evaluations/evaluation-history-panel.tsx",
  );

  assert.match(history, /Append-only traceability/);
  assert.match(history, /Session revisions/);
  assert.match(history, /Review events/);
  assert.match(history, /Correction requests/);
  assert.match(history, /Earlier states remain preserved/);
});

test("Phase 24 adds no AI decision path", () => {
  const files = [
    "src/components/polish/guided-workflow.tsx",
    "src/components/polish/evaluation-progress-overview.tsx",
    "src/components/evaluations/result-panel.tsx",
    "src/components/reports/report-session-panel.tsx",
    "src/components/evaluations/evaluation-history-panel.tsx",
  ];
  const combined = files.map(readFrontend).join("\n");

  assert.doesNotMatch(combined, /OpenAI|Groq|LLM|prompt|chat completion/i);
});
