import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

test("run source refresh invalidates run history", () => {
  const page = fs.readFileSync(
    path.join(
      root,
      "src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
    ),
    "utf8",
  );

  const refreshStart = page.indexOf("async function refreshRunSources()");
  assert.notEqual(refreshStart, -1);

  const refreshEnd = page.indexOf("\n  function handleError", refreshStart);
  assert.notEqual(refreshEnd, -1);

  const refresh = page.slice(refreshStart, refreshEnd);

  assert.match(refresh, /queryKey: \["run-history", runId\]/);
  assert.match(refresh, /queryKey: \["run-results", runId\]/);
});
