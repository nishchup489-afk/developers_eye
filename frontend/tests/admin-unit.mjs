import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { adminConfig, cookieOptions, seal, unseal, userFromSession } from "../lib/admin-session.ts";
import { isCrawlerReport, safeHttpUrl } from "../lib/crawler-report.ts";
import { fixture } from "./fixtures/crawler-report.mjs";

const names = ["ADMIN_SESSION_SECRET", "ADMIN_APP_URL", "ADMIN_GITHUB_IDS", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"];
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
