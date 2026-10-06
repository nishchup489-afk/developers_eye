import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const processes = [];
const mock = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const q = url.searchParams.get("q");
  res.setHeader("Content-Type", "application/json");
  if (q === "timeout") return;
  if (q === "failure") {
    res.writeHead(503);
    return res.end("{}");
  }
  if (q === "malformed") return res.end("{no");
  const result = {
    title: "Upstream result",
    source: "docs",
    url: "https://example.com/docs",
    snippet: "Validated upstream content.",
    score: 5,
  };
  if (q === "unsafe") result.url = "javascript:alert(1)";
  if (q === "bad-url") result.url = "https://";
  if (q === "bad-source") result.source = "fastapi_docs";
  if (q === "bad-tags") result.tags = [42];
  res.end(JSON.stringify({ results: [result], echoedQuery: q }));
});
await new Promise((resolve) => mock.listen(0, "127.0.0.1", resolve));
const upstream = `http://127.0.0.1:${mock.address().port}`;

async function start(port, backend) {
  let logs = "";
  const process = spawn(
    globalThis.process.execPath,
    [
      "node_modules/next/dist/bin/next",
      "start",
      "--hostname",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      env: { ...globalThis.process.env, BACKEND_URL: backend },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  processes.push(process);
  process.stdout.on("data", (chunk) => {
    logs += chunk;
  });
  process.stderr.on("data", (chunk) => {
    logs += chunk;
  });
  for (let attempt = 0; attempt < 80; attempt++) {
    if (process.exitCode !== null) throw new Error(logs);
    try {
      if ((await fetch(`http://127.0.0.1:${port}/api/search?q=ready`)).ok)
        return `http://127.0.0.1:${port}`;
    } catch {}
    await delay(200);
  }
  throw new Error(`Server failed to start: ${logs}`);
}
async function get(base, params, status = 200) {
  const response = await fetch(
    `${base}/api/search?${new URLSearchParams(params)}`,
  );
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  return response.json();
}
try {
  const demo = await start(3181, "");
  let data = await get(demo, { q: " fastapi async " });
  assert.equal(data.mode, "demo");
  assert.equal(data.query, "fastapi async");
  assert.ok(data.results.length > 0);
  data = await get(demo, { q: "python", source: "docs" });
  assert.ok(data.results.length > 0);
  assert.ok(data.results.every((result) => result.source === "docs"));
  assert.equal((await get(demo, { q: "qzxqzxqzx" })).results.length, 0);
  await get(demo, {}, 400);
  await get(demo, { q: "   " }, 400);
  await get(demo, { q: "x".repeat(301) }, 400);
  await get(demo, { q: "python", source: "unknown" }, 400);
  assert.equal(
    (await fetch(`${demo}/api/search?q=python`, { method: "POST" })).status,
    405,
  );
  assert.equal((await fetch(`${demo}/docs`)).status, 200);
  assert.match(
    await (await fetch(`${demo}/api-reference.md`)).text(),
    /Proposed provider connectors/,
  );
  console.log(
    "PASS demo search, source filtering, empty state, validation, method handling, docs",
  );
  const live = await start(3182, upstream);
  data = await get(live, { q: "python" });
  assert.equal(data.mode, "live");
  assert.equal(data.results[0].title, "Upstream result");
  for (const q of [
    "failure",
    "malformed",
    "unsafe",
    "bad-url",
    "bad-source",
    "bad-tags",
  ]) {
    data = await get(live, { q }, 502);
    assert.equal(typeof data.error, "string");
    assert.equal(data.results, undefined);
  }
  await get(live, { q: "timeout" }, 504);
  await new Promise((resolve) => {
    mock.closeAllConnections();
    mock.close(resolve);
  });
  await get(live, { q: "disconnected" }, 502);
  console.log(
    "PASS live proxy, schema/URL validation, upstream failures, timeout, no demo fallback",
  );
} finally {
  for (const child of processes) child.kill();
  mock.closeAllConnections();
  mock.close();
}
