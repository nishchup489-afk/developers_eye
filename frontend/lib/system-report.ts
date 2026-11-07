export type Budget = {
  budget_bytes: number; used_bytes: number; used_percent: number | null; warn_at_bytes: number; target_documents: number;
  bytes_per_document: number | null; target_bytes_per_document: number | null; projected_bytes_at_target: number | null;
  projected_percent_of_budget: number | null; documents_that_fit: number | null; status: "ok" | "warning" | "critical";
};
export type TableSize = {
  name: string; total_bytes: number; heap_bytes: number; index_bytes: number; toast_bytes: number; estimated_rows: number;
  dead_rows: number; dead_percent: number | null; last_vacuum_at: string | null; last_analyze_at: string | null;
};
export type SourceYield = {
  id: number; slug: string; name: string; enabled: boolean; attempts: number; stored_attempts: number; failed: number; blocked: number;
  bytes_received: number; documents: number; duplicate_documents: number; duplicate_percent: number | null;
  average_body_characters: number | null; yield_percent: number | null;
};
export type SystemReport = {
  version: 1; generated_at: string; window_days: number;
  database: { size_bytes: number; connections_used: number; connections_active: number; connections_max: number };
  budget: Budget;
  per_document_bytes: Record<string, number | null>;
  tables: TableSize[];
  progress: { target_documents: number; documents: number; available_documents: number; percent: number | null; new_last_hour: number;
    new_last_24h: number; per_day: number; remaining: number; eta_days: number | null; eta_at: string | null };
  sources: SourceYield[];
  telemetry: { retention_days: number; oldest_event_at: string | null; events_past_retention: number; estimated_event_rows: number };
  slow_queries: { query: string; calls: number; mean_ms: number; total_ms: number }[] | null;
};
export type HostFlag = "over_rate" | "throttled" | "hot";
export type HostRow = {
  host: string; attempts: number; attempts_last_5m: number; requests_per_minute: number; share_percent: number | null; successful: number;
  http_429: number; http_503: number; http_4xx: number; http_5xx: number; blocked: number; timeouts: number; sources: number;
  avg_fetch_ms: number | null; last_attempt_at: string | null; flags: HostFlag[];
};
export type HostReport = {
  version: 1; generated_at: string; window_minutes: number; total_attempts: number; min_interval_seconds: number;
  polite_requests_per_minute: number | null; online_workers: number; worst_case_requests_per_minute: number | null; hosts: HostRow[];
};
export type Severity = "critical" | "warning" | "info";
export type Problem = { id: string; severity: Severity; title: string; detail: string };
export type ProblemsReport = { version: 1; generated_at: string; problems: Problem[]; counts: Record<Severity, number> };

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const nullableNum = (v: unknown) => v === null || num(v);
const count = (v: unknown) => num(v) && Number.isSafeInteger(v);
const counts = (v: Record<string, unknown>, keys: string[]) => keys.every(k => count(v[k]));
const stamp = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const nullableStamp = (v: unknown) => v === null || stamp(v);
const percent = (v: unknown) => v === null || (num(v) && v <= 100);
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === "string");

