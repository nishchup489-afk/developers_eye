<<<<<<< HEAD
export type CrawlEvent = {
  id: number; attempt_id: number; target_id: number; worker_id: string | null;
  at: string; source: string; source_id: number; url: string; stage: string;
  outcome: string; details: Record<string, unknown>;
};
export type StoredDocument = { id: number; source: string; title: string; canonical_url: string; document_type: string; last_seen_at: string; is_available?: boolean; unavailable_at?: string | null; unavailable_http_status?: number | null };
export type FrontierTarget = { id: number; source: string; url: string; normalized_url: string; state: string; priority: number; retries: number; next_fetch_at: string; lease_until: string | null };
export type Worker = { id: string; hostname: string; pid: number; status: "online" | "offline" | "stopped"; started_at: string; heartbeat_at: string; concurrency: number; batch_size: number; uptime_seconds: number; idle_seconds: number; active_targets: { target_id: number; source_id: number; url: string }[] };
export type SourceHealth = { id: number; slug: string; name: string; is_enabled: boolean; attempts: number; successful: number; failed: number; blocked: number; documents: number; avg_fetch_ms: number | null; last_activity_at: string | null };
export type CrawlMonitor = {
  version: 1; generated_at: string; window_start: string; active_workers: number;
  summary: { attempted: number; instrumented: number; historical_uninstrumented: number; fetched: number; parsed: number; accepted: number; persisted: number; unfinished: number; http_responses: number; http_successes: number; fetch_success_percent: number | null; fetch_p50_ms: number | null; fetch_p95_ms: number | null; storage_avg_ms: number | null; response_avg_bytes: number | null; fetch_samples: number; urls_per_second: number; completed_last_5m: number; dispositions: Record<string, number> };
  throughput: { at: string; attempts: number; successful: number }[];
  events: CrawlEvent[]; events_has_more: boolean; workers: Worker[]; sources: SourceHealth[];
  documents: StoredDocument[]; documents_has_more: boolean; frontier: FrontierTarget[]; frontier_has_more: boolean;
};
export type DocumentDetail = StoredDocument & { description: string | null; body: string; body_truncated: boolean; body_characters: number; word_count: number; content_hash: string; metadata: Record<string, unknown>; author: string | null; updated_at: string; published_at: string | null; original_url: string | null; normalized_url: string | null; matching_content: { id: number; canonical_url: string }[]; raw_html_available: boolean; latest_attempt: { id: number; http_status: number | null; outcome: string | null } | null };
export type AttemptDetail = { id: number; url: string; normalized_url: string; source: string; target_id: number; http_status: number | null; started_at: string; finished_at: string | null; outcome: string | null; error: string | null; bytes_received: number | null; telemetry: Record<string, unknown> | null; events: CrawlEvent[] };

export function object(v: unknown): v is Record<string, unknown> { return !!v && typeof v === "object" && !Array.isArray(v); }
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const nullableNum = (v: unknown) => v === null || num(v);
const stamp = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === "string");
const numbers = (v: Record<string, unknown>, keys: string[]) => keys.every(k => num(v[k]));
const nullableString = (v: unknown) => v === null || typeof v === "string";
const events = (v: unknown): v is CrawlEvent[] => Array.isArray(v) && v.length <= 200 && v.every(e => object(e) && numbers(e, ["id", "attempt_id", "target_id", "source_id"]) && strings(e, ["at", "source", "url", "stage", "outcome"]) && stamp(e.at) && nullableString(e.worker_id) && object(e.details));
const doc = (v: unknown) => object(v) && num(v.id) && strings(v, ["source", "title", "canonical_url", "document_type", "last_seen_at"]) && stamp(v.last_seen_at) && (v.is_available === undefined || typeof v.is_available === "boolean") && (v.unavailable_at === undefined || v.unavailable_at === null || stamp(v.unavailable_at)) && (v.unavailable_http_status === undefined || v.unavailable_http_status === null || typeof v.unavailable_http_status === "number" && [404, 410].includes(v.unavailable_http_status));

