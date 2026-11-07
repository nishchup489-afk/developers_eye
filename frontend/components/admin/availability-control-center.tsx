"use client";

import { useState } from "react";
import { Activity, ChevronRight, CircleAlert, Gauge, Hourglass, Loader2, Pause, Play, RefreshCw, ShieldCheck, Timer, Users } from "lucide-react";
import { isSearchReport, type SearchReport, type SearchStatus } from "@/lib/system-report";
import { Empty, Panel, usePolling } from "./crawler-control-center";
import { Tone } from "./system-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const ms = (value: number | null | undefined) => value == null ? "N/A" : value >= 1000 ? `${(value / 1000).toLocaleString("en-US", { maximumFractionDigits: 2 })} s` : `${Math.round(value)} ms`;
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Never";
const clock = (value: string) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const statusTone: Record<SearchStatus, "ok" | "warning" | "critical"> = { ok: "ok", degraded: "warning", down: "critical" };
const statusText: Record<SearchStatus, string> = { ok: "Search is healthy", degraded: "Search is degraded", down: "Search is down" };

export default function AvailabilityControlCenter() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [hours, setHours] = useState(24);
  const report = usePolling(`/api/admin/system/search?hours=${hours}`, isSearchReport, 15000, auto, refresh);
  const r = report.data;
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Availability</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><Activity size={12} /> SEARCH HEALTH & LATENCY</div><h1>Is search up.<br /><span>And is it fast</span><span className="admin-heading-dot">.</span></h1><p>What every API process saw: failures, timeouts against the deadline, latency, and the checks behind them.</p></div><div className="cc-heading-actions">{r && <Tone value={statusText[r.status]} status={statusTone[r.status]} />}</div></div>
      <div className="cc-control-bar"><label><span>Window</span><select value={hours} aria-label="Availability window" onChange={e => setHours(Number(e.target.value))}><option value={1}>Last hour</option><option value={6}>Last 6 hours</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option></select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 15s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "Availability data is unavailable"}</strong><p>{report.error}</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      {r ? <>
        {r.reasons.length > 0 && <div className="admin-alert" role="status"><CircleAlert size={19} /><div><strong>{statusText[r.status]}</strong>{r.reasons.map(reason => <p key={reason}>{reason}</p>)}</div></div>}
        {r.partial && <p className="cc-note cc-warning">The database is unreachable, so traffic below is only what this one API process still holds in memory.</p>}
        <Cards report={r} />
        <Timeline report={r} />
        <div className="cc-grid cc-grid-equal"><Failures report={r} /><Latency report={r} /></div>
        <div className="cc-grid cc-grid-equal"><Health report={r} /><Planner report={r} /></div>
        <Processes report={r} />
      </> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading availability snapshot.</div>}
    </main>
  </>;
}

