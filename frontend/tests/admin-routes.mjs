// Invoke the actual production handlers in request context, without opening sockets.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";
import { AsyncLocalStorage } from "node:async_hooks";
import { resolve } from "node:path";
import { seal, unseal, userFromSession } from "../lib/admin-session.ts";
import { fixture } from "./fixtures/crawler-report.mjs";
import { monitorFixture, documentFixture, attemptFixture } from "./fixtures/crawler-monitor.mjs";
import { corpusFixture, hostsFixture, problemsFixture, searchFixture, systemFixture } from "./fixtures/system-report.mjs";
import { evaluationFixture, judgingFixture, slowFixture } from "./fixtures/search-quality.mjs";

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
const systemRoute = load("admin/system/report");
const hostsRoute = load("admin/system/hosts");
const problemsRoute = load("admin/system/problems");
const corpusRoute = load("admin/system/corpus");
const searchRoute = load("admin/system/search");
const slowRoute = load("admin/search-quality/slow");
const evaluationRoute = load("admin/search-quality/evaluation");
const judgingQueryRoute = load("admin/search-quality/queries/[id]");
const judgmentsRoute = load("admin/search-quality/queries/[id]/judgments");
const poolRoute = load("admin/search-quality/queries/[id]/pool");
const importRoute = load("admin/search-quality/queries/import");
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
// Any handler and method, with dynamic route params, in request context.
function handle(route, method, token, path, { params, body, origin = base } = {}) {
  const cookieJar = { get: () => token ? { value: token } : undefined };
  const init = { method, headers: { Origin: origin, ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) };
  return route.workAsyncStorage.run({ route: path, isStaticGeneration: false }, () =>
    route.workUnitAsyncStorage.run({ type: "request", phase: "render", cookies: cookieJar }, () => route.routeModule.userland[method](request(path, undefined, init), { params: Promise.resolve(params ?? {}) })));
}
let calls = [];
let responseMode = "ok";
let profileId = 42;
const originalFetch = globalThis.fetch;
// axios hands fetch a Request plus init, so normalise both into one view for the assertions.
globalThis.fetch = async (input, init) => {
  const req = new Request(input, init);
  const url = new URL(req.url);
  const text = req.method === "GET" ? "" : await req.text();
  const options = { method: req.method, headers: Object.fromEntries([...req.headers].map(([name, value]) => [name === "authorization" ? "Authorization" : name, value])), body: req.method === "POST" ? new URLSearchParams(text) : null, json: text && url.hostname === "reporting.test" ? JSON.parse(text) : null, redirect: req.redirect };
  calls.push({ url, options });
  if (url.hostname === "reporting.test") {
    assert.equal(options.headers.Authorization, `Bearer ${serviceKey}`);
    assert.equal(options.redirect, "error");
    if (responseMode === "timeout") throw new DOMException("timed out", "TimeoutError");
    if (responseMode === "unavailable") return Response.json({}, { status: 503 });
    if (responseMode === "malformed") return Response.json({});
    if (responseMode === "notfound") return Response.json({}, { status: 404 });
    if (url.pathname.endsWith("/search-quality/slow")) return Response.json(slowFixture());
    if (url.pathname.endsWith("/search-quality/evaluation")) return Response.json(evaluationFixture());
    if (url.pathname.includes("/search-quality/queries/")) {
      if (url.pathname.endsWith("/queries/MISSING/judgments")) return Response.json({ detail: "Judging query not found" }, { status: 404 });
      if (options.json?.url === "https://rejected.test/") return Response.json({ detail: "This URL is not in the pool; add it as an independently found page" }, { status: 422 });
      return Response.json(req.method === "GET" ? judgingFixture() : { ok: true });
    }
    if (url.pathname.endsWith("/monitor")) return Response.json(monitorFixture());
    if (url.pathname.endsWith("/system/report")) return Response.json(systemFixture());
    if (url.pathname.endsWith("/system/hosts")) return Response.json(hostsFixture());
    if (url.pathname.endsWith("/system/problems")) return Response.json(problemsFixture());
    if (url.pathname.endsWith("/system/corpus")) return Response.json(corpusFixture());
    if (url.pathname.endsWith("/system/search")) return Response.json(searchFixture());
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

  // Read-only viewers: listed ids sign in and read every report; slow query text stays admin-only.
  process.env.ADMIN_VIEWER_GITHUB_IDS = "77";
  profileId = 77;
  responseMode = "ok";
  const viewerLogin = await callbackRoute.routeModule.userland.GET(request(callbackUrl, flowCookie));
  assert.equal(new URL(viewerLogin.headers.get("location")).pathname, "/admin/crawler");
  const viewerToken = viewerLogin.headers.getSetCookie().find((cookie) => cookie.startsWith("de_admin_session=")).split(";")[0].split("=")[1];
  assert.equal(userFromSession(viewerToken), null);
  for (const [route, path] of [[monitorRoute, "/api/admin/crawler/monitor"], [systemRoute, "/api/admin/system/report"], [hostsRoute, "/api/admin/system/hosts"], [problemsRoute, "/api/admin/system/problems"]]) {
    const result = await monitoring(route, viewerToken, path);
    assert.equal(result.status, 200, `${path} ${result.status} ${await result.clone().text()}`);
    assert.equal(result.headers.get("cache-control"), "private, no-store");
  }
  assert.equal((await report(viewerToken)).status, 200);
  assert.equal((await (await monitoring(systemRoute, viewerToken, "/api/admin/system/report")).json()).slow_queries, null);
  assert.equal((await (await monitoring(systemRoute, session, "/api/admin/system/report?days=30")).json()).slow_queries.length, 1);
  assert.equal(calls.at(-1).url.pathname, "/admin/system/report");
  assert.equal(calls.at(-1).url.searchParams.get("days"), "30");
  for (const query of ["days=0", "days=91", "days=x"]) assert.equal((await monitoring(systemRoute, session, `/api/admin/system/report?${query}`)).status, 400);
  for (const query of ["minutes=4", "minutes=1441", "minutes=1e3"]) assert.equal((await monitoring(hostsRoute, session, `/api/admin/system/hosts?${query}`)).status, 400);
  assert.equal((await (await monitoring(corpusRoute, viewerToken, "/api/admin/system/corpus")).json()).summary.total_documents, 2000000);
  assert.equal((await (await monitoring(searchRoute, session, "/api/admin/system/search?hours=6")).json()).processes[0].process, "api-host:12:abc123");
  assert.equal(calls.at(-1).url.pathname, "/admin/system/search");
  assert.equal(calls.at(-1).url.searchParams.get("hours"), "6");
  assert.equal((await (await monitoring(searchRoute, viewerToken, "/api/admin/system/search")).json()).processes[0].process, "API process 1");
  for (const query of ["hours=0", "hours=169", "hours=1e2"]) assert.equal((await monitoring(searchRoute, session, `/api/admin/system/search?${query}`)).status, 400);
  for (const route of [systemRoute, hostsRoute, problemsRoute]) assert.equal((await monitoring(route, undefined, "/api/admin/system/problems")).status, 401);
  responseMode = "malformed";
  assert.equal((await monitoring(systemRoute, session, "/api/admin/system/report")).status, 502);
  responseMode = "ok";
  // Public mode: anonymous guests read, but never through a forged or unknown session.
  process.env.ADMIN_VIEWER_ACCESS = "public";
  const guest = await monitoring(problemsRoute, undefined, "/api/admin/system/problems");
  assert.equal(guest.status, 200);
  assert.equal((await (await monitoring(systemRoute, undefined, "/api/admin/system/report")).json()).slow_queries, null);
  assert.equal((await report(undefined)).status, 200);
  process.env.ADMIN_VIEWER_ACCESS = "off";
  process.env.ADMIN_VIEWER_GITHUB_IDS = "";
  assert.equal((await monitoring(systemRoute, viewerToken, "/api/admin/system/report")).status, 401);
  console.log("PASS read-only access: viewer sign-in, viewer and guest report reads, admin-only slow queries, query limits, revocation");

  // Search quality: slow-search text is admin-only; judging writes need an admin and this app's origin.
  process.env.ADMIN_VIEWER_GITHUB_IDS = "77";
  const slowAdmin = await (await monitoring(slowRoute, session, "/api/admin/search-quality/slow?hours=24&limit=50")).json();
  assert.equal(slowAdmin.queries[0].query, "HTTP 500 internal server error");
  assert.equal(calls.at(-1).url.pathname, "/admin/search-quality/slow");
  assert.equal(calls.at(-1).url.searchParams.get("limit"), "50");
  const slowViewer = await (await monitoring(slowRoute, viewerToken, "/api/admin/search-quality/slow")).json();
  assert.ok(slowViewer.queries.every((q) => q.query === "(hidden)"));
  for (const query of ["hours=0", "hours=721", "limit=501", "limit=1e2"]) assert.equal((await monitoring(slowRoute, session, `/api/admin/search-quality/slow?${query}`)).status, 400);
  assert.equal((await monitoring(evaluationRoute, viewerToken, "/api/admin/search-quality/evaluation?k=5")).status, 200);
  assert.equal(calls.at(-1).url.searchParams.get("k"), "5");
  assert.equal((await monitoring(evaluationRoute, session, "/api/admin/search-quality/evaluation?k=7")).status, 400);
  const judging = await handle(judgingQueryRoute, "GET", viewerToken, "/api/admin/search-quality/queries/H001", { params: { id: "H001" } });
  assert.equal((await judging.json()).judgments.length, 2);
  assert.equal(calls.at(-1).url.pathname, "/admin/search-quality/queries/H001");
  assert.equal((await handle(judgingQueryRoute, "GET", session, "/api/admin/search-quality/queries/x", { params: { id: "../crawler" } })).status, 400);
  let callsBefore = calls.length;
  const judgment = { url: "https://docs.python.org/3/", grade: 3, note: "best", judge: "forged" };
  const judgmentPath = "/api/admin/search-quality/queries/H001/judgments";
  assert.equal((await handle(judgmentsRoute, "PUT", viewerToken, judgmentPath, { params: { id: "H001" }, body: judgment })).status, 401);
  assert.equal((await handle(judgmentsRoute, "PUT", undefined, judgmentPath, { params: { id: "H001" }, body: judgment })).status, 401);
  assert.equal((await handle(judgmentsRoute, "PUT", session, judgmentPath, { params: { id: "H001" }, body: judgment, origin: "https://other.example" })).status, 403);
  assert.equal((await handle(judgmentsRoute, "PUT", session, judgmentPath, { params: { id: "H001" }, body: { ...judgment, grade: 5 } })).status, 400);
  assert.equal(calls.length, callsBefore);
  const saved = await handle(judgmentsRoute, "PUT", session, judgmentPath, { params: { id: "H001" }, body: judgment });
  assert.equal(saved.status, 200);
  assert.equal(calls.at(-1).options.method, "PUT");
  assert.equal(calls.at(-1).url.pathname, "/admin/search-quality/queries/H001/judgments");
  assert.deepEqual(calls.at(-1).options.json, { url: "https://docs.python.org/3/", grade: 3, note: "best", add: false, judge: "test-admin" });
  const rejected = await handle(judgmentsRoute, "PUT", session, judgmentPath, { params: { id: "H001" }, body: { url: "https://rejected.test/", grade: 1 } });
  assert.equal(rejected.status, 422);
  assert.match((await rejected.json()).error, /not in the pool/);
  assert.equal((await handle(judgmentsRoute, "PUT", session, "/api/admin/search-quality/queries/MISSING/judgments", { params: { id: "MISSING" }, body: judgment })).status, 404);
  const removed = await handle(judgmentsRoute, "DELETE", session, `${judgmentPath}?url=${encodeURIComponent("https://example.com/added")}`, { params: { id: "H001" } });
  assert.equal(removed.status, 200);
  assert.equal(calls.at(-1).url.searchParams.get("url"), "https://example.com/added");
  assert.equal((await handle(judgmentsRoute, "DELETE", session, `${judgmentPath}?url=javascript:alert(1)`, { params: { id: "H001" } })).status, 400);
  const queryEdit = await handle(judgingQueryRoute, "PUT", session, "/api/admin/search-quality/queries/H001", { params: { id: "H001" }, body: { query: "python async api", mode: "text", no_relevant_documents: true } });
  assert.equal(queryEdit.status, 200);
  assert.equal(calls.at(-1).options.json.no_relevant_documents, true);
  assert.equal((await handle(judgingQueryRoute, "PUT", session, "/api/admin/search-quality/queries/H001", { params: { id: "H001" }, body: { query: "x", mode: "images" } })).status, 400);
  assert.equal((await handle(judgingQueryRoute, "DELETE", viewerToken, "/api/admin/search-quality/queries/H001", { params: { id: "H001" } })).status, 401);
  assert.equal((await handle(poolRoute, "POST", session, "/api/admin/search-quality/queries/H001/pool", { params: { id: "H001" } })).status, 200);
  assert.equal(calls.at(-1).url.pathname, "/admin/search-quality/queries/H001/pool");
  assert.equal((await handle(importRoute, "POST", session, "/api/admin/search-quality/queries/import")).status, 200);
  assert.equal(calls.at(-1).url.pathname, "/admin/search-quality/queries/import");
  callsBefore = calls.length;
  assert.equal((await handle(importRoute, "POST", viewerToken, "/api/admin/search-quality/queries/import")).status, 401);
  assert.equal(calls.length, callsBefore);
  process.env.ADMIN_VIEWER_GITHUB_IDS = "";
  console.log("PASS search quality routes: admin-only slow query text, query limits, admin-only same-origin writes, judge from session, upstream errors");

  const deniedLogout = await logoutRoute.routeModule.userland.POST(request("/api/auth/logout", undefined, { method: "POST", headers: { Origin: "https://other.example" } }));
  assert.equal(deniedLogout.status, 403);
  const logout = await logoutRoute.routeModule.userland.POST(request("/api/auth/logout", undefined, { method: "POST", headers: { Origin: base } }));
  assert.equal(logout.status, 303);
  assert.ok(logout.headers.getSetCookie().every((cookie) => cookie.includes("Max-Age=0")));
  console.log("PASS production logout handler: origin enforcement and cleared cookies");
} finally { globalThis.fetch = originalFetch; }
