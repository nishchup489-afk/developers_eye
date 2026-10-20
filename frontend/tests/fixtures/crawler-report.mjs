// Synthetic data for automated tests only. Never imported by the application.
export function fixture(days) {
  const now = new Date();
  const daily = Array.from({ length: days }, (_, i) => {
    const day = new Date(now); day.setUTCDate(day.getUTCDate() - days + 1 + i);
    return { date: day.toISOString().slice(0, 10), attempts: 10, successful: 8, failed: 1, blocked: 1 };
  });
  return {
    generated_at: now.toISOString(), window: { days, start_utc: `${daily[0].date}T00:00:00Z`, end_utc: now.toISOString() },
    sources: { total: 2, enabled: 1, disabled: 1 },
    frontier: { total: 100, by_state: { queued: 80, leased: 10, blocked: 8, disabled: 2 }, queued_due: 60, queued_scheduled: 20, leases_active: 9, leases_expired: 1 },
    documents: { total: 1000, seen_in_window: 200, updated_in_window: 100, indexed: 800, not_indexed: 200, stale_index_hashes: 20 },
    robots_cache: { origins: 2, valid: 1, expired: 1 },
    attempts: { total_in_window: days * 10, finished_in_window: days * 10, by_outcome: { success: days * 8, failed: days, blocked: days, not_modified: 0, unfinished: 0 }, success_rate_percent: 80, last_attempt_at: now.toISOString(), last_success_at: now.toISOString() },
    daily_attempts: daily,
    top_sources: [{ id: 1, slug: "python-docs", name: "Python Documentation", kind: "website", enabled: true, targets: 80, documents: 800, attempts: days * 10, successful: days * 8, failed: days }, { id: 2, slug: "mdn", name: "MDN Web Docs", kind: "website", enabled: false, targets: 20, documents: 200, attempts: 0, successful: 0, failed: 0 }],
    recent_errors: [{ attempt_id: 1, target_id: 2, source: "python-docs", url: "https://docs.python.org/3/missing", outcome: "failed", http_status: 404, error: "Page not found", started_at: now.toISOString(), finished_at: now.toISOString() }],
  };
}
