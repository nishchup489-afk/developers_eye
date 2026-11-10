// Shapes match backend.admin_services.search_quality (ADR-0057).
const now = "2026-11-10T04:13:19+00:00";
export function slowFixture() {
  return {
    hours: 24, threshold_ms: 1000, total: 2, timed_out: 1,
    stage_means_ms: { retrieval: 420.5, ranking: 1630.2, metadata: 5.0, snippets: 1.8 },
    timeouts_by_stage: { ranking: 1 },
    repeated: [{ query: "HTTP 500 internal server error", mode: "all", count: 2, timed_out: 1, max_ms: 10700, mean_ms: 6100 }],
    queries: [
      { recorded_at: now, query: "HTTP 500 internal server error", mode: "all", category: null, page: 1, outcome: "timed_out", elapsed_ms: 10700, result_count: null, stages: { retrieval: 800.1 }, stopped_in: "ranking" },
      { recorded_at: now, query: "python context manager", mode: "text", category: "docs", page: 1, outcome: "successful", elapsed_ms: 1500, result_count: 10, stages: { retrieval: 41, ranking: 1420, metadata: 5, snippets: 2 }, stopped_in: null },
    ],
  };
}
export function evaluationFixture() {
  const metrics = { precision_at_10: 0.5, mrr_at_10: 1.0, ndcg_at_10: 0.81 };
  return {
    k: 10, human_set_available: true,
    aggregate: { complete_queries: 1, total_queries: 2, status: "incomplete", bm25: metrics, postgresql: { ...metrics, ndcg_at_10: 0.7 }, candidate_recall: 1.0 },
    queries: [
      { id: "H001", query: "python async api", mode: "text", stratum: "multi-term", source: "docs", note: "", no_relevant_documents: false, pooled: 12, graded: 12, positives: 5, last_pooled_at: now, candidate_count: 100, status: "complete", candidate_recall_at_100_per_channel: 1.0, bm25: metrics, postgresql: metrics },
      { id: "H002", query: "asyncio.create_task", mode: "code", stratum: "identifier", source: null, note: "", no_relevant_documents: false, pooled: 0, graded: 0, positives: 0, last_pooled_at: null, candidate_count: null, status: "not_pooled", reason: "Capture a pool first" },
    ],
  };
}
export function judgingFixture() {
  return {
    id: "H001", query: "python async api", mode: "text", stratum: "multi-term", source: "docs", note: "", no_relevant_documents: false,
    judgments: [
      { url: "https://docs.python.org/3/library/asyncio.html", title: "asyncio", grade: 3, note: "Canonical reference", origin: "pool", judged_by: "test-admin", judged_at: now },
      { url: "https://example.com/added", title: "", grade: null, note: "", origin: "added", judged_by: null, judged_at: null },
    ],
  };
}
