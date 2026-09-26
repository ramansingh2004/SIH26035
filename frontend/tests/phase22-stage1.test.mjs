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

test("Phase 22 Stage 1 supports same-origin production API requests", () => {
  const config = frontend("src/lib/config.ts");
  assert.match(config, /NEXT_PUBLIC_API_BASE_URL/);
  assert.match(config, /configured === "\/"/);
  assert.match(config, /return ""/);
  assert.match(config, /http:\/\/127\.0\.0\.1:8000/);
});

test("Vercel proxies canonical API paths through a server-only backend origin", () => {
  const config = frontend("next.config.ts");
  assert.match(config, /BACKEND_API_ORIGIN/);
  assert.doesNotMatch(config, /NEXT_PUBLIC_BACKEND_API_ORIGIN/);
  assert.match(config, /source: "\/api\/v1"/);
  assert.match(config, /source: "\/api\/v1\/:path\*"/);
  assert.match(config, /destination: `\$\{origin\}\/api\/v1\/:path\*`/);
});

test("production proxy preserves strict cookie architecture", () => {
  const auth = repository("backend/app/api/v1/auth.py");
  assert.match(auth, /samesite="strict"/);
  assert.doesNotMatch(auth, /samesite="none"/i);

  const client = frontend("src/lib/api/client.ts");
  assert.match(client, /credentials: "include"/);
  assert.match(client, /X-CSRF-Token/);
});

test("deployment examples separate public frontend config from backend origin", () => {
  const env = frontend(".env.example");
  assert.match(env, /NEXT_PUBLIC_API_BASE_URL=\//);
  assert.match(env, /BACKEND_API_ORIGIN=https:\/\/your-render-service\.onrender\.com/);

  const backend = repository("backend/.env.example");
  assert.match(backend, /ENVIRONMENT=development/);
  assert.match(backend, /COOKIE_SECURE=true/);
  assert.match(backend, /STORAGE_PROVIDER=minio/);
});

test("Render production preflight checks security without printing secret values", () => {
  const script = repository("backend/scripts/check_production_config.py");
  assert.match(script, /ENVIRONMENT must be production/);
  assert.match(script, /COOKIE_SECURE must be true/);
  assert.match(script, /STORAGE_PROVIDER=s3/);
  assert.match(script, /secrets were not printed/);
  assert.doesNotMatch(script, /get_secret_value\(\).*print/);
});
