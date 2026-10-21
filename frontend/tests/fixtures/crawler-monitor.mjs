// Synthetic records for automated tests only. Never imported by application code.
export function monitorFixture() {
  const now = new Date().toISOString();
  const document = { id: 42, source: "python-docs", title: "asyncio — Asynchronous I/O", canonical_url: "https://docs.python.org/3/library/asyncio.html", document_type: "documentation", last_seen_at: now };
  const events = [
    { id: 8, stage: "FINALIZE", outcome: "success", details: { reason: "Parsed 1 accepted, 0 skipped documents", action: "complete" } },
    { id: 7, stage: "DISCOVER", outcome: "complete", details: { discovered: 12, enqueued: 8 } },
    { id: 6, stage: "STORE", outcome: "persisted", details: { documents: [{ id: 42, decision: "new" }], duration_ms: 16 } },
    { id: 5, stage: "DEDUP", outcome: "new", details: { canonical_url: document.canonical_url, decision: "new", reason: "Canonical URL content hash comparison" } },
    { id: 4, stage: "PROCESS", outcome: "accepted", details: { accepted: 1, skipped: [] } },
    { id: 3, stage: "PARSE", outcome: "success", details: { documents: 1, words: 124 } },
    { id: 2, stage: "FETCH", outcome: "success", details: { http_status: 200, duration_ms: 248, bytes: 1800 } },
    { id: 1, stage: "FETCH", outcome: "running", details: { url: document.canonical_url } },
  ].map(event => ({ ...event, at: now, attempt_id: 1, target_id: 1, worker_id: "test-worker", source: "python-docs", source_id: 1, url: document.canonical_url }));
  return {
    version: 1, generated_at: now, window_start: now, active_workers: 1,
    summary: { attempted: 110, instrumented: 100, historical_uninstrumented: 10, fetched: 94, parsed: 91, accepted: 83, persisted: 76, unfinished: 2, http_responses: 100, http_successes: 94, fetch_success_percent: 94, fetch_p50_ms: 240, fetch_p95_ms: 680, storage_avg_ms: 16, response_avg_bytes: 1800, fetch_samples: 98, urls_per_second: 0.167, completed_last_5m: 50, dispositions: { persisted: 76, skipped: 16, failed: 4, blocked: 2, unfinished: 2, historical_unknown: 10 } },
    throughput: Array.from({ length: 60 }, (_, i) => ({ at: new Date(Date.now() - (59 - i) * 60000).toISOString(), attempts: i % 7 + 2, successful: i % 7 + 1 })),
    sources: [{ id: 1, slug: "python-docs", name: "Python Documentation", is_enabled: true, documents: 76, attempts: 110, successful: 94, failed: 4, blocked: 2, avg_fetch_ms: 280, last_activity_at: now }],
    workers: [{ id: "test-worker", hostname: "LOCAL-TEST", pid: 1234, status: "online", started_at: now, heartbeat_at: now, concurrency: 2, batch_size: 5, uptime_seconds: 125, idle_seconds: 0, active_targets: [{ target_id: 2, source_id: 1, url: "https://docs.python.org/3/tutorial/" }] }],
    events, events_has_more: false, documents: [document], documents_has_more: false,
    frontier: [{ id: 2, source: "python-docs", url: "https://docs.python.org/3/tutorial/", normalized_url: "https://docs.python.org/3/tutorial/", state: "leased", priority: 5, retries: 0, next_fetch_at: now, lease_until: now }], frontier_has_more: false,
  };
}
export function documentFixture() {
  const monitor = monitorFixture();
  return { ...monitor.documents[0], description: "Asynchronous I/O using async and await.", body: "asyncio is a library to write concurrent code using the async/await syntax.\n\n<script>This is stored text, never executable HTML.</script>", body_truncated: false, body_characters: 130, word_count: 20, content_hash: "test-content-hash", metadata: { headings: ["asyncio"], code_blocks: ["await asyncio.sleep(1)"] }, author: null, updated_at: monitor.generated_at, published_at: null, original_url: monitor.documents[0].canonical_url, normalized_url: monitor.documents[0].canonical_url, matching_content: [], raw_html_available: false, latest_attempt: { id: 1, http_status: 200, outcome: "success" } };
}
export function attemptFixture() {
  const m = monitorFixture();
  return { id: 1, url: m.documents[0].canonical_url, normalized_url: m.documents[0].canonical_url, source: "python-docs", target_id: 1, http_status: 200, started_at: m.generated_at, finished_at: m.generated_at, outcome: "success", error: null, bytes_received: 1800, telemetry: { fetch_ms: 248, content_type: "text/html", final_url: m.documents[0].canonical_url, redirects: [], documents: [{ id: 42, decision: "new", duplicate_of: null, canonical_url: m.documents[0].canonical_url }] }, events: m.events.toReversed() };
}