export function isCrawlMonitor(v: unknown): v is CrawlMonitor {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !stamp(v.window_start) || !num(v.active_workers) || !object(v.summary)) return false;
  const s = v.summary;
  if (!numbers(s, ["attempted", "instrumented", "historical_uninstrumented", "fetched", "parsed", "accepted", "persisted", "unfinished", "http_responses", "http_successes", "fetch_samples", "urls_per_second", "completed_last_5m"]) || ![s.fetch_success_percent, s.fetch_p50_ms, s.fetch_p95_ms, s.storage_avg_ms, s.response_avg_bytes].every(nullableNum) || !object(s.dispositions) || !Object.values(s.dispositions).every(num)) return false;
  if (!events(v.events) || !Array.isArray(v.throughput) || v.throughput.length !== 60 || !v.throughput.every(t => object(t) && stamp(t.at) && numbers(t, ["attempts", "successful"]))) return false;
  if (![v.events_has_more, v.documents_has_more, v.frontier_has_more].every(b => typeof b === "boolean")) return false;
  if (!Array.isArray(v.documents) || v.documents.length > 30 || !v.documents.every(doc)) return false;
  if (!Array.isArray(v.frontier) || v.frontier.length > 30 || !v.frontier.every(t => object(t) && numbers(t, ["id", "retries"]) && typeof t.priority === "number" && Number.isFinite(t.priority) && strings(t, ["source", "url", "normalized_url", "state"]) && stamp(t.next_fetch_at) && (t.lease_until === null || stamp(t.lease_until)))) return false;
  if (!Array.isArray(v.sources) || !v.sources.every(s => object(s) && numbers(s, ["id", "attempts", "successful", "failed", "blocked", "documents"]) && strings(s, ["slug", "name"]) && typeof s.is_enabled === "boolean" && nullableNum(s.avg_fetch_ms) && (s.last_activity_at === null || stamp(s.last_activity_at)))) return false;
  return Array.isArray(v.workers) && v.workers.length <= 50 && v.workers.every(w => object(w) && strings(w, ["id", "hostname"]) && ["online", "offline", "stopped"].includes(String(w.status)) && stamp(w.started_at) && stamp(w.heartbeat_at) && numbers(w, ["pid", "concurrency", "batch_size", "uptime_seconds", "idle_seconds"]) && Array.isArray(w.active_targets) && w.active_targets.every(t => object(t) && numbers(t, ["target_id", "source_id"]) && typeof t.url === "string"));
}
export function isDocumentDetail(v: unknown): v is DocumentDetail {
  return object(v) && doc(v) && strings(v, ["body", "content_hash"]) && numbers(v, ["word_count", "body_characters"]) && typeof v.body_truncated === "boolean" && typeof v.raw_html_available === "boolean" && [v.description, v.author, v.original_url, v.normalized_url].every(nullableString) && stamp(v.updated_at) && (v.published_at === null || stamp(v.published_at)) && object(v.metadata) && (v.latest_attempt === null || object(v.latest_attempt) && num(v.latest_attempt.id) && nullableNum(v.latest_attempt.http_status) && nullableString(v.latest_attempt.outcome)) && Array.isArray(v.matching_content) && v.matching_content.every(m => object(m) && num(m.id) && typeof m.canonical_url === "string");
}
export function isAttemptDetail(v: unknown): v is AttemptDetail {
  return object(v) && numbers(v, ["id", "target_id"]) && strings(v, ["url", "normalized_url", "source"]) && nullableNum(v.http_status) && nullableNum(v.bytes_received) && [v.error, v.outcome].every(nullableString) && stamp(v.started_at) && (v.finished_at === null || stamp(v.finished_at)) && (v.telemetry === null || object(v.telemetry)) && events(v.events);
}
=======
export type CrawlEvent = {
  id: number; attempt_id: number; target_id: number; worker_id: string | null;
  at: string; source: string; source_id: number; url: string; stage: string;
  outcome: string; details: Record<string, unknown>;
};
export type StoredDocument = { id: number; source: string; title: string; canonical_url: string; document_type: string; last_seen_at: string; is_available?: boolean; unavailable_at?: string | null; unavailable_http_status?: number | null };
export type FrontierTarget = { id: number; source: string; url: string; normalized_url: string; state: string; priority: number; retries: number; next_fetch_at: string; lease_until: string | null };
export type Worker = { id: string; hostname: string; pid: number; status: "online" | "offline" | "stopped"; started_at: string; heartbeat_at: string; concurrency: number; batch_size: number; uptime_seconds: number; idle_seconds: number; active_targets: { target_id: number; source_id: number; url: string }[] };
export type SourceHealth = { id: number; slug: string; name: string; is_enabled: boolean; attempts: number; successful: number; failed: number; blocked: number; documents: number; avg_fetch_ms: number | null; last_activity_at: string | null };
export type CrawlMonitor = {
  version: 1; generated_at: string; window_start: string; active_workers: number;
  summary: { attempted: number; instrumented: number; historical_uninstrumented: number; fetched: number; parsed: number; accepted: number; persisted: number; unfinished: number; http_responses: number; http_successes: number; fetch_success_percent: number | null; fetch_p50_ms: number | null; fetch_p95_ms: number | null; storage_avg_ms: number | null; response_avg_bytes: number | null; fetch_samples: number; urls_per_second: number; completed_last_5m: number; dispositions: Record<string, number> };
  throughput: { at: string; attempts: number; successful: number }[];
  events: CrawlEvent[]; events_has_more: boolean; workers: Worker[]; sources: SourceHealth[];
  documents: StoredDocument[]; documents_has_more: boolean; frontier: FrontierTarget[]; frontier_has_more: boolean;
};
export type DocumentDetail = StoredDocument & { description: string | null; body: string; body_truncated: boolean; body_characters: number; word_count: number; content_hash: string; metadata: Record<string, unknown>; author: string | null; updated_at: string; published_at: string | null; original_url: string | null; normalized_url: string | null; matching_content: { id: number; canonical_url: string }[]; raw_html_available: boolean; latest_attempt: { id: number; http_status: number | null; outcome: string | null } | null };
export type AttemptDetail = { id: number; url: string; normalized_url: string; source: string; target_id: number; http_status: number | null; started_at: string; finished_at: string | null; outcome: string | null; error: string | null; bytes_received: number | null; telemetry: Record<string, unknown> | null; events: CrawlEvent[] };

