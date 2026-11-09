// Unit tests for the spelling-suggestion helpers in lib/search.ts (no build needed).
import assert from "node:assert/strict";
import { forwardedFor, isSearchMode, isSearchableLength, maxQueryLength, maxRawQueryLength, maxSuggestQueryLength, normalizedQueryLength, parseCorrection, searchModes, shouldSuggest, suggestBelowResults, upstreamFailure } from "../lib/search.ts";

assert.deepEqual(searchModes, ["all", "text", "code"]);
for (const mode of searchModes) assert.equal(isSearchMode(mode), true);
for (const invalid of ["", "ALL", "javascript", null, 2, [], {}])
  assert.equal(isSearchMode(invalid), false);
console.log("PASS search modes: all, text, code and strict validation");

const correction = (suggested_query, corrections) => ({
  original_query: "ignored",
  suggested_query,
  corrections,
});
const fix = [{ original: "pyhton", replacement: "python", similarity: 0.3, edit_distance: 1 }];

// When the results page asks for a suggestion.
assert.equal(shouldSuggest("pyhton async", 0), true);
assert.equal(shouldSuggest("pyhton async", suggestBelowResults - 1), true);
assert.equal(shouldSuggest("pyhton async", suggestBelowResults), false);
assert.equal(shouldSuggest("   ", 0), false);
assert.equal(shouldSuggest("def f():\n  pass", 0), false, "pasted code");
assert.equal(shouldSuggest("x".repeat(257), 0), false, "over the backend's 256 chars");
assert.equal(shouldSuggest("a.b c_d 123", 0), false, "no plain word of 4+ letters");
console.log("PASS shouldSuggest: few results, plain single-line queries only");

// Validating FastAPI's QueryCorrection.
assert.deepEqual(parseCorrection(correction("python async", fix), "pyhton async"), {
  suggestion: "python async",
  corrections: [{ original: "pyhton", replacement: "python" }],
});
assert.deepEqual(
  parseCorrection(correction("  python   async ", fix), "pyhton async").suggestion,
  "python async",
  "whitespace is collapsed",
);
for (const [suggested, query] of [
  ["python async", "python async"],
  ["Python Async", "python   async"],
  ["", "pyhton"],
]) {
  assert.deepEqual(parseCorrection(correction(suggested, fix), query), {
    suggestion: null,
    corrections: [],
  });
}
assert.equal(
  parseCorrection(correction("python async", []), "pyhton async").suggestion,
  null,
  "no corrections means nothing to suggest",
);
for (const bad of [
  null,
  "text",
  {},
  { suggested_query: 5, corrections: [] },
  { suggested_query: "x", corrections: "no" },
  { suggested_query: "x", corrections: [{ original: "a" }] },
  { suggested_query: "x", corrections: [null] },
]) {
  assert.equal(parseCorrection(bad, "pyhton"), null);
}
console.log("PASS parseCorrection: valid, unchanged and malformed payloads");

// FastAPI's SearchConfig.max_query_length; the UI and every proxy route use this value.
assert.equal(maxQueryLength, 256);
assert.equal(maxSuggestQueryLength, maxQueryLength);
assert.equal(maxRawQueryLength, 1024);
console.log("PASS query length matches the backend (256)");

// Same expectations as _normalize_whitespace and analyze_query in the backend.
assert.equal(normalizedQueryLength("a   b\n\tc"), 5, "whitespace runs collapse");
assert.equal(normalizedQueryLength('"a   b"'), 7, "quoted spacing is preserved");
assert.equal(normalizedQueryLength('a  "b  c"  d'), 10);
assert.equal(normalizedQueryLength("😀😀"), 2, "code points, not UTF-16 units");
assert.equal(normalizedQueryLength("é"), 1, "NFC before counting");
assert.equal(isSearchableLength(""), false);
assert.equal(isSearchableLength("x".repeat(256)), true);
assert.equal(isSearchableLength("x".repeat(257)), false);
assert.equal(isSearchableLength(`x${" ".repeat(400)}y`), true, "collapses to 3 characters");
assert.equal(isSearchableLength(`x${" ".repeat(1100)}y`), false, "over the raw limit");
assert.equal(isSearchableLength("😀".repeat(256)), true);
console.log("PASS query length is measured the way FastAPI's analyzer measures it");

assert.deepEqual(upstreamFailure(429, "7"), {
  status: 429,
  error: "Too many searches. Wait a moment and try again.",
  retryAfter: "7",
});
assert.equal(upstreamFailure(429).retryAfter, "1", "429 always tells the client when to retry");
assert.equal(upstreamFailure(429, "soon").retryAfter, "1", "a malformed Retry-After is not passed on");
assert.deepEqual(upstreamFailure(503, "1"), {
  status: 503,
  error: "Search is busy right now. Please try again shortly.",
  retryAfter: "1",
});
assert.equal(upstreamFailure(503).retryAfter, undefined);
assert.equal(upstreamFailure(504).status, 504);
assert.match(upstreamFailure(504, undefined, "Suggestions").error, /^Suggestions timed out/);
assert.equal(upstreamFailure(422).status, 400);
for (const status of [400, 401, 404, 500, 502]) assert.equal(upstreamFailure(status).status, 502);
console.log("PASS upstreamFailure: 429/503 keep Retry-After, 504 stays a timeout, 422 is 400, rest 502");

const forwarded = (value) =>
  forwardedFor(new Request("http://localhost/api/search", value === undefined ? {} : { headers: { "X-Forwarded-For": value } }));
assert.deepEqual(forwarded("203.0.113.7"), { "X-Forwarded-For": "203.0.113.7" });
assert.deepEqual(forwarded("198.51.100.1, 203.0.113.9"), { "X-Forwarded-For": "203.0.113.9" }, "last hop wins");
assert.deepEqual(forwarded("2001:db8::1"), { "X-Forwarded-For": "2001:db8::1" });
assert.deepEqual(forwarded(undefined), {});
// A real Request refuses CR/LF in a header, so this needs a stand-in.
assert.deepEqual(forwardedFor({ headers: { get: () => "evil\r\nheader" } }), {});
assert.deepEqual(forwarded("1.2.3.4, not-an-ip"), {});
console.log("PASS forwardedFor: last hop only, IPv4/IPv6, rejects junk");