function Cards({ report: r }: { report: SearchReport }) {
  const t = r.totals;
  const cards = [
    { label: "Availability", value: metric(t.availability_percent, "%"), note: `Target ${r.limits.availability_target_percent}% · ${metric(r.recent.availability_percent, "%")} last 15 min`, icon: <Activity size={16} /> },
    { label: "Searches", value: n(t.answered), note: `${n(t.invalid)} rejected as invalid, not counted`, icon: <Gauge size={16} /> },
    { label: "Timed out", value: n(t.timed_out), note: `${metric(t.timeout_percent, "%")} hit the ${ms(r.limits.deadline_ms)} limit`, icon: <Hourglass size={16} /> },
    { label: "p95 latency", value: ms(t.p95_ms), note: `p50 ${ms(t.p50_ms)} · p99 ${ms(t.p99_ms)}`, icon: <Timer size={16} /> },
    { label: "Busy rejections", value: n(t.busy), note: `${metric(t.busy_percent, "%")} over ${r.limits.max_concurrent_per_process} at once per process`, icon: <Users size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}

function Timeline({ report: r }: { report: SearchReport }) {
  const max = Math.max(1, ...r.timeline.map(t => t.requests));
  const failed = r.timeline.reduce((sum, t) => sum + t.failed, 0), step = r.window_hours * 60 / r.timeline.length;
  return <Panel title="Searches over time" eyebrow={`LAST ${r.window_hours} HOUR${r.window_hours === 1 ? "" : "S"}`} action={<span className="cc-panel-tag">{n(failed)} failed</span>}>
    <div className="cc-chart" role="img" aria-label={`${n(r.totals.answered)} searches in the window, ${n(failed)} failed. Peak ${n(max)} in one bar.`}><div className="cc-chart-scale"><span>{n(max)}</span><span>{n(Math.round(max / 2))}</span><span>0</span></div><div className="cc-bars sys-failure-bars">{r.timeline.map(t => <div key={t.at} title={`${clock(t.at)}: ${t.requests} searches, ${t.timed_out} timed out, ${t.busy} busy, ${t.failed - t.timed_out - t.busy} other failures, p95 ${ms(t.p95_ms)}`}><i style={{ height: `${100 * t.requests / max}%` }}><b style={{ height: `${t.requests ? 100 * (t.requests - t.failed) / t.requests : 0}%` }} /></i></div>)}</div></div>
    <div className="cc-chart-axis"><span>{clock(r.timeline[0].at)}</span><span>Each bar is {step >= 60 ? `${n(step / 60)} h` : `${n(step)} min`}</span><span>Now</span></div>
    <div className="cc-chart-legend sys-failure-bars"><span><i />Failed</span><span><i style={{ background: "var(--a-lime)" }} />Succeeded</span></div>
    {!r.recording && !r.partial && <p className="cc-note cc-warning">Nothing is recorded yet. Run alembic upgrade head to create the search_minute table.</p>}
  </Panel>;
}

function Failures({ report: r }: { report: SearchReport }) {
  const t = r.totals;
  const rows: [string, string, number][] = [
    ["Timed out", "503: a query passed the deadline", t.timed_out],
    ["Busy", "503: too many searches at once", t.busy],
    ["Database error", "503: the query failed or no connection was free", t.database_errors],
    ["Not ready", "503: the process has no BM25 snapshot", t.engine_errors],
    ["Server error", "500: an unexpected bug", t.server_errors],
  ];
  return <Panel title="Why searches failed" eyebrow="BY CAUSE" action={<Tone value={`${n(t.failed)} failed`} status={t.failed ? "warning" : "ok"} />}><ul className="sys-health">{rows.map(([label, detail, value]) => <li key={label}><span>{label}<small>{detail}</small></span><strong>{n(value)}</strong></li>)}</ul></Panel>;
}

function Latency({ report: r }: { report: SearchReport }) {
  const max = Math.max(1, ...r.latency.map(b => b.count));
  return <Panel title="Latency" eyebrow="SUCCESSFUL SEARCHES ONLY" action={<span className="cc-panel-tag">Mean {ms(r.totals.mean_ms)}</span>}><div className="cc-funnel">{r.latency.filter(b => b.count).map(b => <div key={b.le_ms ?? "over"}><div><span>{b.le_ms === null ? "Over 10 s" : `Up to ${ms(b.le_ms)}`}</span><strong>{n(b.count)}</strong></div><div className="cc-funnel-track"><i style={{ width: `${100 * b.count / max}%` }} /></div></div>)}</div>{!r.totals.successful && <Empty>No successful searches in this window.</Empty>}<p className="cc-note">Percentiles are estimated from these bars. The {ms(r.limits.deadline_ms)} limit applies to each database query, so a search with several queries can take longer overall.</p></Panel>;
}

function Health({ report: r }: { report: SearchReport }) {
  const d = r.database, c = r.schema, s = r.snapshot;
  const rows: { label: string; detail: string; value: string; status: "ok" | "warning" | "critical" | "info" }[] = [
    { label: "Database", detail: d.reachable ? `${n(d.connections_used ?? 0)} of ${n(d.connections_max ?? 0)} connections · ${metric(d.ping_ms, " ms")} ping` : "Did not answer", value: d.reachable ? "reachable" : "down", status: d.reachable ? "ok" : "critical" },
    { label: "Migrations", detail: c.up_to_date === false ? `On ${c.current ?? "none"}, code expects ${c.expected}` : c.current ?? "Unknown", value: c.up_to_date === null ? "unknown" : c.up_to_date ? "current" : "pending", status: c.up_to_date === null ? "info" : c.up_to_date ? "ok" : "warning" },
    { label: "BM25 snapshot", detail: s.loaded ? `${n(s.documents ?? 0)} documents, ${n(Math.round((s.age_seconds ?? 0) / 60))} min old, this process` : "Not loaded in this process", value: s.loaded ? "loaded" : "missing", status: s.loaded ? "ok" : "critical" },
  ];
  return <Panel title="Health checks" eyebrow="CHECKED ON EVERY REFRESH"><ul className="sys-health">{rows.map(row => <li key={row.label}><span>{row.label}<small>{row.detail}</small></span><Tone value={row.value} status={row.status} /></li>)}</ul></Panel>;
}

function Planner({ report: r }: { report: SearchReport }) {
  return <Panel title="Planner statistics" eyebrow="STALE STATISTICS CAUSE SEARCH TIMEOUTS">{r.planner.length ? <ul className="sys-health">{r.planner.map(t => <li key={t.table}><span>{t.table}<small>{n(t.modified_since_analyze)} rows changed since analyze · {metric(t.dead_percent, "%")} dead · analyzed {time(t.last_analyze_at)}</small></span><Tone value={t.status === "ok" ? "current" : "needs analyze"} status={t.status === "ok" ? "ok" : "warning"} /></li>)}</ul> : <Empty>Not available while the database is unreachable.</Empty>}<p className="cc-note">After a large migration or load, run VACUUM ANALYZE on these tables. Common-term searches can pass the deadline until it finishes.</p></Panel>;
}

function Processes({ report: r }: { report: SearchReport }) {
  return <Panel title="API processes" eyebrow="SEEN IN THIS WINDOW"><div className="cc-table-wrap" role="region" aria-label="API process records" tabIndex={0}><table className="cc-table" role="table"><caption>Searches answered by each API process.</caption><thead><tr><th scope="col">Process</th><th scope="col">Searches</th><th scope="col">Last seen</th></tr></thead><tbody>{r.processes.map(p => <tr key={p.process}><td>{p.process}</td><td data-label="Searches">{n(p.requests)}</td><td data-label="Last seen">{time(p.last_seen_at)}</td></tr>)}</tbody></table></div>{!r.processes.length && <Empty>No searches in this window.</Empty>}<p className="cc-note">A process that restarts appears as a new row.</p></Panel>;
}
