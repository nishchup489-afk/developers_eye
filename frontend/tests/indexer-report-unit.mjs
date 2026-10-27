import assert from "node:assert/strict";
import { isIndexerReport } from "../lib/indexer-report.ts";

const now = Date.now(), at = (m = 0) => new Date(now - m * 60000).toISOString();
const fixture = () => ({
  version: 1, generated_at: at(), index_version: 1,
  coverage: { total_documents: 12, available_documents: 10, indexed_rows: 9, current_documents: 7, missing_documents: 2, stale_documents: 1, pending_documents: 3, reindex_requested: 1, unavailable_index_rows: 1, coverage_percent: 70 },
  activity: { status: "indexing", last_indexed_at: at(1), last_document_change_at: at(3), indexed_last_5m: 4, indexed_last_hour: 9, indexed_last_24h: 9, docs_per_minute: 0.8 },
  throughput: Array.from({ length: 60 }, (_, i) => ({ at: at(59 - i), indexed: i % 3 })),
  recent: [{ document_id: 1, title: "Doc", canonical_url: "https://example.com/a", source: "ex", indexed_at: at(1), index_version: "v1", current: true }],
  pending: [{ document_id: 2, title: "Doc 2", canonical_url: "https://example.com/b", source: "ex", updated_at: at(2), indexed_at: null, reason: "missing" }],
  sources: [{ id: 1, slug: "ex", name: "Example", available: 10, current: 7, missing: 2, stale: 1, coverage_percent: 70, last_indexed_at: at(1) }],
});

assert.ok(isIndexerReport(fixture()));
for (const mutate of [
  r => { r.version = 2; },
  r => { r.coverage.pending_documents = -1; },
  r => { r.coverage.coverage_percent = 101; },
  r => { r.activity.status = "running"; },
  r => { r.throughput.pop(); },
  r => { r.pending[0].reason = "unknown"; },
  r => { r.recent[0].current = "yes"; },
  r => { r.sources[0].last_indexed_at = "nope"; },
]) { const r = fixture(); mutate(r); assert.equal(isIndexerReport(r), false); }
const empty = fixture();
Object.assign(empty.coverage, { coverage_percent: null });
Object.assign(empty.activity, { status: "empty", last_indexed_at: null, last_document_change_at: null });
empty.recent = []; empty.pending = []; empty.sources = [];
assert.ok(isIndexerReport(empty));
console.log("PASS indexer report contract, null metrics and malformed responses");
