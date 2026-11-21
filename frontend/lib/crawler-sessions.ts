// Crawl session report: total work between a crawler start and stop, across every worker.

export type SessionSourceWork = { slug: string; attempts: number; successful: number; errors: number; documents_stored: number };
export type SessionWork = {
  attempts: number; finished: number; successful: number; failed: number; blocked: number; not_modified: number; stale: number;
  timeouts: number; attempts_stored: number; documents_stored: number; links_discovered: number; links_enqueued: number;
  bytes_received: number; sources: number; avg_fetch_ms: number | null; p95_fetch_ms: number | null;
  first_attempt_at: string | null; last_attempt_at: string | null; attempts_per_minute: number; success_percent: number | null;
  by_source: SessionSourceWork[];
};
export type SessionWorker = { id: string; hostname: string; pid: number; started_at: string; stopped_at: string | null; crashed: boolean; concurrency: number };
export type CrawlSession = {
  id: string; started_at: string; stopped_at: string | null; running: boolean; duration_seconds: number;
  worker_count: number; hosts: string[]; peak_concurrency: number; workers: SessionWorker[]; work: SessionWork;
};
export type CrawlSessionsReport = { version: 1; generated_at: string; custom: boolean; sessions: CrawlSession[] };

const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const count = (v: unknown) => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const num = (v: unknown) => typeof v === "number" && Number.isFinite(v);
const nullableNum = (v: unknown) => v === null || num(v);
const stamp = (v: unknown) => typeof v === "string" && !Number.isNaN(Date.parse(v));
const nullableStamp = (v: unknown) => v === null || stamp(v);
const counts = (o: Record<string, unknown>, keys: string[]) => keys.every(k => count(o[k]));

function isWork(w: unknown): w is SessionWork {
  return object(w) && counts(w, ["attempts", "finished", "successful", "failed", "blocked", "not_modified", "stale", "timeouts",
    "attempts_stored", "documents_stored", "links_discovered", "links_enqueued", "bytes_received", "sources"]) &&
    nullableNum(w.avg_fetch_ms) && nullableNum(w.p95_fetch_ms) && num(w.attempts_per_minute) && nullableNum(w.success_percent) &&
    nullableStamp(w.first_attempt_at) && nullableStamp(w.last_attempt_at) &&
    Array.isArray(w.by_source) && w.by_source.length <= 15 &&
    w.by_source.every(s => object(s) && typeof s.slug === "string" && counts(s, ["attempts", "successful", "errors", "documents_stored"]));
}

export function isCrawlSessionsReport(v: unknown): v is CrawlSessionsReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || typeof v.custom !== "boolean" || !Array.isArray(v.sessions) || v.sessions.length > 50) return false;
  return v.sessions.every(s => object(s) && typeof s.id === "string" && stamp(s.started_at) && nullableStamp(s.stopped_at) &&
    typeof s.running === "boolean" && num(s.duration_seconds) && counts(s, ["worker_count", "peak_concurrency"]) &&
    Array.isArray(s.hosts) && s.hosts.every(h => typeof h === "string") && isWork(s.work) &&
    Array.isArray(s.workers) && s.workers.every(w => object(w) && typeof w.id === "string" && typeof w.hostname === "string" &&
      count(w.pid) && stamp(w.started_at) && nullableStamp(w.stopped_at) && typeof w.crashed === "boolean" && count(w.concurrency)));
}
