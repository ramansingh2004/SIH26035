import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("linked run evidence can be safely unlinked while editable", () => {
  const api = read("src/lib/evidence/api.ts");
  const uploader = read("src/components/evidence/evidence-uploader.tsx");
  const page = read(
    "src/app/(protected)/evaluations/[sessionId]/runs/[runId]/page.tsx",
  );

  assert.match(
    api,
    /attachments\/\$\{input\.attachmentId\}\/links\/\$\{input\.linkId\}/,
  );
  assert.match(api, /method: "DELETE"/);
  assert.match(api, /etag: input\.targetEtag/);
  assert.match(uploader, /Reason for unlinking this evidence/);
  assert.match(uploader, /"Unlink"/);
  assert.match(page, /hasPermission\("attachment:delete"\)/);
});

