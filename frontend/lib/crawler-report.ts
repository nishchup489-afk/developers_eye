export type CrawlerSource = { id: number; slug: string; name: string; kind: string; enabled: boolean; targets: number; documents: number; attempts: number; successful: number; failed: number };
export type CrawlError = { attempt_id: number; target_id: number; source: string; url: string; outcome: "failed" | "blocked"; http_status: number | null; error: string | null; started_at: string; finished_at: string | null };
export type DailyAttempts = { date: string; attempts: number; successful: number; failed: number; blocked: number };
export type CrawlerReport = {
  generated_at: string;
  window: { days: number; start_utc: string; end_utc: string };
  sources: { total: number; enabled: number; disabled: number };
  frontier: { total: number; by_state: { queued: number; leased: number; blocked: number; disabled: number }; queued_due: number; queued_scheduled: number; leases_active: number; leases_expired: number };
  documents: { total: number; seen_in_window: number; updated_in_window: number; indexed: number; not_indexed: number; stale_index_hashes: number };
  robots_cache: { origins: number; valid: number; expired: number };
  attempts: { total_in_window: number; finished_in_window: number; by_outcome: { success: number; failed: number; blocked: number; not_modified: number; unfinished: number }; success_rate_percent: number | null; last_attempt_at: string | null; last_success_at: string | null };
  daily_attempts: DailyAttempts[];
  top_sources: CrawlerSource[];
  recent_errors: CrawlError[];
};

function record(value: unknown): value is Record<string, unknown> { return Boolean(value && typeof value === "object" && !Array.isArray(value)); }
function count(value: unknown): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0; }
function counts(value: unknown, keys: string[]) { return record(value) && keys.every((key) => count(value[key])); }
function timestamp(value: unknown): value is string { return typeof value === "string" && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)); }
function nullableTimestamp(value: unknown) { return value === null || timestamp(value); }
export function safeHttpUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; } catch { return null; }
}

// Validate at the server boundary so incomplete reports never become invented zeroes.
export function isCrawlerReport(value: unknown): value is CrawlerReport {
  if (!record(value) || !timestamp(value.generated_at) || !record(value.window) || !count(value.window.days) || value.window.days < 1 || value.window.days > 365 || !timestamp(value.window.start_utc) || !timestamp(value.window.end_utc)) return false;
  if (!counts(value.sources, ["total", "enabled", "disabled"]) || !counts(value.frontier, ["total", "queued_due", "queued_scheduled", "leases_active", "leases_expired"]) || !record(value.frontier) || !counts(value.frontier.by_state, ["queued", "leased", "blocked", "disabled"])) return false;
  if (!counts(value.documents, ["total", "seen_in_window", "updated_in_window", "indexed", "not_indexed", "stale_index_hashes"]) || !counts(value.robots_cache, ["origins", "valid", "expired"])) return false;
  if (!counts(value.attempts, ["total_in_window", "finished_in_window"]) || !record(value.attempts) || !counts(value.attempts.by_outcome, ["success", "failed", "blocked", "not_modified", "unfinished"]) || !nullableTimestamp(value.attempts.last_attempt_at) || !nullableTimestamp(value.attempts.last_success_at)) return false;
  const rate = value.attempts.success_rate_percent;
  if (rate !== null && !(typeof rate === "number" && Number.isFinite(rate) && rate >= 0 && rate <= 100)) return false;
  if (!Array.isArray(value.daily_attempts) || value.daily_attempts.length !== value.window.days || !value.daily_attempts.every((day) => counts(day, ["attempts", "successful", "failed", "blocked"]) && record(day) && typeof day.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(day.date) && Number.isFinite(Date.parse(day.date)))) return false;
  if (!Array.isArray(value.top_sources) || value.top_sources.length > 100 || !value.top_sources.every((source) => counts(source, ["id", "targets", "documents", "attempts", "successful", "failed"]) && record(source) && [source.slug, source.name, source.kind].every((s) => typeof s === "string") && typeof source.enabled === "boolean")) return false;
  return Array.isArray(value.recent_errors) && value.recent_errors.length <= 100 && value.recent_errors.every((error) => record(error) && counts(error, ["attempt_id", "target_id"]) && typeof error.source === "string" && typeof error.url === "string" && ["failed", "blocked"].includes(String(error.outcome)) && (error.http_status === null || (count(error.http_status) && error.http_status >= 100 && error.http_status <= 599)) && (error.error === null || typeof error.error === "string") && timestamp(error.started_at) && nullableTimestamp(error.finished_at));
}
