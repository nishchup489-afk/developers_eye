import assert from "node:assert/strict";
import { fixture } from "./fixtures/crawler-report.mjs";
import { createHmac, randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const secret = randomBytes(32).toString("hex");
const serviceKey = randomBytes(32).toString("hex");
let mode = "ok";
let calls = 0;

const mock = createServer((req, res) => {
  calls++;
  assert.equal(req.headers.authorization, `Bearer ${serviceKey}`);
  const url = new URL(req.url, "http://localhost");
  assert.equal(url.pathname, "/admin/crawler/report");
  res.setHeader("Content-Type", "application/json");
  if (mode === "unavailable") { res.writeHead(503); return res.end("{}"); }
  if (mode === "unauthorized") { res.writeHead(401); return res.end("{}"); }
  if (mode === "malformed") return res.end(JSON.stringify({ generated_at: "bad" }));
  if (mode === "bad-json") return res.end("{broken");
  res.end(JSON.stringify(fixture(Number(url.searchParams.get("days")))));
});
await new Promise((resolve) => mock.listen(0, "127.0.0.1", resolve));
const probe = createServer();
await new Promise((resolve) => probe.listen(0, "127.0.0.1", resolve));
const port = probe.address().port;
await new Promise((resolve) => probe.close(resolve));
const base = `http://127.0.0.1:${port}`;
let logs = "";
const child = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)], {
  env: { ...process.env, ADMIN_APP_URL: base, ADMIN_SESSION_SECRET: secret, ADMIN_GITHUB_IDS: "12345", GITHUB_CLIENT_ID: "integration-client", GITHUB_CLIENT_SECRET: "integration-secret", CRAWLER_REPORT_API_URL: `http://127.0.0.1:${mock.address().port}/admin/crawler/report`, CRAWLER_REPORT_API_KEY: serviceKey },
  windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
});
child.stdout.on("data", (chunk) => logs += chunk);
child.stderr.on("data", (chunk) => logs += chunk);
function session(overrides = {}) {
  const payload = Buffer.from(JSON.stringify({ purpose: "session", exp: Math.floor(Date.now() / 1000) + 3600, id: 12345, login: "test-admin", name: "Test Admin", ...overrides })).toString("base64url");
  return `${payload}.${createHmac("sha256", secret).update(payload).digest("base64url")}`;
}
const cookie = `de_admin_session=${session()}`;
try {
  let ready = false;
  let readiness = "";
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error(logs);
    try {
      const response = await fetch(`${base}/admin/login`, { signal: AbortSignal.timeout(2000) });
      if (response.ok) { ready = true; break; }
      readiness = `${response.status}: ${(await response.text()).slice(0, 500)}`;
    } catch (error) { readiness = `${error.message}: ${error.cause?.message || ""}`; }
    await delay(150);
  }
  assert.ok(ready, `Server did not start: ${readiness}\n${logs}`);
  for (const path of ["/admin", "/admin/crawler"]) {
    const response = await fetch(base + path, { redirect: "manual" });
    assert.equal(response.status, 307);
    assert.equal(new URL(response.headers.get("location"), base).pathname, "/admin/login");
  }
  const login = await (await fetch(`${base}/admin/login`)).text();
  assert.match(login, /Continue with GitHub/);
  const rejected = [undefined, "de_admin_session=forged", `de_admin_session=${session({ id: 99999 })}`, `de_admin_session=${session({ exp: 1 })}`, `de_admin_session=${session({ purpose: "oauth" })}`, `${cookie.slice(0, -1)}!`];
  for (const token of rejected) {
    const response = await fetch(`${base}/api/admin/crawler/report`, { headers: token ? { Cookie: token } : {} });
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  }
  assert.equal(calls, 0);
  console.log("PASS protected pages, forged/expired/wrong-purpose sessions, allowlist enforcement");
  const initiation = await fetch(`${base}/api/auth/github`, { redirect: "manual" });
  const github = new URL(initiation.headers.get("location"));
  assert.equal(github.origin, "https://github.com");
  assert.equal(github.searchParams.get("code_challenge_method"), "S256");
  assert.equal(github.searchParams.get("redirect_uri"), `${base}/api/auth/github/callback`);
  assert.equal(github.searchParams.get("state").length, 43);
  assert.equal(github.searchParams.get("code_challenge").length, 43);
  assert.match(initiation.headers.get("set-cookie"), /HttpOnly/);
  const flowCookie = initiation.headers.get("set-cookie").split(";")[0];
  const callback = await fetch(`${base}/api/auth/github/callback?state=wrong&code=bad`, { redirect: "manual", headers: { Cookie: flowCookie } });
  assert.match(callback.headers.get("location"), /error=state/);
  assert.match(callback.headers.get("set-cookie"), /Max-Age=0/);
  console.log("PASS OAuth state, PKCE, HttpOnly cookies, invalid callback rejection");
  const page = await fetch(`${base}/admin/crawler`, { headers: { Cookie: cookie } });
  assert.equal(page.status, 200);
  assert.match(await page.text(), /Crawler|overview/);
  for (const days of [7, 30, 90]) {
    const response = await fetch(`${base}/api/admin/crawler/report?days=${days}`, { headers: { Cookie: cookie } });
    assert.equal(response.status, 200);
    const report = await response.json();
    assert.equal(report.window.days, days);
    assert.equal(report.daily_attempts.length, days);
  }
  for (const query of ["days=0", "days=366", "days=7oops", "top_sources=101", "recent_errors=-1"]) {
    assert.equal((await fetch(`${base}/api/admin/crawler/report?${query}`, { headers: { Cookie: cookie } })).status, 400);
  }
  console.log("PASS authenticated report proxy, service credentials, date ranges, validation");
  for (mode of ["unavailable", "unauthorized", "malformed", "bad-json"]) {
    const response = await fetch(`${base}/api/admin/crawler/report`, { headers: { Cookie: cookie } });
    assert.equal(response.status, 502);
    assert.equal(typeof (await response.json()).error, "string");
  }
  assert.equal((await fetch(`${base}/api/auth/logout`, { method: "POST", redirect: "manual", headers: { Origin: "https://other.example", Cookie: cookie } })).status, 403);
  const logout = await fetch(`${base}/api/auth/logout`, { method: "POST", redirect: "manual", headers: { Origin: base, Cookie: cookie } });
  assert.equal(logout.status, 303);
  assert.match(logout.headers.get("set-cookie"), /Max-Age=0/);
  console.log("PASS upstream failure handling, invalid snapshots, same-origin logout, session clearing");

} finally {
  child.kill();
  mock.closeAllConnections();
  mock.close();
}
