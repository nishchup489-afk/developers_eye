import assert from "node:assert/strict";
import { isCrawlMonitor, isAttemptDetail, isDocumentDetail } from "../lib/crawler-monitor.ts";
import { monitorFixture, documentFixture, attemptFixture } from "./fixtures/crawler-monitor.mjs";

assert.ok(isCrawlMonitor(monitorFixture()));
assert.ok(isDocumentDetail(documentFixture()));
assert.ok(isAttemptDetail(attemptFixture()));
for (const mutate of [
  m => { m.summary.fetch_p95_ms = "fast"; },
  m => { m.summary.persisted = -1; },
  m => { m.events[0].details = null; },
  m => { m.workers[0].active_targets[0].url = 4; },
  m => { m.throughput.pop(); },
  m => { m.documents_has_more = "yes"; },
  m => { m.frontier[0].next_fetch_at = "nope"; },
]) { const m = monitorFixture(); mutate(m); assert.equal(isCrawlMonitor(m), false); }
const empty = monitorFixture();
Object.assign(empty.summary, { fetch_p50_ms: null, fetch_p95_ms: null, storage_avg_ms: null, response_avg_bytes: null, fetch_success_percent: null });
empty.workers = []; empty.events = []; empty.documents = []; empty.frontier = [];
assert.ok(isCrawlMonitor(empty));
const doc = documentFixture(); doc.latest_attempt = { id: "bad" };
assert.equal(isDocumentDetail(doc), false);
assert.equal(isAttemptDetail({ ...attemptFixture(), telemetry: [] }), false);
console.log("PASS monitoring, worker, document and attempt contracts, null metrics and malformed responses");

const unavailable = documentFixture();
Object.assign(unavailable, { is_available: false, unavailable_http_status: 410, unavailable_at: new Date().toISOString() });
assert.ok(isDocumentDetail(unavailable));
unavailable.unavailable_http_status = "410";
assert.equal(isDocumentDetail(unavailable), false);
