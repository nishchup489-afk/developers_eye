// Invoke the actual production handlers in request context, without opening sockets.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";
import { AsyncLocalStorage } from "node:async_hooks";
import { resolve } from "node:path";
import { seal, unseal, userFromSession } from "../lib/admin-session.ts";
import { fixture } from "./fixtures/crawler-report.mjs";
import { monitorFixture, documentFixture, attemptFixture } from "./fixtures/crawler-monitor.mjs";

const require = createRequire(import.meta.url);
globalThis.AsyncLocalStorage = AsyncLocalStorage;
process.env.NODE_ENV = "production";
const { NextRequest } = require("next/server");
const dir = process.env.NEXT_BUILD_DIR || ".next";
const load = (path) => require(resolve(dir, `server/app/api/${path}/route.js`));
const reportRoute = load("admin/crawler/report");
const monitorRoute = load("admin/crawler/monitor");
const inspectRoute = load("admin/crawler/inspect");
const githubRoute = load("auth/github");
const callbackRoute = load("auth/github/callback");
const logoutRoute = load("auth/logout");
const base = "http://localhost:3000";
const serviceKey = randomBytes(32).toString("hex");
Object.assign(process.env, { NODE_ENV: "production", ADMIN_APP_URL: base, ADMIN_SESSION_SECRET: randomBytes(32).toString("hex"), ADMIN_GITHUB_IDS: "42", GITHUB_CLIENT_ID: "test-client", GITHUB_CLIENT_SECRET: "test-secret", CRAWLER_REPORT_API_URL: "http://reporting.test/admin/crawler/report", CRAWLER_REPORT_API_KEY: serviceKey });
const identity = { id: 42, login: "test-admin", name: "Test Admin" };
const session = seal(identity, "session", 3600);
function request(path, cookie, extra = {}) {
  return new NextRequest(new URL(path, base), { ...extra, headers: { ...(cookie ? { Cookie: cookie } : {}), ...extra.headers } });
}
function report(token, query = "") {
  const cookieJar = { get: () => token ? { value: token } : undefined };
  return reportRoute.workAsyncStorage.run({ route: "/api/admin/crawler/report", isStaticGeneration: false }, () =>
    reportRoute.workUnitAsyncStorage.run({ type: "request", phase: "render", cookies: cookieJar }, () => reportRoute.routeModule.userland.GET(request(`/api/admin/crawler/report${query}`))));
}
function monitoring(route, token, path) {
  const cookieJar = { get: () => token ? { value: token } : undefined };
  return route.workAsyncStorage.run({ route: "/api/admin/crawler/monitor", isStaticGeneration: false }, () =>
    route.workUnitAsyncStorage.run({ type: "request", phase: "render", cookies: cookieJar }, () => route.routeModule.userland.GET(request(path))));
}
let calls = [];
let responseMode = "ok";
let profileId = 42;
const originalFetch = globalThis.fetch;
// axios hands fetch a Request plus init, so normalise both into one view for the assertions.
globalThis.fetch = async (input, init) => {
  const req = new Request(input, init);
  const url = new URL(req.url);
  const options = { headers: Object.fromEntries([...req.headers].map(([name, value]) => [name === "authorization" ? "Authorization" : name, value])), body: req.method === "POST" ? new URLSearchParams(await req.text()) : null, redirect: req.redirect };
  calls.push({ url, options });
  if (url.hostname === "reporting.test") {
    assert.equal(options.headers.Authorization, `Bearer ${serviceKey}`);
    assert.equal(options.redirect, "error");
    if (responseMode === "timeout") throw new DOMException("timed out", "TimeoutError");
    if (responseMode === "unavailable") return Response.json({}, { status: 503 });
    if (responseMode === "malformed") return Response.json({});
    if (responseMode === "notfound") return Response.json({}, { status: 404 });
    if (url.pathname.endsWith("/monitor")) return Response.json(monitorFixture());
    if (url.pathname.includes("/documents/")) return Response.json(documentFixture());
    if (url.pathname.includes("/attempts/")) return Response.json(attemptFixture());
    return Response.json(fixture(Number(url.searchParams.get("days"))));
  }
  if (url.href === "https://github.com/login/oauth/access_token") {
    assert.equal(options.body.get("client_secret"), "test-secret");
    assert.equal(typeof options.body.get("code_verifier"), "string");
    return Response.json({ access_token: "mock-provider-token", token_type: "bearer" });
  }
  assert.equal(url.href, "https://api.github.com/user");
  assert.equal(options.headers.Authorization, "Bearer mock-provider-token");
  return Response.json({ ...identity, id: profileId });
};
try {
  for (const token of [undefined, "forged", `${session}!`, seal(identity, "session", -1), seal({ ...identity, id: 99 }, "session", 60), seal(identity, "oauth", 60)]) assert.equal((await report(token)).status, 401);
  assert.equal(calls.length, 0);
  for (const [route, path] of [[monitorRoute, "/api/admin/crawler/monitor"], [inspectRoute, "/api/admin/crawler/inspect?type=documents&id=42"]]) {
    assert.equal((await monitoring(route, undefined, path)).status, 401);
    assert.equal((await monitoring(route, "forged", path)).status, 401);
    const result = await monitoring(route, session, path);
    assert.equal(result.status, 200);
    assert.equal(result.headers.get("cache-control"), "private, no-store");
    assert.equal(result.headers.get("vary"), "Cookie");
  }
  const monitorResult = await monitoring(monitorRoute, session, "/api/admin/crawler/monitor?source_id=1&status=skipped&category=process&q=async&unknown=secret");
  assert.equal(monitorResult.status, 200);
  assert.equal(calls.at(-1).url.pathname, "/admin/crawler/monitor");
  assert.equal(calls.at(-1).url.searchParams.get("status"), "skipped");
  assert.equal(calls.at(-1).url.searchParams.has("unknown"), false);
  assert.equal((await monitoring(inspectRoute, session, "/api/admin/crawler/inspect?type=attempts&id=1")).status, 200);
  for (const query of ["days=0", "source_id=-1", "status=invented", "category=imaginary", "frontier_page=10001", "q=" + "a".repeat(201)]) assert.equal((await monitoring(monitorRoute, session, `/api/admin/crawler/monitor?${query}`)).status, 400);
  for (const query of ["type=secret&id=1", "type=documents&id=0", "type=documents&id=../report"]) assert.equal((await monitoring(inspectRoute, session, `/api/admin/crawler/inspect?${query}`)).status, 400);
  for (responseMode of ["malformed", "unavailable", "timeout", "notfound"]) {
    assert.equal((await monitoring(monitorRoute, session, "/api/admin/crawler/monitor")).status, responseMode === "timeout" ? 504 : responseMode === "notfound" ? 404 : 502);
  }
  responseMode = "ok";
  console.log("PASS monitoring and inspector production handlers: authentication, query allowlists, validation, service key, private responses and upstream failures");
  const valid = await report(session, "?days=30&top_sources=50&recent_errors=0");
  assert.equal(valid.status, 200);
  assert.equal(valid.headers.get("cache-control"), "private, no-store");
  assert.equal((await valid.json()).window.days, 30);
  assert.equal(calls.at(-1).url.searchParams.get("recent_errors"), "0");
  for (const query of ["?days=0", "?days=366", "?days=7bad", "?top_sources=101", "?recent_errors=-1"]) assert.equal((await report(session, query)).status, 400);
  for (responseMode of ["unavailable", "malformed", "timeout"]) assert.equal((await report(session)).status, responseMode === "timeout" ? 504 : 502);
  const savedKey = process.env.CRAWLER_REPORT_API_KEY;
  delete process.env.CRAWLER_REPORT_API_KEY;
  assert.equal((await report(session)).status, 503);
  process.env.CRAWLER_REPORT_API_KEY = savedKey;
  console.log("PASS production report handler: session enforcement, query limits, service key, response validation, errors and timeouts");

  const initiation = await githubRoute.routeModule.userland.GET(request("/api/auth/github"));
  const provider = new URL(initiation.headers.get("location"));
  assert.equal(provider.origin, "https://github.com");
  assert.equal(provider.searchParams.get("code_challenge_method"), "S256");
  const flowCookie = initiation.headers.get("set-cookie").split(";")[0];
  const flow = unseal(flowCookie.slice(flowCookie.indexOf("=") + 1), "oauth");
  assert.equal(flow.state, provider.searchParams.get("state"));
  const before = calls.length;
  const bad = await callbackRoute.routeModule.userland.GET(request("/api/auth/github/callback?state=wrong&code=bad", flowCookie));
  assert.match(bad.headers.get("location"), /error=state/);
  assert.equal(calls.length, before);
  const callbackUrl = `/api/auth/github/callback?state=${flow.state}&code=mock-code`;
  const authenticated = await callbackRoute.routeModule.userland.GET(request(callbackUrl, flowCookie));
  assert.equal(new URL(authenticated.headers.get("location")).pathname, "/admin/crawler");
  const cookies = authenticated.headers.getSetCookie();
  const sessionCookie = cookies.find((cookie) => cookie.startsWith("de_admin_session="));
  assert.ok(sessionCookie);
  const token = sessionCookie.split(";")[0].split("=")[1];
  assert.deepEqual(userFromSession(token), identity);
  assert.equal(unseal(token, "session").access_token, undefined);
  assert.ok(cookies.some((cookie) => cookie.startsWith("de_github_flow=") && cookie.includes("Max-Age=0")));
  profileId = 99;
  const denied = await callbackRoute.routeModule.userland.GET(request(callbackUrl, flowCookie));
  assert.match(denied.headers.get("location"), /error=denied/);
  assert.ok(!denied.headers.getSetCookie().some((cookie) => cookie.startsWith("de_admin_session=")));
  console.log("PASS production OAuth handlers: PKCE initiation, state validation, mocked token exchange, verified identity, allowlist denial, signed session");

  const deniedLogout = await logoutRoute.routeModule.userland.POST(request("/api/auth/logout", undefined, { method: "POST", headers: { Origin: "https://other.example" } }));
  assert.equal(deniedLogout.status, 403);
  const logout = await logoutRoute.routeModule.userland.POST(request("/api/auth/logout", undefined, { method: "POST", headers: { Origin: base } }));
  assert.equal(logout.status, 303);
  assert.ok(logout.headers.getSetCookie().every((cookie) => cookie.includes("Max-Age=0")));
  console.log("PASS production logout handler: origin enforcement and cleared cookies");
} finally { globalThis.fetch = originalFetch; }