export function isSystemReport(v: unknown): v is SystemReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !count(v.window_days)) return false;
  const d = v.database, b = v.budget, p = v.progress, t = v.telemetry;
  if (!object(d) || !counts(d, ["size_bytes", "connections_used", "connections_active", "connections_max"])) return false;
  if (!object(b) || !counts(b, ["budget_bytes", "used_bytes", "warn_at_bytes", "target_documents"]) || !["ok", "warning", "critical"].includes(String(b.status)) ||
    !["used_percent", "bytes_per_document", "target_bytes_per_document", "projected_bytes_at_target", "projected_percent_of_budget", "documents_that_fit"].every(k => nullableNum(b[k]))) return false;
  if (!object(v.per_document_bytes) || !Object.values(v.per_document_bytes).every(nullableNum)) return false;
  if (!Array.isArray(v.tables) || !v.tables.every(r => object(r) && typeof r.name === "string" && counts(r, ["total_bytes", "heap_bytes", "index_bytes", "toast_bytes", "estimated_rows", "dead_rows"]) && percent(r.dead_percent) && nullableStamp(r.last_vacuum_at) && nullableStamp(r.last_analyze_at))) return false;
  if (!object(p) || !counts(p, ["target_documents", "documents", "available_documents", "new_last_hour", "new_last_24h", "per_day", "remaining"]) || !percent(p.percent) || !nullableNum(p.eta_days) || !nullableStamp(p.eta_at)) return false;
  if (!Array.isArray(v.sources) || !v.sources.every(s => object(s) && strings(s, ["slug", "name"]) && typeof s.enabled === "boolean" &&
    counts(s, ["id", "attempts", "stored_attempts", "failed", "blocked", "bytes_received", "documents", "duplicate_documents"]) &&
    percent(s.duplicate_percent) && percent(s.yield_percent) && nullableNum(s.average_body_characters))) return false;
  if (!object(t) || !counts(t, ["retention_days", "events_past_retention", "estimated_event_rows"]) || !nullableStamp(t.oldest_event_at)) return false;
  return v.slow_queries === null || (Array.isArray(v.slow_queries) && v.slow_queries.every(q => object(q) && typeof q.query === "string" && count(q.calls) && num(q.mean_ms) && num(q.total_ms)));
}

export function isHostReport(v: unknown): v is HostReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !counts(v, ["window_minutes", "total_attempts", "online_workers"]) ||
    !num(v.min_interval_seconds) || !nullableNum(v.polite_requests_per_minute) || !nullableNum(v.worst_case_requests_per_minute)) return false;
  return Array.isArray(v.hosts) && v.hosts.length <= 50 && v.hosts.every(h => object(h) && typeof h.host === "string" &&
    counts(h, ["attempts", "attempts_last_5m", "successful", "http_429", "http_503", "http_4xx", "http_5xx", "blocked", "timeouts", "sources"]) &&
    num(h.requests_per_minute) && percent(h.share_percent) && nullableNum(h.avg_fetch_ms) && nullableStamp(h.last_attempt_at) &&
    Array.isArray(h.flags) && h.flags.every(f => ["over_rate", "throttled", "hot"].includes(String(f))));
}

export function isProblemsReport(v: unknown): v is ProblemsReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !object(v.counts) || !counts(v.counts, ["critical", "warning", "info"])) return false;
  return Array.isArray(v.problems) && v.problems.length <= 100 && v.problems.every(p => object(p) && strings(p, ["id", "title", "detail"]) &&
    ["critical", "warning", "info"].includes(String(p.severity)));
}

// Viewers see capacity numbers but not query text, which can carry literal values.
export function redactSystemReport(report: SystemReport, role: "admin" | "viewer" | "guest"): SystemReport {
  return role === "admin" ? report : { ...report, slow_queries: null };
}

export function bytes(value: number | null | undefined): string {
  if (value == null) return "N/A";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit++; }
  return `${size.toLocaleString("en-US", { maximumFractionDigits: unit >= 3 && size < 100 ? 1 : 0 })} ${units[unit]}`;
}

export function eta(days: number | null): string {
  if (days == null) return "N/A";
  if (days === 0) return "Reached";
  if (days < 1) return `${Math.max(1, Math.round(days * 24))} hours`;
  if (days < 365) return `${Math.round(days)} days`;
  return `${(days / 365).toLocaleString("en-US", { maximumFractionDigits: 1 })} years`;
}

