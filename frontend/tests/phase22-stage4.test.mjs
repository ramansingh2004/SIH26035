import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const frontendRoot = path.resolve(import.meta.dirname, "..");
const repositoryRoot = path.resolve(frontendRoot, "..");

function frontend(relative) {
  return fs.readFileSync(path.join(frontendRoot, relative), "utf8");
}

function repository(relative) {
  return fs.readFileSync(path.join(repositoryRoot, relative), "utf8");
}

test("Stage 4 keeps browser API requests same-origin on Vercel", () => {
  const config = frontend("src/lib/config.ts");
  assert.match(config, /configured === "\/"/);
  assert.match(config, /return ""/);

  const client = frontend("src/lib/api/client.ts");
  assert.match(client, /fetch\(`\$\{API_BASE_URL\}\$\{path\}`/);
  assert.match(client, /credentials: "include"/);
});

test("Stage 4 keeps the Render origin server-only", () => {
  const nextConfig = frontend("next.config.ts");
  assert.match(nextConfig, /process\.env\.BACKEND_API_ORIGIN/);
  assert.doesNotMatch(nextConfig, /NEXT_PUBLIC_BACKEND_API_ORIGIN/);
  assert.match(nextConfig, /source: "\/api\/v1\/:path\*"/);
});

test("Stage 4 retains strict auth cookies instead of cross-site cookies", () => {
  const auth = repository("backend/app/api/v1/auth.py");
  assert.match(auth, /samesite="strict"/);
  assert.doesNotMatch(auth, /samesite="none"/i);
});

test("Stage 4 S3 CORS template requires an exact production origin", () => {
  const cors = repository("deploy/aws/s3-cors.json.example");
  assert.match(cors, /REPLACE_WITH_VERCEL_PRODUCTION_ORIGIN/);
  assert.match(cors, /"AllowedMethods": \[\s*"PUT"/);
  assert.doesNotMatch(cors, /"AllowedOrigins": \[\s*"\*"/);
});

test("Stage 4 public verifier checks frontend and proxied auth boundary", () => {
  const script = repository("backend/scripts/check_vercel_frontend.py");
  assert.match(script, /VERCEL_FRONTEND_URL/);
  assert.match(script, /request\("\/login"\)/);
  assert.match(script, /request\("\/api\/v1\/auth\/me"\)/);
  assert.match(script, /auth_status != 401/);
});
