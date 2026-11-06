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
export function corpusFixture() {
  return {
    version: 1, generated_at: now,
    estimates: { exact: false, sampled_documents: 50000, sampled_index_rows: 50000 },
    summary: { total_documents: 2000000, available_documents: 1900000, unavailable_documents: 100000, indexed_documents: 1890000, indexed_percent: 99.47,
      total_body_bytes: 24000000000, average_body_bytes: 12000, sources: 3, enabled_sources: 2, hosts: 40, hosts_exact: false },
    vocabulary: { terms: 3100000, exact: false, pending_changes: 12 },
    freshness: { last_crawled_at: now, last_indexed_at: null,
      seen: [{ id: "day", label: "Last 24 hours", documents: 1000, share_percent: 0.05 }],
      indexed: [{ id: "day", label: "Last 24 hours", documents: 900, share_percent: 0.05 }] },
    bm25: { loaded: true, documents: 1890000, average_text_length: 410.2, average_code_length: 88.1, loaded_at: now },
    storage: [{ table: "document", total_bytes: 50000000000, heap_bytes: 2000000000, index_bytes: 1000000000, toast_bytes: 47000000000, bytes_per_document: 25000 }],
    sources: [{ id: 1, slug: "python-docs", name: "Python docs", enabled: true, documents: 12000, available: 11900, share_percent: 0.6, average_body_bytes: 8400 }],
    hosts: [{ name: "docs.python.org", documents: 12000, share_percent: 0.6 }],
    document_types: [{ name: "documentation", documents: 12000, share_percent: 0.6 }],
    categories: [{ name: "docs", documents: 12000, share_percent: 0.6 }],
  };
}
const searchTotals = { successful: 950, invalid: 4, busy: 10, timed_out: 40, database_errors: 0, engine_errors: 0, server_errors: 0, requests: 1004, answered: 1000,
  failed: 50, availability_percent: 95, timeout_percent: 4, busy_percent: 1, mean_ms: 120.5, p50_ms: 75, p95_ms: 900, p99_ms: 2400 };
export function searchFixture() {
  return {
    version: 1, generated_at: now, window_hours: 24, status: "degraded", reasons: ["95% of searches succeeded in the last 15 minutes."], recording: true, partial: false,
    limits: { deadline_ms: 3000, max_concurrent_per_process: 16, availability_target_percent: 99 },
    database: { reachable: true, ping_ms: 1.2, connections_used: 6, connections_max: 100 },
    schema: { current: "d4f1a7c2e9b3", expected: "d4f1a7c2e9b3", up_to_date: true },
    snapshot: { loaded: true, documents: 42000, loaded_at: now, age_seconds: 120 },
    planner: [{ table: "search_index", estimated_rows: 42000, modified_since_analyze: 10, dead_rows: 5, dead_percent: 0.01, last_analyze_at: now, last_vacuum_at: null, status: "ok" }],
    totals: { ...searchTotals }, recent: { ...searchTotals },
    timeline: [{ at: now, requests: 1000, failed: 50, timed_out: 40, busy: 10, p95_ms: 900 }],
    latency: [{ le_ms: 100, count: 950 }, { le_ms: null, count: 0 }],
    processes: [{ process: "api-host:12:abc123", requests: 1000, last_seen_at: now }],
  };
}
