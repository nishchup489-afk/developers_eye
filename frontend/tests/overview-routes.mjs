// Real compiled route handlers, with only upstream fetch mocked. No real key/network.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
const require = createRequire(import.meta.url);
const dir = process.env.NEXT_BUILD_DIR || ".next";
const load = (path) => require(resolve(dir, `server/app/api/${path}/route.js`)).routeModule.userland;
const searchRoute = load("search");
const overviewRoute = load("search/overview");
process.env.BACKEND_URL = "http://search.test";
process.env.GROQ_API_KEY = "fake-groq-key-never-use";
process.env.AI_OVERVIEW = "on";
process.env.AI_OVERVIEW_CLIENT_IP_HEADER = "x-test-client";
const originalFetch = globalThis.fetch;
const originalNow = Date.now;
let now = originalNow();
Date.now = () => now;
let mode = "ok", sourceRevision = 0, groqCalls = 0, searches = 0;
const calls = [];
globalThis.fetch = async (input, init) => {
  const request = new Request(input, init);
  if (new URL(request.url).hostname === "search.test") {
    searches++;
    return Response.json({ results: [
      { title: "Python async documentation", source: "docs", url: `https://docs.python.org/3/library/asyncio.html?revision=${sourceRevision}`,
        snippet: "asyncio is a library to write concurrent code using the async/await syntax. ".repeat(5), score: 2 },
      { title: "Async guide", source: "articles", url: "https://example.com/async",
        snippet: "Asyncio is used for IO-bound concurrent code. ".repeat(9), score: 1 },
    ] });
  }
  assert.equal(request.url, "https://api.groq.com/openai/v1/chat/completions");
  assert.equal(request.headers.get("authorization"), `Bearer ${process.env.GROQ_API_KEY}`);
  assert.equal(request.redirect, "error");
  groqCalls++;
  const body = await request.json();
  calls.push(body);
  assert.equal(body.max_completion_tokens, 600);
  assert.equal(body.response_format.type, "json_object");
  assert.match(body.messages[0].content, /untrusted data/);
  assert.match(body.messages[0].content, /ONLY the provided/);
  const evidence = JSON.parse(body.messages[1].content);
  assert.equal(evidence.sources[0].kind, "docs");
  assert.equal(evidence.sources[0].url, undefined, "the model cannot choose or fetch URLs");
  if (mode === "limited") return Response.json({}, { status: 429, headers: { "Retry-After": "120" } });
  if (mode === "timeout") throw new DOMException("Timeout", "TimeoutError");
  if (mode === "error") return Response.json({ error: "private provider diagnostic" }, { status: 401 });
  const output = mode === "abstain" ? { paragraphs: [] } : {
    paragraphs: [{ text: "Asyncio supports concurrent code using async/await.", sources: [mode === "bad-citation" ? 99 : 1] }],
  };
  return Response.json({ choices: [{ finish_reason: mode === "truncated" ? "length" : "stop",
    message: { content: mode === "malformed" ? "{not json" : JSON.stringify(output) } }] });
};
const request = (body, headers = {}) => new Request("http://localhost:3000/api/search/overview", {
  method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json", ...headers },
});
const search = async (query) => {
  const response = await searchRoute.GET(new Request(`http://localhost:3000/api/search?q=${encodeURIComponent(query)}`));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.mode, "live");
  assert.equal(typeof body.overviewToken, "string");
  assert.ok(!JSON.stringify(body).includes(process.env.GROQ_API_KEY));
  return body;
};
try {
  const first = await search("python async");
  const [a, b] = await Promise.all([overviewRoute.POST(request({ token: first.overviewToken })), overviewRoute.POST(request({ token: first.overviewToken }))]);
  assert.equal(a.status, 200); assert.equal(b.status, 200);
  assert.equal(groqCalls, 1, "concurrent overview shares a single provider call");
  assert.equal(searches, 1, "overview reuses exact results without another search");
  const answer = await a.json();
  assert.equal(answer.overview.sources.length, 1);
  assert.equal(answer.overview.sources[0].url, first.results[0].url);
  const cached = await overviewRoute.POST(request({ token: first.overviewToken }));
  assert.equal(cached.status, 200); assert.equal(groqCalls, 1, "cache bypasses generation budgets");
  assert.equal(cached.headers.get("cache-control"), "no-store");
  const proxied = await overviewRoute.POST(new Request("http://internal-next:3000/api/search/overview", {
    method: "POST", headers: { "Content-Type": "application/json", Host: "search.example.com", Origin: "https://search.example.com" },
    body: JSON.stringify({ token: first.overviewToken }),
  }));
  assert.equal(proxied.status, 200, "browser-facing Host works behind an HTTPS reverse proxy");
  assert.equal((await overviewRoute.POST(request({ token: `${first.overviewToken}tampered` }))).status, 400);
  assert.equal((await overviewRoute.POST(request({ token: first.overviewToken }, { Origin: "https://attacker.test" }))).status, 403);
  assert.equal((await overviewRoute.POST(request({ token: first.overviewToken }, { "Sec-Fetch-Site": "cross-site" }))).status, 403);
  assert.equal((await overviewRoute.POST(request({ token: "x".repeat(25001) }))).status, 413);
  assert.equal((await overviewRoute.POST(request({}, { "Content-Type": "text/plain" }))).status, 415);
  assert.equal(groqCalls, 1, "invalid requests never call provider");
  const other = await search("another query");
  const limited = await overviewRoute.POST(request({ token: other.overviewToken }, { "x-test-client": "different" }));
  assert.equal(limited.status, 429); assert.ok(Number(limited.headers.get("retry-after")) > 0);
  assert.equal(groqCalls, 1, "global tokens cannot be bypassed with another client");
  now += 61_000;
  sourceRevision++;
  const changed = await search("python async");
  assert.equal((await overviewRoute.POST(request({ token: changed.overviewToken }))).status, 200);
  assert.equal(groqCalls, 2, "changed evidence invalidates cache for the same query");
  console.log("PASS overview routes: existing results, signed evidence, citations, coalescing/cache, source changes, request limits");

  for (const [scenario, status] of [["abstain", 200], ["bad-citation", 502], ["malformed", 502], ["truncated", 502], ["timeout", 504], ["error", 502], ["limited", 429]]) {
    now += 61_000; mode = scenario;
    const data = await search(scenario);
    const response = await overviewRoute.POST(request({ token: data.overviewToken }));
    assert.equal(response.status, status, scenario);
    const value = await response.json();
    assert.equal(value.overview, null);
    assert.ok(!JSON.stringify(value).includes("private provider diagnostic"));
    if (scenario === "limited") {
      assert.equal(response.headers.get("retry-after"), "120");
      const count = groqCalls;
      now += 61_000;
      const next = await search("during-provider-cooldown");
      const result = await overviewRoute.POST(request({ token: next.overviewToken }));
      assert.equal(result.status, 429); assert.equal(result.headers.get("retry-after"), "59");
      assert.equal(groqCalls, count, "provider cooldown stops new upstream requests");
    }
  }
  now += 11 * 60_000;
  assert.equal((await overviewRoute.POST(request({ token: first.overviewToken }))).status, 400);
  delete process.env.GROQ_API_KEY;
  assert.deepEqual(await (await overviewRoute.POST(request({}))).json(), { overview: null });
  const disabled = await (await searchRoute.GET(new Request("http://localhost:3000/api/search?q=disabled"))).json();
  assert.equal(disabled.overviewToken, undefined);
  delete process.env.BACKEND_URL;
  process.env.GROQ_API_KEY = "fake-key";
  const demo = await (await searchRoute.GET(new Request("http://localhost:3000/api/search?q=python"))).json();
  assert.equal(demo.mode, "demo"); assert.equal(demo.overviewToken, undefined);
  console.log("PASS overview routes: abstention, bad JSON/citations, truncation, timeouts, provider cooldown, expiry, missing key, demo mode");
} finally { globalThis.fetch = originalFetch; Date.now = originalNow; }
