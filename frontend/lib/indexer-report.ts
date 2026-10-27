export type IndexerStatus = "indexing" | "caught_up" | "backlog_waiting" | "empty";
export type PendingReason = "missing" | "reindex_requested" | "old_version" | "content_changed";
export type IndexedDocument = { document_id: number; title: string; canonical_url: string; source: string; indexed_at: string; index_version: string; current: boolean };
export type PendingDocument = { document_id: number; title: string; canonical_url: string; source: string; updated_at: string; indexed_at: string | null; reason: PendingReason };
export type IndexerSource = { id: number; slug: string; name: string; available: number; current: number; missing: number; stale: number; coverage_percent: number | null; last_indexed_at: string | null };
export type IndexerReport = {
  version: 1; generated_at: string; index_version: number;
  coverage: { total_documents: number; available_documents: number; indexed_rows: number; current_documents: number; missing_documents: number; stale_documents: number; pending_documents: number; reindex_requested: number; unavailable_index_rows: number; coverage_percent: number | null };
  activity: { status: IndexerStatus; last_indexed_at: string | null; last_document_change_at: string | null; indexed_last_5m: number; indexed_last_hour: number; indexed_last_24h: number; docs_per_minute: number };
  throughput: { at: string; indexed: number }[];
  recent: IndexedDocument[]; pending: PendingDocument[]; sources: IndexerSource[];
};

export const statusLabel: Record<IndexerStatus, string> = { indexing: "Indexing now", caught_up: "Index caught up", backlog_waiting: "Backlog waiting", empty: "No documents yet" };

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const count = (v: unknown) => num(v) && Number.isSafeInteger(v);
const counts = (v: Record<string, unknown>, keys: string[]) => keys.every(k => count(v[k]));
const stamp = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const nullableStamp = (v: unknown) => v === null || stamp(v);
const percent = (v: unknown) => v === null || (num(v) && v <= 100);
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === "string");

// Validate at the server boundary so a partial snapshot never renders as zero backlog.
export function isIndexerReport(v: unknown): v is IndexerReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !count(v.index_version) || !object(v.coverage) || !object(v.activity)) return false;
  const c = v.coverage, a = v.activity;
  if (!counts(c, ["total_documents", "available_documents", "indexed_rows", "current_documents", "missing_documents", "stale_documents", "pending_documents", "reindex_requested", "unavailable_index_rows"]) || !percent(c.coverage_percent)) return false;
  if (!["indexing", "caught_up", "backlog_waiting", "empty"].includes(String(a.status)) || !nullableStamp(a.last_indexed_at) || !nullableStamp(a.last_document_change_at) || !counts(a, ["indexed_last_5m", "indexed_last_hour", "indexed_last_24h"]) || !num(a.docs_per_minute)) return false;
  if (!Array.isArray(v.throughput) || v.throughput.length !== 60 || !v.throughput.every(t => object(t) && stamp(t.at) && count(t.indexed))) return false;
  const doc = (d: unknown): d is Record<string, unknown> => object(d) && count(d.document_id) && strings(d, ["title", "canonical_url", "source"]);
  if (!Array.isArray(v.recent) || v.recent.length > 30 || !v.recent.every(d => doc(d) && stamp(d.indexed_at) && typeof d.index_version === "string" && typeof d.current === "boolean")) return false;
  if (!Array.isArray(v.pending) || v.pending.length > 30 || !v.pending.every(d => doc(d) && stamp(d.updated_at) && nullableStamp(d.indexed_at) && ["missing", "reindex_requested", "old_version", "content_changed"].includes(String(d.reason)))) return false;
  return Array.isArray(v.sources) && v.sources.every(s => object(s) && counts(s, ["id", "available", "current", "missing", "stale"]) && strings(s, ["slug", "name"]) && percent(s.coverage_percent) && nullableStamp(s.last_indexed_at));
}
