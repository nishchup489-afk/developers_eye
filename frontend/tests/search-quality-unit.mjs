import assert from "node:assert/strict";
import { isEvaluationReport, isJudgingQuery, isSlowSearchReport, judgmentBody, queryBody, redactSlowSearchReport } from "../lib/search-quality.ts";
import { evaluationFixture, judgingFixture, slowFixture } from "./fixtures/search-quality.mjs";

assert.equal(isSlowSearchReport(slowFixture()), true);
assert.equal(isEvaluationReport(evaluationFixture()), true);
assert.equal(isJudgingQuery(judgingFixture()), true);
const slowMutations = [(r) => { r.queries[0].elapsed_ms = "slow"; }, (r) => { r.stage_means_ms.ranking = "slow"; }, (r) => { r.repeated = null; }, (r) => { r.queries[0].stages.ranking = "x"; }];
for (const mutate of slowMutations) { const r = slowFixture(); mutate(r); assert.equal(isSlowSearchReport(r), false); }
const evalMutations = [(r) => { r.k = 7; }, (r) => { r.aggregate.bm25.ndcg_at_10 = "high"; }, (r) => { r.queries[0].no_relevant_documents = "no"; }, (r) => { delete r.aggregate; }];
for (const mutate of evalMutations) { const r = evaluationFixture(); mutate(r); assert.equal(isEvaluationReport(r), false); }
const judgingMutations = [(r) => { r.judgments[0].grade = 4; }, (r) => { r.judgments[0].origin = "agent"; }, (r) => { r.judgments = null; }];
for (const mutate of judgingMutations) { const r = judgingFixture(); mutate(r); assert.equal(isJudgingQuery(r), false); }
// The backend sends null means when no slow search was recorded in the window.
assert.equal(isSlowSearchReport({ ...slowFixture(), total: 0, timed_out: 0, timeouts_by_stage: {}, repeated: [], queries: [], stage_means_ms: { retrieval: null, ranking: null, metadata: null, snippets: null } }), true);
console.log("PASS search quality contract: slow searches (including an empty window), evaluation metrics, judging queries, malformed fields");

const admin = redactSlowSearchReport(slowFixture(), "admin");
assert.equal(admin.queries[0].query, "HTTP 500 internal server error");
for (const role of ["viewer", "guest"]) {
  const hidden = redactSlowSearchReport(slowFixture(), role);
  assert.ok(hidden.queries.every((q) => q.query === "(hidden)"));
  assert.equal(hidden.repeated[0].query, "Query 1");
  assert.equal(hidden.queries[0].elapsed_ms, 10700);
}
console.log("PASS slow search text is admin-only; viewers keep the timings");

assert.deepEqual(judgmentBody({ url: "https://docs.python.org/3/", grade: 2, note: "ok", judge: "forged" }), { url: "https://docs.python.org/3/", grade: 2, note: "ok", add: false });
assert.deepEqual(judgmentBody({ url: "http://example.com", grade: null, add: true }), { url: "http://example.com", grade: null, note: "", add: true });
for (const body of [null, [], { url: "javascript:alert(1)", grade: 1 }, { url: "https://x.test", grade: 4 }, { url: "https://x.test", grade: 1.5 }, { url: "https://x.test", grade: "2" }, { url: "https://x.test", grade: 1, note: "n".repeat(2001) }, { url: "https://x.test/" + "a".repeat(2048), grade: 1 }, { url: "https://x.test", grade: 1, add: "yes" }]) assert.equal(judgmentBody(body), null);
assert.deepEqual(queryBody({ query: "  python  ", mode: "text", source: "", no_relevant_documents: true }), { query: "python", mode: "text", source: null, stratum: "", note: "", no_relevant_documents: true });
for (const body of [{ query: "", mode: "all" }, { query: "x", mode: "images" }, { query: "q".repeat(257), mode: "all" }, { query: "x", mode: "all", no_relevant_documents: "yes" }, { query: "x", mode: "all", stratum: 3 }]) assert.equal(queryBody(body), null);
console.log("PASS judging write bodies: URL, grade 0-3 or null, note size, query and mode checks");
