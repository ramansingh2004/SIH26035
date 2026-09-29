import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

test("evidence uploader always uses the latest target ETag prop", () => {
  const uploader = fs.readFileSync(
    path.join(root, "src/components/evidence/evidence-uploader.tsx"),
    "utf8",
  );

  assert.match(uploader, /if \(!file \|\| !targetEtag\) return/);
  assert.equal(
    (uploader.match(/targetEtag,/g) ?? []).length >= 2,
    true,
  );
  assert.doesNotMatch(uploader, /currentEtag/);
  assert.doesNotMatch(uploader, /setCurrentEtag/);
  assert.doesNotMatch(uploader, /useEffect/);
});
