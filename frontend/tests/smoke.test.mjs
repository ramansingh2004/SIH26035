import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:net";
import { setTimeout as delay } from "node:timers/promises";
import { test } from "node:test";

test("built frontend starts and serves the Phase 18 login shell", async () => {
  const reservation = createServer();
  reservation.listen(0, "127.0.0.1");
  await once(reservation, "listening");
  const port = reservation.address().port;
  await new Promise((resolve, reject) => {
    reservation.close((error) => (error ? reject(error) : resolve()));
  });

  const server = spawn(
    process.execPath,
    [
      "node_modules/next/dist/bin/next",
      "start",
      "--hostname",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
  let logs = "";
  server.stdout.on("data", (chunk) => (logs += chunk));
  server.stderr.on("data", (chunk) => (logs += chunk));
  const exit = once(server, "exit");

  try {
    const deadline = Date.now() + 30_000;
    let response;
    while (Date.now() < deadline) {
      assert.equal(server.exitCode, null, logs);
      try {
        response = await fetch(`http://127.0.0.1:${port}/login`, {
          signal: AbortSignal.timeout(2000),
        });
        break;
      } catch {
        await delay(100);
      }
    }

    assert.ok(response, `Frontend did not become ready.\n${logs}`);
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /<html[^>]+lang="en"/);
    assert.match(html, /NAWI Type Evaluation/);
    assert.match(html, /Authorized access/);
    assert.match(html, /Sign in/);
  } finally {
    if (server.exitCode === null) {
      server.kill("SIGTERM");
      const killTimer = setTimeout(() => server.kill("SIGKILL"), 5000);
      killTimer.unref();
      await exit;
      clearTimeout(killTimer);
    }
  }
});
