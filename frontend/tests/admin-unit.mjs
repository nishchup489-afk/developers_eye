import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { adminConfig, cookieOptions, roleFor, seal, unseal, userFromSession, viewerFromSession } from "../lib/admin-session.ts";
import { bytes, eta, isCorpusReport, isHostReport, isProblemsReport, isSearchReport, isSystemReport, redactSearchReport, redactSystemReport } from "../lib/system-report.ts";
import { corpusFixture, hostsFixture, problemsFixture, searchFixture, systemFixture } from "./fixtures/system-report.mjs";
import { isCrawlerReport, safeHttpUrl } from "../lib/crawler-report.ts";
import { fixture } from "./fixtures/crawler-report.mjs";

const names = ["ADMIN_SESSION_SECRET", "ADMIN_APP_URL", "ADMIN_GITHUB_IDS", "ADMIN_VIEWER_GITHUB_IDS", "ADMIN_VIEWER_ACCESS", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"];
const previous = Object.fromEntries(names.map((name) => [name, process.env[name]]));
try {
  Object.assign(process.env, { ADMIN_SESSION_SECRET: randomBytes(32).toString("hex"), ADMIN_APP_URL: "http://localhost:3000", ADMIN_GITHUB_IDS: "42, 73", GITHUB_CLIENT_ID: "test", GITHUB_CLIENT_SECRET: "test" });
  assert.equal(adminConfig().ready, true);
  const identity = { id: 42, login: "admin-user", name: "Admin" };
  const token = seal(identity, "session", 60);
  assert.deepEqual(userFromSession(token), identity);
  assert.equal(userFromSession(undefined), null);
  assert.equal(userFromSession(`${token}!`), null);
  assert.equal(userFromSession(`x.${token.split(".")[1]}`), null);
  assert.equal(userFromSession(seal(identity, "session", -1)), null);
  assert.equal(userFromSession(seal(identity, "oauth", 60)), null);
  assert.equal(userFromSession(seal({ ...identity, id: 999 }, "session", 60)), null);
  assert.equal(userFromSession(seal({ ...identity, login: "<script>" }, "session", 60)), null);
  assert.equal(userFromSession(seal({ ...identity, id: "42" }, "session", 60)), null);
  const flow = seal({ state: "state", verifier: "verifier" }, "oauth", 600);
  assert.equal(unseal(flow, "oauth").verifier, "verifier");
  assert.equal(unseal(flow, "session"), null);
  process.env.ADMIN_GITHUB_IDS = "73";
  assert.equal(userFromSession(token), null);
  process.env.ADMIN_GITHUB_IDS = "";
  assert.equal(adminConfig().ready, false);
  process.env.ADMIN_GITHUB_IDS = "42";
  process.env.ADMIN_APP_URL = "http://public.example.com";
  assert.equal(adminConfig().ready, false);
  process.env.ADMIN_APP_URL = "https://admin.example.com";
  assert.equal(cookieOptions(60).secure, true);
  assert.equal(cookieOptions(60).httpOnly, true);
  assert.equal(cookieOptions(60).sameSite, "lax");
  process.env.ADMIN_SESSION_SECRET = "short";
  assert.equal(userFromSession(token), null);
  assert.throws(() => seal(identity, "session", 60));
  console.log("PASS admin session signing, expiry, purpose isolation, tampering, allowlist revocation, fail-closed config, cookie flags");

  // Read-only roles: admins stay admins, listed viewers read only, guests only in public mode.
  Object.assign(process.env, { ADMIN_SESSION_SECRET: randomBytes(32).toString("hex"), ADMIN_APP_URL: "http://localhost:3000", ADMIN_GITHUB_IDS: "42", ADMIN_VIEWER_GITHUB_IDS: "77", ADMIN_VIEWER_ACCESS: "off" });
  const admin = seal(identity, "session", 60), viewer = seal({ id: 77, login: "viewer-user", name: null }, "session", 60), stranger = seal({ id: 99, login: "someone", name: null }, "session", 60);
  assert.deepEqual(viewerFromSession(admin), { ...identity, role: "admin" });
  assert.deepEqual(viewerFromSession(viewer), { id: 77, login: "viewer-user", name: null, role: "viewer" });
  assert.equal(userFromSession(viewer), null, "a viewer is never an administrator");
  assert.equal(viewerFromSession(stranger), null);
  assert.equal(viewerFromSession(undefined), null);
  assert.equal(roleFor(42), "admin"); assert.equal(roleFor(77), "viewer"); assert.equal(roleFor(99), null);
  process.env.ADMIN_VIEWER_ACCESS = "github";
  assert.equal(viewerFromSession(stranger).role, "viewer");
  assert.equal(viewerFromSession(seal({ id: 99, login: "<bad>", name: null }, "session", 60)), null);
  process.env.ADMIN_VIEWER_ACCESS = "public";
  assert.deepEqual(viewerFromSession(undefined), { id: null, login: null, name: null, role: "guest" });
  assert.equal(viewerFromSession(admin).role, "admin");
  assert.equal(userFromSession(undefined), null, "public mode never grants admin");
  process.env.ADMIN_VIEWER_ACCESS = "PUBLIC ";
  assert.equal(adminConfig().viewerAccess, "public");
  process.env.ADMIN_VIEWER_ACCESS = "everyone";
  assert.equal(adminConfig().viewerAccess, "off");
  assert.equal(viewerFromSession(undefined), null);
  process.env.ADMIN_VIEWER_ACCESS = "off"; process.env.ADMIN_VIEWER_GITHUB_IDS = "";
  assert.equal(viewerFromSession(viewer), null, "removing a viewer id revokes access at once");
  console.log("PASS read-only roles: admin, listed viewers, any-GitHub viewers, public guests, revocation, unknown modes fail closed");

  assert.equal(isSystemReport(systemFixture()), true);
  assert.equal(isHostReport(hostsFixture()), true);
  assert.equal(isProblemsReport(problemsFixture()), true);
  const systemMutations = [(r) => { r.budget.status = "fine"; }, (r) => { r.tables[0].total_bytes = -1; }, (r) => { r.progress.percent = 101; }, (r) => { delete r.telemetry; }, (r) => { r.slow_queries = "x"; }];
  for (const mutate of systemMutations) { const r = systemFixture(); mutate(r); assert.equal(isSystemReport(r), false); }
  const hostMutations = [(r) => { r.hosts[0].flags = ["banned"]; }, (r) => { r.hosts[0].requests_per_minute = -1; }, (r) => { r.online_workers = 1.5; }];
  for (const mutate of hostMutations) { const r = hostsFixture(); mutate(r); assert.equal(isHostReport(r), false); }
  const badProblems = problemsFixture(); badProblems.problems[0].severity = "panic"; assert.equal(isProblemsReport(badProblems), false);
  const empty = systemFixture(); Object.assign(empty.budget, { bytes_per_document: null, projected_bytes_at_target: null, projected_percent_of_budget: null, documents_that_fit: null }); empty.progress.eta_days = null; empty.progress.eta_at = null; empty.slow_queries = null;
  assert.equal(isSystemReport(empty), true);
  assert.equal(redactSystemReport(systemFixture(), "viewer").slow_queries, null);
  assert.equal(redactSystemReport(systemFixture(), "guest").slow_queries, null);
  assert.equal(redactSystemReport(systemFixture(), "admin").slow_queries.length, 1);
  assert.equal(bytes(1372585984), "1.3 GB"); assert.equal(bytes(166.3 * 1024 ** 3), "166 GB"); assert.equal(eta(688.6), "1.9 years"); assert.equal(eta(12.4), "12 days"); assert.equal(eta(0), "Reached"); assert.equal(eta(null), "N/A"); assert.equal(bytes(512), "512 B"); assert.equal(bytes(null), "N/A");
  assert.equal(isCorpusReport(corpusFixture()), true);
  const corpusMutations = [(r) => { delete r.estimates; }, (r) => { r.summary.total_documents = -1; }, (r) => { r.hosts = Array(51).fill(r.hosts[0]); }, (r) => { r.freshness.seen[0].share_percent = 101; }, (r) => { r.vocabulary.exact = "no"; }];
  for (const mutate of corpusMutations) { const r = corpusFixture(); mutate(r); assert.equal(isCorpusReport(r), false); }
  assert.equal(isSearchReport(searchFixture()), true);
  const searchMutations = [(r) => { r.status = "fine"; }, (r) => { r.totals.availability_percent = 101; }, (r) => { delete r.recent; }, (r) => { r.timeline[0].requests = -1; }, (r) => { r.schema.up_to_date = "yes"; }];
  for (const mutate of searchMutations) { const r = searchFixture(); mutate(r); assert.equal(isSearchReport(r), false); }
  // A database outage still produces a report, full of nulls.
  const offline = searchFixture(); Object.assign(offline.database, { reachable: false, ping_ms: null, connections_used: null, connections_max: null }); Object.assign(offline.schema, { current: null, expected: null, up_to_date: null }); Object.assign(offline.snapshot, { loaded: false, documents: null, loaded_at: null, age_seconds: null }); offline.planner = []; offline.totals.availability_percent = null; offline.totals.p95_ms = null;
  assert.equal(isSearchReport(offline), true);
  assert.equal(redactSearchReport(searchFixture(), "admin").processes[0].process, "api-host:12:abc123");
  assert.equal(redactSearchReport(searchFixture(), "guest").processes[0].process, "API process 1");
  console.log("PASS system, host and problem report contracts, nullable projections, viewer redaction, byte formatting");

  for (const days of [7, 30, 90]) assert.equal(isCrawlerReport(fixture(days)), true);
  const mutations = [
    (report) => { delete report.documents; },
    (report) => { report.documents.total = -1; },
    (report) => { report.attempts.success_rate_percent = 101; },
    (report) => { report.frontier.by_state = {}; },
    (report) => { report.generated_at = "2026-10-20"; },
    (report) => { report.daily_attempts.pop(); },
    (report) => { report.top_sources[0].enabled = "yes"; },
    (report) => { report.recent_errors[0].http_status = 900; },
  ];
  for (const mutate of mutations) { const report = fixture(7); mutate(report); assert.equal(isCrawlerReport(report), false); }
  const noSamples = fixture(7);
  noSamples.attempts.success_rate_percent = null;
  noSamples.attempts.last_attempt_at = null;
  assert.equal(isCrawlerReport(noSamples), true);
  for (const url of ["javascript:alert(1)", "data:text/html,x", "https://user:pass@example.com", "https://", "/relative"]) assert.equal(safeHttpUrl(url), null);
  assert.equal(safeHttpUrl("https://docs.python.org/3/"), "https://docs.python.org/3/");
  console.log("PASS reporting contract, invalid/missing fields, nullable metrics, date ranges, safe external links");
} finally {
  for (const name of names) { if (previous[name] === undefined) delete process.env[name]; else process.env[name] = previous[name]; }
}
