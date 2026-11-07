// Unit tests for the spelling-suggestion helpers in lib/search.ts (no build needed).
import assert from "node:assert/strict";
import { parseCorrection, shouldSuggest, suggestBelowResults } from "../lib/search.ts";

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