export type CorpusShare = { name: string; documents: number; share_percent: number | null };
export type CorpusAge = { id: string; label: string; documents: number; share_percent: number | null };
export type CorpusSource = { id: number; slug: string; name: string; enabled: boolean; documents: number; available: number; share_percent: number | null; average_body_bytes: number | null };
export type CorpusStorage = { table: string; total_bytes: number; heap_bytes: number; index_bytes: number; toast_bytes: number; bytes_per_document: number | null };
export type CorpusReport = {
  version: 1; generated_at: string;
  estimates: { exact: boolean; sampled_documents: number; sampled_index_rows: number };
  summary: { total_documents: number; available_documents: number; unavailable_documents: number; indexed_documents: number; indexed_percent: number | null;
    total_body_bytes: number; average_body_bytes: number | null; sources: number; enabled_sources: number; hosts: number; hosts_exact: boolean };
  vocabulary: { terms: number; exact: boolean; pending_changes: number };
  freshness: { last_crawled_at: string | null; last_indexed_at: string | null; seen: CorpusAge[]; indexed: CorpusAge[] };
  bm25: { loaded: boolean; documents: number | null; average_text_length: number | null; average_code_length: number | null; loaded_at: string | null };
  storage: CorpusStorage[]; sources: CorpusSource[]; hosts: CorpusShare[]; document_types: CorpusShare[]; categories: CorpusShare[];
};

export type SearchStatus = "ok" | "degraded" | "down";
export type SearchTotals = {
  successful: number; invalid: number; busy: number; timed_out: number; database_errors: number; engine_errors: number; server_errors: number;
  requests: number; answered: number; failed: number; availability_percent: number | null; timeout_percent: number | null; busy_percent: number | null;
  mean_ms: number | null; p50_ms: number | null; p95_ms: number | null; p99_ms: number | null;
};
export type SearchSlot = { at: string; requests: number; failed: number; timed_out: number; busy: number; p95_ms: number | null };
export type PlannerTable = { table: string; estimated_rows: number; modified_since_analyze: number; dead_rows: number; dead_percent: number | null; last_analyze_at: string | null; last_vacuum_at: string | null; status: "ok" | "stale" };
export type SearchReport = {
  version: 1; generated_at: string; window_hours: number; status: SearchStatus; reasons: string[]; recording: boolean; partial: boolean;
  limits: { deadline_ms: number; max_concurrent_per_process: number; availability_target_percent: number };
  database: { reachable: boolean; ping_ms: number | null; connections_used: number | null; connections_max: number | null };
  schema: { current: string | null; expected: string | null; up_to_date: boolean | null };
  snapshot: { loaded: boolean; documents: number | null; loaded_at: string | null; age_seconds: number | null };
  planner: PlannerTable[]; totals: SearchTotals; recent: SearchTotals; timeline: SearchSlot[];
  latency: { le_ms: number | null; count: number }[];
  processes: { process: string; requests: number; last_seen_at: string }[];
};

const nullableCount = (v: unknown) => v === null || count(v);
const nullableText = (v: unknown) => v === null || typeof v === "string";
const nullableBool = (v: unknown) => v === null || typeof v === "boolean";
const shares = (v: unknown) => Array.isArray(v) && v.every(s => object(s) && typeof s.name === "string" && count(s.documents) && percent(s.share_percent));
const ages = (v: unknown) => Array.isArray(v) && v.every(a => object(a) && strings(a, ["id", "label"]) && count(a.documents) && percent(a.share_percent));

