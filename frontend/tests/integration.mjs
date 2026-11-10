import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const processes = [];
const seenSearchRequests = [];
const seenForwardedFor = [];
// Upstream requests whose connection closed before the mock answered them.
const abandonedUpstream = [];
// A tiny MediaWiki action API (formatversion=2) for the knowledge panel.
const wikiCalls = {};
const article = (title, description, extra = {}) => ({
  ns: 0,
  title,
  description,
  extract: `${title} is a topic described by a fixture lead that is long enough to show. It has a second sentence.`,
  fullurl: `https://en.wikipedia.org/wiki/${encodeURIComponent(title.replace(/ /g, "_"))}`,
  ...extra,
});
const wikiPages = {
  direct: {
    postgres: [
      article("PostgreSQL", "Free and open-source relational database management system", {
        thumbnail: { source: "https://upload.wikimedia.org/pg.png", width: 320, height: 330 },
      }),
    ],
    rust: [article("Rust", "Iron oxide, a usually reddish-brown oxide")],
    python: [{ ...article("Python", ""), pageprops: { disambiguation: "" } }],
    apple: [article("Apple", "Fruit of the apple tree")],
    "wiki-unsafe": [{ ...article("Unsafe", "Programming"), fullurl: "javascript:alert(1)" }],
  },
  search: {
    rust: [
      { ...article("Rust (programming language)", "General-purpose programming language"), index: 2 },
      { ...article("Rust", "Iron oxide"), index: 1 },
    ],
    python: [
      { ...article("Monty Python", "British comedy troupe"), index: 1 },
      { ...article("Python (programming language)", "General-purpose programming language"), index: 3 },
    ],
    "react hooks tutorial": [{ ...article("React (software)", "JavaScript library"), index: 1 }],
  },
};
function wiki(url, res) {
  const term = url.searchParams.get("titles") ?? url.searchParams.get("gsrsearch");
  const kind = url.searchParams.has("titles") ? "direct" : "search";
  wikiCalls[term] = (wikiCalls[term] ?? 0) + 1;
  if (term === "wiki-timeout") return;
  if (term === "wiki-failure") {
    res.writeHead(503);
    return res.end("{}");
  }
  if (term === "wiki-malformed") return res.end("{no");
  const pages = wikiPages[kind][term] ?? (kind === "direct" ? [{ ns: 0, title: term, missing: true }] : []);
  res.end(JSON.stringify({ batchcomplete: true, query: { pages } }));
}
const mock = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const q = url.searchParams.get("q");
  res.setHeader("Content-Type", "application/json");
  if (url.pathname === "/w/api.php") return wiki(url, res);
  if (q === "timeout") return;
  if (q === "hang") {
    res.on("close", () => abandonedUpstream.push(url.pathname));
    return;
  }
  // FastAPI's overload and deadline responses.
  const failures = {
    limited: [429, { "Retry-After": "7" }],
    busy: [503, { "Retry-After": "1" }],
    "slow-db": [504, {}],
    "unsearchable": [422, {}],
  };
  if (failures[q]) {
    const [status, headers] = failures[q];
    res.writeHead(status, headers);
    return res.end(JSON.stringify({ detail: "upstream detail" }));
  }
  if (url.pathname === "/search" && q === "whoami")
    seenForwardedFor.push(req.headers["x-forwarded-for"] ?? null);
  if (q === "failure") {
    res.writeHead(503);
    return res.end("{}");
  }
  if (q === "malformed") return res.end("{no");
  if (url.pathname === "/search") seenSearchRequests.push(url.searchParams.toString());
  if (url.pathname === "/search/suggest") {
    if (q === "rejected") {
      res.writeHead(422);
      return res.end("{}");
    }
    if (q === "bad-suggest") return res.end(JSON.stringify({ suggested_query: 5 }));
    // Like the backend analyzer, collapse whitespace before correcting.
    const fixed = q.trim().replace(/\s+/g, " ") === "pyhton async";
    return res.end(
      JSON.stringify({
        original_query: q,
        suggested_query: fixed ? "python async" : q,
        corrections: fixed
          ? [{ original: "pyhton", replacement: "python", similarity: 0.27, edit_distance: 1 }]
          : [],
      }),
    );
  }
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
      env: {
        ...globalThis.process.env,
        BACKEND_URL: backend,
        WIKIPEDIA_API_URL: `${upstream}/w/api.php`,
      },
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
async function get(base, params, status = 200, path = "/api/search") {
  const response = await fetch(
    `${base}${path}?${new URLSearchParams(params)}`,
  );
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  return response.json();
}
try {
  const demo = await start(3181, "");
  const home = await (await fetch(demo)).text();
  assert.match(home, /class="eye-art reveal"/);
  assert.match(home, /id="sources"/);
  assert.doesNotMatch(home, /id="results"/);
  const resultsPage = await (await fetch(`${demo}/search?q=react`)).text();
  assert.match(resultsPage, /id="results"/);
  assert.match(resultsPage, /value="react"/);
  assert.doesNotMatch(resultsPage, /class="eye-art reveal"|id="sources"/);
  assert.equal((await fetch(`${demo}/search`)).status, 200);
  const savedPage = await (await fetch(`${demo}/search?saved=1`)).text();
  assert.match(savedPage, /YOUR PERSONAL INDEX/);
  const legacy = await fetch(`${demo}/?q=react&source=github`, { redirect: "manual" });
  assert.equal(legacy.status, 307);
  assert.equal(legacy.headers.get("location"), "/search?q=react&source=github");
  const modePage = await (await fetch(`${demo}/search?q=react&mode=code&source=docs`)).text();
  assert.match(modePage, /aria-label="Search mode"/);
  assert.match(modePage, /aria-pressed="true"[^>]*>Code</);
  const legacyMode = await fetch(`${demo}/?q=react&mode=text`, { redirect: "manual" });
  assert.equal(legacyMode.headers.get("location"), "/search?q=react&mode=text");
  console.log("PASS separate home/results routes, mode URL, saved page, legacy redirect");
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
  await get(demo, { q: "x".repeat(257) }, 400);
  await get(demo, { q: "x".repeat(256) });
  await get(demo, { q: `  ${"x".repeat(256)}  ` });
  await get(demo, { q: `x${" ".repeat(400)}y` });
  await get(demo, { q: `x${" ".repeat(1100)}y` }, 400);
  await get(demo, { q: "python", source: "unknown" }, 400);
  await get(demo, { q: "python", mode: "unsupported" }, 400);
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
  const suggest = (base, params, status = 200) =>
    get(base, params, status, "/api/search/suggest");
  data = await suggest(demo, { q: "pyhton" });
  assert.deepEqual(data, { query: "pyhton", suggestion: null, corrections: [], mode: "demo" });
  await suggest(demo, {}, 400);
  await suggest(demo, { q: "x".repeat(301) }, 400);
  await suggest(demo, { q: "x".repeat(257) }, 400);
  console.log("PASS demo suggestions return none, suggestion validation");
  const knowledge = async (params, status = 200) => {
    const response = await fetch(`${demo}/api/search/knowledge?${new URLSearchParams(params)}`);
    assert.equal(response.status, status);
    assert.equal(
      response.headers.get("cache-control"),
      status === 200 ? "public, max-age=3600" : "no-store",
    );
    return response.json();
  };
  data = await knowledge({ q: " postgres " });
  assert.equal(data.query, "postgres");
  assert.equal(data.panel.title, "PostgreSQL");
  assert.equal(data.panel.url, "https://en.wikipedia.org/wiki/PostgreSQL");
  assert.deepEqual(data.panel.thumbnail, { url: "https://upload.wikimedia.org/pg.png", width: 320, height: 330 });
  await knowledge({ q: "Postgres" });
  assert.equal(wikiCalls.postgres, 2, "cached: one direct and one search request");
  assert.equal((await knowledge({ q: "rust" })).panel.title, "Rust (programming language)");
  assert.equal((await knowledge({ q: "python" })).panel.title, "Python (programming language)");
  assert.equal((await knowledge({ q: "apple" })).panel.title, "Apple");
  assert.equal((await knowledge({ q: "react hooks tutorial" })).panel, null, "fuzzy hit");
  assert.equal((await knowledge({ q: "wiki-unsafe" })).panel, null, "unsafe article URL");
  assert.equal((await knowledge({ q: "wiki-malformed" })).panel, null);
  assert.equal((await knowledge({ q: "def f():\n  pass" })).panel, null);
  assert.equal(wikiCalls["def f():\n  pass"], undefined, "code never reaches Wikipedia");
  assert.equal(typeof (await knowledge({ q: "wiki-failure" }, 502)).error, "string");
  await knowledge({ q: "wiki-timeout" }, 504);
  await knowledge({}, 400);
  await knowledge({ q: "x".repeat(301) }, 400);
  await knowledge({ q: "x".repeat(257) }, 400);
  console.log("PASS knowledge panel: redirects, computing preference, confidence, cache, failures");
  const live = await start(3182, upstream);
  data = await get(live, { q: "python" });
  assert.equal(data.mode, "live");
  assert.equal(data.results[0].title, "Upstream result");
  for (const searchMode of ["all", "text", "code"]) {
    await get(live, { q: "fastapi", source: "docs", mode: searchMode });
    const forwarded = new URLSearchParams(seenSearchRequests.at(-1));
    assert.equal(forwarded.get("q"), "fastapi");
    assert.equal(forwarded.get("source"), "docs");
    assert.equal(forwarded.get("mode"), searchMode);
  }
  const seenBeforeInvalid = seenSearchRequests.length;
  await get(live, { q: "fastapi", mode: "invalid" }, 400);
  assert.equal(seenSearchRequests.length, seenBeforeInvalid, "invalid mode never reaches FastAPI");
  console.log("PASS all/text/code modes forwarded through live proxy");
  await get(live, { q: "fastapi", source: "docs", mode: "code", page: "2", limit: "10", language: "en" });
  const presentationParams = new URLSearchParams(seenSearchRequests.at(-1));
  for (const [key, value] of Object.entries({ page: "2", limit: "10", language: "en" }))
    assert.equal(presentationParams.get(key), value);
  const beforeBadPresentation = seenSearchRequests.length;
  for (const params of [{ language: "<en>" }, { limit: "51" }, { limit: "0" }, { page: "999", limit: "50" }])
    await get(live, { q: "fastapi", ...params }, 400);
  assert.equal(seenSearchRequests.length, beforeBadPresentation);
  console.log("PASS page size and language preference forwarding and validation");
  data = await get(live, { q: "failure" }, 503);
  assert.equal(data.results, undefined);
  assert.match(data.error, /busy/);
  for (const q of [
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
  let response = await fetch(`${live}/api/search?q=limited`);
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "7");
  assert.doesNotMatch(await response.text(), /upstream detail/);
  response = await fetch(`${live}/api/search?q=busy`);
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("retry-after"), "1");
  assert.equal((await get(live, { q: "slow-db" }, 504)).error, "Search timed out. Please try again.");
  await get(live, { q: "unsearchable" }, 400);
  response = await fetch(`${live}/api/search/suggest?q=limited`);
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "7");
  await suggest(live, { q: "slow-db" }, 504);
  console.log("PASS FastAPI 429/503 keep Retry-After, 504 stays 504, 422 becomes 400");
  for (const [sent, expected] of [
    ["203.0.113.7", "203.0.113.7"],
    ["198.51.100.1, 203.0.113.9", "203.0.113.9"],
  ]) {
    await fetch(`${live}/api/search?q=whoami`, { headers: { "X-Forwarded-For": sent } });
    assert.equal(seenForwardedFor.at(-1), expected);
  }
  console.log("PASS browser address forwarded to FastAPI for rate limiting");
  for (const path of ["/api/search", "/api/search/suggest"]) {
    const before = abandonedUpstream.length;
    const controller = new AbortController();
    const pending = fetch(`${live}${path}?q=hang`, { signal: controller.signal }).catch((error) => error);
    await delay(300);
    controller.abort();
    assert.equal((await pending).name, "AbortError");
    for (let i = 0; i < 30 && abandonedUpstream.length === before; i++) await delay(100);
    assert.equal(abandonedUpstream.length, before + 1, `${path}: browser abort closed the FastAPI request`);
    assert.equal(abandonedUpstream.at(-1), path.replace("/api", ""));
  }
  console.log("PASS browser cancellation propagates through Next.js to FastAPI");
  console.log(
    "PASS live proxy, schema/URL validation, upstream failures, timeout",
  );
  data = await suggest(live, { q: " pyhton   async " });
  assert.equal(data.query, "pyhton   async");
  assert.equal(data.suggestion, "python async");
  assert.deepEqual(data.corrections, [{ original: "pyhton", replacement: "python" }]);
  assert.equal(data.mode, "live");
  assert.equal((await suggest(live, { q: "python" })).suggestion, null);
  assert.equal((await suggest(live, { q: "rejected" })).suggestion, null);
  assert.equal((await suggest(live, { q: "def f():\n  pass" })).suggestion, null);
  assert.match((await suggest(live, { q: "failure" }, 503)).error, /busy/);
  for (const q of ["malformed", "bad-suggest"]) {
    data = await suggest(live, { q }, 502);
    assert.equal(typeof data.error, "string");
    assert.equal(data.suggestion, undefined);
  }
  await suggest(live, { q: "timeout" }, 504);
  console.log("PASS live suggestions, no-change, 422, code, upstream failures, timeout");
  await new Promise((resolve) => {
    mock.closeAllConnections();
    mock.close(resolve);
  });
  await get(live, { q: "disconnected" }, 502);
  await suggest(live, { q: "disconnected" }, 502);
  console.log("PASS no demo fallback when the backend is down");
} finally {
  for (const child of processes) child.kill();
  mock.closeAllConnections();
  mock.close();
}
