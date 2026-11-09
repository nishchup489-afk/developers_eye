// The UI bridge only forwards FastAPI's token/result/status; never calls Groq.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
const require = createRequire(import.meta.url);
const load = (path) => require(resolve(process.env.NEXT_BUILD_DIR || ".next", `server/app/api/${path}/route.js`)).routeModule.userland;
const search = load("search"), overview = load("search/overview");
const original = globalThis.fetch;
process.env.BACKEND_URL = "http://backend.test";
const token = "opaque-backend-token";
const result = { title: "Docs", source: "docs", url: "https://example.com/docs", snippet: "Evidence", score: 1 };
let status = 200, calls = [];
globalThis.fetch = async (input, init) => {
  const request = new Request(input, init);
  const url = new URL(request.url);
  assert.equal(url.hostname, "backend.test", "frontend must only contact FastAPI");
  calls.push(request);
  if (url.pathname === "/search") return Response.json({ results: [result], overview_token: token });
  assert.equal(url.pathname, "/search/overview");
  assert.deepEqual(await request.json(), { token });
  assert.equal(request.headers.get("x-eye-client-ip"), "198.51.100.12");
  assert.equal(request.headers.get("authorization"), null, "no Groq credentials in UI transport");
  return Response.json(status === 200 ? { overview: null } : { overview: null, error: "Backend quota reached" },
    { status, headers: status === 429 ? { "Retry-After": "120" } : {} });
};
const request = () => new Request("http://localhost:3000/api/search/overview", { method: "POST", headers: {
  "Content-Type": "application/json", "X-Eye-Client-IP": "198.51.100.12" }, body: JSON.stringify({ token }) });
try {
  const data = await (await search.GET(new Request("http://localhost:3000/api/search?q=python"))).json();
  assert.equal(data.overviewToken, token);
  assert.deepEqual(await (await overview.POST(request())).json(), { overview: null });
  status = 429;
  const limited = await overview.POST(request());
  assert.equal(limited.status, 429); assert.equal(limited.headers.get("retry-after"), "120");
  assert.equal(limited.headers.get("cache-control"), "no-store");
  status = 503;
  assert.equal((await overview.POST(request())).status, 503);
  const count = calls.length;
  delete process.env.BACKEND_URL;
  assert.deepEqual(await (await overview.POST(request())).json(), { overview: null });
  assert.equal(calls.length, count);
  const demo = await (await search.GET(new Request("http://localhost:3000/api/search?q=python"))).json();
  assert.equal(demo.mode, "demo"); assert.equal(demo.overviewToken, undefined);
  console.log("PASS UI overview bridge: backend token/results, shared quota headers, trusted ingress forwarding, no provider calls, demo mode");
} finally { globalThis.fetch = original; }