export function object(v: unknown): v is Record<string, unknown> { return !!v && typeof v === "object" && !Array.isArray(v); }
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const nullableNum = (v: unknown) => v === null || num(v);
const stamp = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === "string");
const numbers = (v: Record<string, unknown>, keys: string[]) => keys.every(k => num(v[k]));
const nullableString = (v: unknown) => v === null || typeof v === "string";
const events = (v: unknown): v is CrawlEvent[] => Array.isArray(v) && v.length <= 200 && v.every(e => object(e) && numbers(e, ["id", "attempt_id", "target_id", "source_id"]) && strings(e, ["at", "source", "url", "stage", "outcome"]) && stamp(e.at) && nullableString(e.worker_id) && object(e.details));
const doc = (v: unknown) => object(v) && num(v.id) && strings(v, ["source", "title", "canonical_url", "document_type", "last_seen_at"]) && stamp(v.last_seen_at) && (v.is_available === undefined || typeof v.is_available === "boolean") && (v.unavailable_at === undefined || v.unavailable_at === null || stamp(v.unavailable_at)) && (v.unavailable_http_status === undefined || v.unavailable_http_status === null || typeof v.unavailable_http_status === "number" && [404, 410].includes(v.unavailable_http_status));

export function isCrawlMonitor(v: unknown): v is CrawlMonitor {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !stamp(v.window_start) || !num(v.active_workers) || !object(v.summary)) return false;
  const s = v.summary;
  if (!numbers(s, ["attempted", "instrumented", "historical_uninstrumented", "fetched", "parsed", "accepted", "persisted", "unfinished", "http_responses", "http_successes", "fetch_samples", "urls_per_second", "completed_last_5m"]) || ![s.fetch_success_percent, s.fetch_p50_ms, s.fetch_p95_ms, s.storage_avg_ms, s.response_avg_bytes].every(nullableNum) || !object(s.dispositions) || !Object.values(s.dispositions).every(num)) return false;
  if (!events(v.events) || !Array.isArray(v.throughput) || v.throughput.length !== 60 || !v.throughput.every(t => object(t) && stamp(t.at) && numbers(t, ["attempts", "successful"]))) return false;
  if (![v.events_has_more, v.documents_has_more, v.frontier_has_more].every(b => typeof b === "boolean")) return false;
  if (!Array.isArray(v.documents) || v.documents.length > 30 || !v.documents.every(doc)) return false;
  if (!Array.isArray(v.frontier) || v.frontier.length > 30 || !v.frontier.every(t => object(t) && numbers(t, ["id", "retries"]) && typeof t.priority === "number" && Number.isFinite(t.priority) && strings(t, ["source", "url", "normalized_url", "state"]) && stamp(t.next_fetch_at) && (t.lease_until === null || stamp(t.lease_until)))) return false;
  if (!Array.isArray(v.sources) || !v.sources.every(s => object(s) && numbers(s, ["id", "attempts", "successful", "failed", "blocked", "documents"]) && strings(s, ["slug", "name"]) && typeof s.is_enabled === "boolean" && nullableNum(s.avg_fetch_ms) && (s.last_activity_at === null || stamp(s.last_activity_at)))) return false;
  return Array.isArray(v.workers) && v.workers.length <= 50 && v.workers.every(w => object(w) && strings(w, ["id", "hostname"]) && ["online", "offline", "stopped"].includes(String(w.status)) && stamp(w.started_at) && stamp(w.heartbeat_at) && numbers(w, ["pid", "concurrency", "batch_size", "uptime_seconds", "idle_seconds"]) && Array.isArray(w.active_targets) && w.active_targets.every(t => object(t) && numbers(t, ["target_id", "source_id"]) && typeof t.url === "string"));
}
export function isDocumentDetail(v: unknown): v is DocumentDetail {
  return object(v) && doc(v) && strings(v, ["body", "content_hash"]) && numbers(v, ["word_count", "body_characters"]) && typeof v.body_truncated === "boolean" && typeof v.raw_html_available === "boolean" && [v.description, v.author, v.original_url, v.normalized_url].every(nullableString) && stamp(v.updated_at) && (v.published_at === null || stamp(v.published_at)) && object(v.metadata) && (v.latest_attempt === null || object(v.latest_attempt) && num(v.latest_attempt.id) && nullableNum(v.latest_attempt.http_status) && nullableString(v.latest_attempt.outcome)) && Array.isArray(v.matching_content) && v.matching_content.every(m => object(m) && num(m.id) && typeof m.canonical_url === "string");
}
export function isAttemptDetail(v: unknown): v is AttemptDetail {
  return object(v) && numbers(v, ["id", "target_id"]) && strings(v, ["url", "normalized_url", "source"]) && nullableNum(v.http_status) && nullableNum(v.bytes_received) && [v.error, v.outcome].every(nullableString) && stamp(v.started_at) && (v.finished_at === null || stamp(v.finished_at)) && (v.telemetry === null || object(v.telemetry)) && events(v.events);
}
>>>>>>> e23ba5ea5dff62949216780657e331ee7de5c4d1
