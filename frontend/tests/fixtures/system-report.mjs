// Shapes match backend.admin_services.system_reporting (version 1).
const now = "2026-11-04T03:00:00+00:00";
export function systemFixture() {
  return {
    version: 1, generated_at: now, window_days: 7,
    database: { size_bytes: 1372585984, connections_used: 6, connections_active: 1, connections_max: 100 },
    budget: { budget_bytes: 128849018880, used_bytes: 1372585984, used_percent: 1.07, warn_at_bytes: 103079215104, target_documents: 5000000,
      bytes_per_document: 32592.0, target_bytes_per_document: 25769.8, projected_bytes_at_target: 162960000000, projected_percent_of_budget: 126.47,
      documents_that_fit: 3953415, status: "warning" },
    per_document_bytes: { document: 20480.5, search_index: 8000.1, search_terms: 300.0, crawl_attempt: 900.0, crawl_event: 2500.0, crawl_target: 400.0 },
    tables: [{ name: "document", total_bytes: 862000000, heap_bytes: 300000000, index_bytes: 60000000, toast_bytes: 502000000, estimated_rows: 42114,
      dead_rows: 120, dead_percent: 0.28, last_vacuum_at: now, last_analyze_at: null }],
    progress: { target_documents: 5000000, documents: 42114, available_documents: 41900, percent: 0.84, new_last_hour: 310, new_last_24h: 7200,
      per_day: 7200, remaining: 4957886, eta_days: 688.6, eta_at: "2028-09-22T00:00:00+00:00" },
    sources: [{ id: 1, slug: "python-docs", name: "Python docs", enabled: true, attempts: 900, stored_attempts: 700, failed: 20, blocked: 5,
      bytes_received: 90000000, documents: 12000, duplicate_documents: 40, duplicate_percent: 0.33, average_body_characters: 8400, yield_percent: 77.78 }],
    telemetry: { retention_days: 14, oldest_event_at: now, events_past_retention: 0, estimated_event_rows: 290000 },
    slow_queries: [{ query: "SELECT * FROM document WHERE canonical_url = $1", calls: 900, mean_ms: 1.2, total_ms: 1080 }],
  };
}
export function hostsFixture() {
  return {
    version: 1, generated_at: now, window_minutes: 60, total_attempts: 120, min_interval_seconds: 2, polite_requests_per_minute: 30,
    online_workers: 2, worst_case_requests_per_minute: 60,
    hosts: [{ host: "docs.python.org", attempts: 100, attempts_last_5m: 40, requests_per_minute: 8, share_percent: 83.33, successful: 95, http_429: 2,
      http_503: 0, http_4xx: 3, http_5xx: 0, blocked: 1, timeouts: 1, sources: 1, avg_fetch_ms: 210.5, last_attempt_at: now, flags: ["throttled", "hot"] }],
  };
}
export function problemsFixture() {
  return { version: 1, generated_at: now, counts: { critical: 0, warning: 1, info: 0 },
    problems: [{ id: "disk_projection_over", severity: "warning", title: "The document goal will not fit the disk budget", detail: "At 31.8 KB per document..." }] };
}
