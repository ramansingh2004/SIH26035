import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("run evidence is persisted and rendered after refresh", () => {
  const api = read("src/lib/evaluations/run-api.ts");
  const page = read(
    "src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
  );
  const uploader = read("src/components/evidence/evidence-uploader.tsx");

  assert.match(api, /\/test-runs\/\$\{id\}\/evidence/);
  assert.match(page, /queryKey: \["run-evidence", runId\]/);
  assert.match(page, /existing=\{evidenceQuery\.data \?\? \[\]\}/);
  assert.doesNotMatch(page, /run-evidence-\$\{runItem\.lock_version\}/);
  assert.match(uploader, /Linked evidence/);
  assert.match(uploader, /No evidence is linked to this record/);
  assert.match(uploader, /attachment\.purpose/);
});