export function isCorpusReport(v: unknown): v is CorpusReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at)) return false;
  const e = v.estimates, s = v.summary, w = v.vocabulary, f = v.freshness, b = v.bm25;
  if (!object(e) || typeof e.exact !== "boolean" || !counts(e, ["sampled_documents", "sampled_index_rows"])) return false;
  if (!object(s) || !counts(s, ["total_documents", "available_documents", "unavailable_documents", "indexed_documents", "total_body_bytes", "sources", "enabled_sources", "hosts"]) ||
    !percent(s.indexed_percent) || !nullableNum(s.average_body_bytes) || typeof s.hosts_exact !== "boolean") return false;
  if (!object(w) || !counts(w, ["terms", "pending_changes"]) || typeof w.exact !== "boolean") return false;
  if (!object(f) || !nullableStamp(f.last_crawled_at) || !nullableStamp(f.last_indexed_at) || !ages(f.seen) || !ages(f.indexed)) return false;
  if (!object(b) || typeof b.loaded !== "boolean" || !nullableCount(b.documents) || !nullableNum(b.average_text_length) || !nullableNum(b.average_code_length) || !nullableStamp(b.loaded_at)) return false;
  if (!Array.isArray(v.storage) || !v.storage.every(t => object(t) && typeof t.table === "string" && counts(t, ["total_bytes", "heap_bytes", "index_bytes", "toast_bytes"]) && nullableNum(t.bytes_per_document))) return false;
  if (!Array.isArray(v.sources) || !v.sources.every(r => object(r) && strings(r, ["slug", "name"]) && typeof r.enabled === "boolean" && counts(r, ["id", "documents", "available"]) && percent(r.share_percent) && nullableNum(r.average_body_bytes))) return false;
  return Array.isArray(v.hosts) && v.hosts.length <= 50 && shares(v.hosts) && shares(v.document_types) && shares(v.categories);
}

const totals = (v: unknown) => object(v) && counts(v, ["successful", "invalid", "busy", "timed_out", "database_errors", "engine_errors", "server_errors", "requests", "answered", "failed"]) &&
  percent(v.availability_percent) && percent(v.timeout_percent) && percent(v.busy_percent) && ["mean_ms", "p50_ms", "p95_ms", "p99_ms"].every(k => nullableNum(v[k]));

export function isSearchReport(v: unknown): v is SearchReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !count(v.window_hours) || !["ok", "degraded", "down"].includes(String(v.status)) ||
    !Array.isArray(v.reasons) || !v.reasons.every(r => typeof r === "string") || typeof v.recording !== "boolean" || typeof v.partial !== "boolean") return false;
  const l = v.limits, d = v.database, c = v.schema, s = v.snapshot;
  if (!object(l) || !counts(l, ["deadline_ms", "max_concurrent_per_process"]) || !num(l.availability_target_percent)) return false;
  if (!object(d) || typeof d.reachable !== "boolean" || !nullableNum(d.ping_ms) || !nullableCount(d.connections_used) || !nullableCount(d.connections_max)) return false;
  if (!object(c) || !nullableText(c.current) || !nullableText(c.expected) || !nullableBool(c.up_to_date)) return false;
  if (!object(s) || typeof s.loaded !== "boolean" || !nullableCount(s.documents) || !nullableStamp(s.loaded_at) || !nullableCount(s.age_seconds)) return false;
  if (!Array.isArray(v.planner) || !v.planner.every(t => object(t) && typeof t.table === "string" && counts(t, ["estimated_rows", "modified_since_analyze", "dead_rows"]) && percent(t.dead_percent) && nullableStamp(t.last_analyze_at) && nullableStamp(t.last_vacuum_at) && ["ok", "stale"].includes(String(t.status)))) return false;
  if (!totals(v.totals) || !totals(v.recent)) return false;
  if (!Array.isArray(v.timeline) || !v.timeline.every(t => object(t) && stamp(t.at) && counts(t, ["requests", "failed", "timed_out", "busy"]) && nullableNum(t.p95_ms))) return false;
  if (!Array.isArray(v.latency) || !v.latency.every(b => object(b) && nullableCount(b.le_ms) && count(b.count))) return false;
  return Array.isArray(v.processes) && v.processes.every(p => object(p) && typeof p.process === "string" && count(p.requests) && stamp(p.last_seen_at));
}

// Process names carry the server's hostname, which viewers have no need for.
export function redactSearchReport(report: SearchReport, role: "admin" | "viewer" | "guest"): SearchReport {
  return role === "admin" ? report : { ...report, processes: report.processes.map((p, i) => ({ ...p, process: `API process ${i + 1}` })) };
}
