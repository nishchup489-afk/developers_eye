// Unit tests for the Wikipedia knowledge-panel helpers in lib/knowledge.ts (no build needed).
import assert from "node:assert/strict";
import {
  baseTitle,
  isKnowledgeResponse,
  knowledgeQuery,
  normalizeTitle,
  pickPanel,
  trimExtract,
} from "../lib/knowledge.ts";

// Which queries can get a panel.
assert.equal(knowledgeQuery("  react   native "), "react native");
assert.equal(knowledgeQuery("C++"), "C++");
assert.equal(knowledgeQuery("def f():\n  pass"), null, "pasted code");
assert.equal(knowledgeQuery("x"), null, "too short");
assert.equal(knowledgeQuery("a".repeat(61)), null, "too long");
assert.equal(knowledgeQuery("how do i center a div in css"), null, "more than five words");
assert.equal(knowledgeQuery("123 456"), null, "no letters");
assert.equal(knowledgeQuery("arr.map(x => x)"), null, "code punctuation");
console.log("PASS knowledgeQuery: short single-line topics only");

assert.equal(normalizeTitle("Café-Racer_JS"), "cafe racer js");
assert.equal(normalizeTitle("C#"), "c#");
assert.equal(baseTitle("Rust (programming language)"), "Rust");
assert.equal(baseTitle("Go"), "Go");
console.log("PASS normalizeTitle/baseTitle");

const page = (title, description, extra = {}) => ({
  ns: 0,
  title,
  description,
  extract: `${title} is described by a lead that is long enough to show in the panel.`,
  fullurl: `https://en.wikipedia.org/wiki/${title.replace(/ /g, "_")}`,
  ...extra,
});
const wiki = (...pages) => ({ query: { pages } });
const lang = "General-purpose programming language";

// Exact title (or redirect target) that is a real article.
let panel = pickPanel(wiki(page("PostgreSQL", "Relational database")), wiki(), "postgres");
assert.equal(panel.title, "PostgreSQL");
assert.equal(panel.thumbnail, null);
// A computing search hit beats an exact article about something else.
panel = pickPanel(
  wiki(page("Rust", "Iron oxide")),
  wiki(page("Rust", "Iron oxide", { index: 1 }), page("Rust (programming language)", lang, { index: 4 })),
  "rust",
);
assert.equal(panel.title, "Rust (programming language)");
// ...but not one about computing already.
panel = pickPanel(wiki(page("Redis", "In-memory key–value database")), wiki(page("Redis (album)", "Album", { index: 1 })), "redis");
assert.equal(panel.title, "Redis");
// Disambiguation pages fall through to the best-ranked computing match.
panel = pickPanel(
  wiki(page("Go", "", { pageprops: { disambiguation: "" } })),
  wiki(page("Go (game)", "Board game", { index: 1 }), page("Go (programming language)", lang, { index: 2 }), page("Go (software)", "Software", { index: 5 })),
  "go",
);
assert.equal(panel.title, "Go (programming language)");
// Non-computing exact articles still show when nothing better exists.
assert.equal(pickPanel(wiki(page("Apple", "Fruit")), wiki(), "apple").title, "Apple");
console.log("PASS pickPanel: exact titles, redirects, computing preference, disambiguation");

// Not confident: no panel.
for (const [direct, search, query, why] of [
  [wiki({ ns: 0, title: "Fastapi async", missing: true }), wiki(page("FastAPI", "Web framework", { index: 1 })), "fastapi async", "fuzzy search hit"],
  [wiki(page("Python", "", { pageprops: { disambiguation: "" } })), wiki(page("Monty Python", "Comedy", { index: 1 })), "python", "only disambiguation"],
  [wiki(page("Mercury", "", { extract: "Mercury may refer to:" })), wiki(), "mercury", "refer-to stub"],
  [wiki(page("List of Python software", "")), wiki(), "list of python software", "list page"],
  [wiki(page("Python", "Snake", { fullurl: "javascript:alert(1)" })), wiki(), "python", "unsafe URL"],
  [wiki(page("Python", "Snake", { fullurl: "https://evil.example/wiki/Python" })), wiki(), "python", "foreign host"],
  ["{no", null, "python", "malformed body"],
  [wiki(page("Talk:Python", "", { ns: 1 })), wiki(), "talk:python", "not an article"],
]) {
  assert.equal(pickPanel(direct, search, query), null, why);
}
console.log("PASS pickPanel: fuzzy hits, disambiguation, stubs, unsafe URLs, malformed bodies");

// Thumbnails only from upload.wikimedia.org with real dimensions.
const thumb = (source, width = 320, height = 200) => ({ thumbnail: { source, width, height } });
assert.deepEqual(
  pickPanel(wiki(page("Redis", "Database", thumb("https://upload.wikimedia.org/r.png"))), wiki(), "redis").thumbnail,
  { url: "https://upload.wikimedia.org/r.png", width: 320, height: 200 },
);
assert.equal(pickPanel(wiki(page("Redis", "Database", thumb("https://evil.example/r.png"))), wiki(), "redis").thumbnail, null);
assert.equal(pickPanel(wiki(page("Redis", "Database", thumb("https://upload.wikimedia.org/r.png", 0))), wiki(), "redis").thumbnail, null);
console.log("PASS thumbnails: Wikimedia host and dimensions only");

// Extracts are cut at a sentence boundary.
const long = "First sentence here. ".repeat(40);
const cut = trimExtract(long, 100);
assert.ok(cut.length <= 100 && cut.endsWith("."));
assert.equal(trimExtract("Short lead."), "Short lead.");
assert.ok(trimExtract("word ".repeat(200), 50).endsWith("…"));
console.log("PASS trimExtract");

// Browser-side validation of the route's body.
assert.equal(isKnowledgeResponse({ query: "x", panel: null }), true);
assert.equal(isKnowledgeResponse({ query: "redis", panel: pickPanel(wiki(page("Redis", "Database")), wiki(), "redis") }), true);
for (const bad of [null, {}, { query: 1, panel: null }, { query: "x", panel: { title: "x", extract: "y", description: null, url: "javascript:1", thumbnail: null } }]) {
  assert.equal(isKnowledgeResponse(bad), false);
}
console.log("PASS isKnowledgeResponse");
