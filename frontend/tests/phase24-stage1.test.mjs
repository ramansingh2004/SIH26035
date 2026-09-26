import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Phase 24 Stage 1 adds permission-aware guided workflow", () => {
  const guide = read("src/components/polish/guided-workflow.tsx");
  for (const href of ["/dashboard", "/evaluations", "/reviews", "/reports"]) {
    assert.ok(guide.includes(`href: "${href}"`));
  }
  for (const permission of [
    "dashboard:read",
    "session:read",
    "approval:read",
    "report:read",
  ]) {
    assert.ok(guide.includes(permission));
  }
  assert.match(guide, /Three axes, three meanings/);
  assert.match(guide, /does not calculate/);
});

test("dashboard surfaces the guided onboarding without backend changes", () => {
  const page = read("src/app/(protected)/dashboard/page.tsx");
  assert.match(page, /GuidedWorkflow/);
});

test("evaluation progress derives presentation coverage only from persisted section states", () => {
  const progress = read(
    "src/components/polish/evaluation-progress-overview.tsx",
  );
  assert.match(progress, /NOT_APPLICABLE/);
  assert.match(progress, /evaluation_status === "COMPLETE"/);
  assert.match(progress, /Presentation progress only/);
  assert.match(progress, /not a compliance score/);
  assert.doesNotMatch(
    progress,
    /maximum permissible error|calculateMpe|mpe\s*=|compliance_outcome\s*=/i,
  );
});

test("evaluation workspace shows readiness overview next to canonical status axes", () => {
  const page = read(
    "src/app/(protected)/evaluations/[sessionId]/page.tsx",
  );
  assert.match(page, /<StatusAxes/);
  assert.match(page, /EvaluationProgressOverview/);
  assert.match(page, /sections=\{sections\}/);
});

test("Stage 1 remains frontend-only explanatory polish", () => {
  const combined = [
    read("src/components/polish/guided-workflow.tsx"),
    read("src/components/polish/evaluation-progress-overview.tsx"),
  ].join("\n");

  assert.doesNotMatch(combined, /\/api\/v1\//);
  assert.doesNotMatch(combined, /method:\s*"(POST|PATCH|DELETE)"/);
  assert.doesNotMatch(combined, /OpenAI|Groq|LLM|prompt/i);
});
