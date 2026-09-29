import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("Stage C provides reusable structured empty and loading states", () => {
  const empty = read("src/components/ui/empty-state.tsx");
  const loading = read("src/components/ui/loading-state.tsx");

  assert.match(empty, /empty-state-mark/);
  assert.match(empty, /empty-state-copy/);
  assert.match(empty, /action\?: ReactNode/);
  assert.match(loading, /loading-state-heading/);
  assert.match(loading, /loading-skeleton/);
  assert.match(loading, /aria-busy="true"/);
});

test("Stage C gives the report repository a real empty state and shared pagination", () => {
  const page = read("src/app/(protected)/reports/page.tsx");

  assert.match(page, /reports\.data\.items\.length === 0/);
  assert.match(page, /No matching reports/);
  assert.match(page, /No reports yet/);
  assert.match(page, /<Pagination/);
  assert.match(page, /onRetry=\{\(\) => void reports\.refetch\(\)\}/);
});

test("Stage C polishes dashboard, tables, interaction and responsive behavior", () => {
  const dashboard = read("src/app/(protected)/dashboard/page.tsx");
  const css = read("src/app/globals.css");

  assert.match(dashboard, /page-stack dashboard-page/);
  assert.match(css, /\/\* Stage C — frontend polish \*\//);
  assert.match(css, /\.dashboard-page \.metric-card::before/);
  assert.match(css, /\.data-table tbody tr:focus-within/);
  assert.match(css, /\.loading-skeleton/);
  assert.match(css, /\.empty-state-mark/);
  assert.match(css, /@media \(hover: hover\)/);
  assert.match(css, /@media \(max-width: 650px\)/);
  assert.match(css, /\.laboratory-picker\s*\{\s*display: grid;/s);
});

test("Stage C remains presentation-only", () => {
  const combined = [
    read("src/components/ui/empty-state.tsx"),
    read("src/components/ui/loading-state.tsx"),
    read("src/app/(protected)/reports/page.tsx"),
    read("src/app/(protected)/dashboard/page.tsx"),
  ].join("\n");

  assert.doesNotMatch(combined, /method:\s*"(POST|PATCH|DELETE)"/);
  assert.doesNotMatch(combined, /useMutation/);
  assert.doesNotMatch(
    combined,
    /calculateMpe|maximum permissible error\s*=|compliance_outcome\s*=/i,
  );
});
