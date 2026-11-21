"use client";

import { useState } from "react";
import { CalendarRange, ChevronRight, CircleAlert, Clock, Database, FileStack, Gauge, Link2, Loader2, Pause, Play, RefreshCw, ShieldCheck, TimerReset, Users } from "lucide-react";
import { isCrawlSessionsReport, type CrawlSession } from "@/lib/crawler-sessions";
import { Empty, Panel, usePolling } from "./crawler-control-center";
import { Tone } from "./system-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const stamp = (value: string | null) => value ? new Date(value).toLocaleString() : "—";
function duration(seconds: number) {
  const s = Math.round(seconds), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
}
function bytes(value: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = value, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toLocaleString("en-US", { maximumFractionDigits: i ? 1 : 0 })} ${units[i]}`;
}
// datetime-local has no timezone; read it as the admin's local time.
const toIso = (local: string) => local && !Number.isNaN(Date.parse(local)) ? new Date(local).toISOString() : "";

export default function CrawlSessions() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0);
  const [draft, setDraft] = useState({ start: "", end: "" }), [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const query = range ? `start=${encodeURIComponent(range.start)}${range.end ? `&end=${encodeURIComponent(range.end)}` : ""}` : "limit=20";
  const report = usePolling(`/api/admin/crawler/sessions?${query}`, isCrawlSessionsReport, 15000, auto, refresh);
  const r = report.data;
  const current = r?.sessions.find(s => s.id === selected) ?? r?.sessions[0];
  const rangeError = draft.start && draft.end && toIso(draft.end) <= toIso(draft.start) ? "The end time must be after the start time." : "";
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Sessions</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><TimerReset size={12} /> CRAWL SESSION REPORT</div><h1>From start.<br /><span>To stop</span><span className="admin-heading-dot">.</span></h1><p>Everything the crawler did between starting and stopping, summed across every worker. Workers whose lifetimes overlap count as one session.</p></div></div>
      <div className="cc-control-bar">
        <label><span>From</span><input type="datetime-local" value={draft.start} aria-label="Session start" onChange={e => setDraft(d => ({ ...d, start: e.target.value }))} /></label>
        <label><span>To</span><input type="datetime-local" value={draft.end} aria-label="Session end (leave empty for now)" onChange={e => setDraft(d => ({ ...d, end: e.target.value }))} /></label>
        <button className="admin-button secondary" disabled={!draft.start || Boolean(rangeError)} onClick={() => { setRange({ start: toIso(draft.start), end: toIso(draft.end) }); setSelected(null); }}><CalendarRange size={13} /> Report this window</button>
        {range && <button className="admin-button secondary" onClick={() => { setRange(null); setDraft({ start: "", end: "" }); setSelected(null); }}>Back to sessions</button>}
        <div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 15s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh sessions" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div>
      </div>
      {rangeError && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>Check the window</strong><p>{rangeError}</p></div></div>}
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "Session data is unavailable"}</strong><p>{report.error}</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      {r ? <>
        {!r.custom && <SessionList sessions={r.sessions} current={current?.id} onSelect={setSelected} />}
        {current ? <SessionDetail session={current} custom={r.custom} /> : <Panel title="No sessions yet"><Empty>No crawler worker has run yet. Start the crawler and its session appears here.</Empty></Panel>}
      </> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading crawl sessions.</div>}
    </main>
  </>;
}

function SessionList({ sessions, current, onSelect }: { sessions: CrawlSession[]; current?: string; onSelect: (id: string) => void }) {
  if (!sessions.length) return null;
  return <Panel title="Sessions" eyebrow={`LAST ${sessions.length} START → STOP RUNS`}>
    <div className="cc-table-wrap" role="region" aria-label="Crawl sessions" tabIndex={0}><table className="cc-table" role="table"><caption>Each crawler run from start to stop. Select one to see its full report.</caption>
      <thead><tr><th scope="col">Started</th><th scope="col">Stopped</th><th scope="col">Duration</th><th scope="col">Workers</th><th scope="col">Attempts</th><th scope="col">Docs stored</th><th scope="col">Success</th><th scope="col"><span className="sr-only">Open</span></th></tr></thead>
      <tbody>{sessions.map(s => <tr key={s.id} aria-selected={s.id === current} className={s.id === current ? "active" : undefined}>
        <td>{stamp(s.started_at)}</td>
        <td data-label="Stopped">{s.running ? <Tone value="running" status="ok" /> : stamp(s.stopped_at)}</td>
        <td data-label="Duration">{duration(s.duration_seconds)}</td>
        <td data-label="Workers">{n(s.worker_count)}</td>
        <td data-label="Attempts">{n(s.work.attempts)}</td>
        <td data-label="Docs stored">{n(s.work.documents_stored)}</td>
        <td data-label="Success">{metric(s.work.success_percent, "%")}</td>
        <td><button className="admin-button secondary" onClick={() => onSelect(s.id)} aria-label={`Open session started ${stamp(s.started_at)}`}>View</button></td>
      </tr>)}</tbody></table></div>
  </Panel>;
}

function SessionDetail({ session: s, custom }: { session: CrawlSession; custom: boolean }) {
  const w = s.work;
  const cards = [
    { label: "Duration", value: duration(s.duration_seconds), note: `${stamp(s.started_at)} → ${s.running ? "now (running)" : stamp(s.stopped_at)}`, icon: <Clock size={16} /> },
    { label: "Pages attempted", value: n(w.attempts), note: `${metric(w.attempts_per_minute, "/min")} across all workers`, icon: <Gauge size={16} /> },
    { label: "Documents stored", value: n(w.documents_stored), note: `from ${n(w.attempts_stored)} pages`, icon: <FileStack size={16} /> },
    { label: "Success rate", value: metric(w.success_percent, "%"), note: `${n(w.successful)} HTTP 2xx / 304`, icon: <ShieldCheck size={16} /> },
    { label: "Links found", value: n(w.links_discovered), note: `${n(w.links_enqueued)} new links queued`, icon: <Link2 size={16} /> },
    { label: "Downloaded", value: bytes(w.bytes_received), note: `${n(w.sources)} source${w.sources === 1 ? "" : "s"} touched`, icon: <Database size={16} /> },
    { label: "Workers", value: n(s.worker_count), note: `${n(s.peak_concurrency)} total concurrency · ${s.hosts.join(", ") || "—"}`, icon: <Users size={16} /> },
  ];
  const outcomes: [string, number, "ok" | "warning" | "critical" | "info"][] = [
    ["finished", w.finished, "ok"], ["not modified", w.not_modified, "info"], ["failed", w.failed, "critical"],
    ["blocked", w.blocked, "warning"], ["timeouts", w.timeouts, "warning"], ["stale", w.stale, "warning"],
  ];
  return <>
    <Panel title={custom ? "Custom window" : s.running ? "Current session" : "Session report"} eyebrow={s.running ? "LIVE · UPDATES EVERY 15S" : "TOTAL WORK, ALL WORKERS"}>
      <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>
      <p className="cc-note">Outcomes: {outcomes.map(([label, value, status]) => <Tone key={label} value={`${n(value)} ${label}`} status={value ? status : "info"} />)} · Fetch time mean {metric(w.avg_fetch_ms, " ms")}, p95 {metric(w.p95_fetch_ms, " ms")}.</p>
    </Panel>
    <Panel title="Work by source" eyebrow="TOP 15 SOURCES IN THIS SESSION">
      {w.by_source.length ? <div className="cc-table-wrap" role="region" aria-label="Work by source" tabIndex={0}><table className="cc-table" role="table"><caption>Attempts and stored documents per source.</caption>
        <thead><tr><th scope="col">Source</th><th scope="col">Attempts</th><th scope="col">Successful</th><th scope="col">Failed / blocked</th><th scope="col">Docs stored</th></tr></thead>
        <tbody>{w.by_source.map(src => <tr key={src.slug}><td>{src.slug}</td><td data-label="Attempts">{n(src.attempts)}</td><td data-label="Successful">{n(src.successful)}</td><td data-label="Failed / blocked">{n(src.errors)}</td><td data-label="Docs stored">{n(src.documents_stored)}</td></tr>)}</tbody></table></div>
        : <Empty>No crawl attempts in this session.</Empty>}
    </Panel>
    <Panel title="Workers" eyebrow="PROCESSES IN THIS SESSION">
      {s.workers.length ? <div className="cc-table-wrap" role="region" aria-label="Session workers" tabIndex={0}><table className="cc-table" role="table"><caption>Crawler processes alive during this session.</caption>
        <thead><tr><th scope="col">Worker</th><th scope="col">Host / PID</th><th scope="col">Started</th><th scope="col">Stopped</th><th scope="col">Concurrency</th></tr></thead>
        <tbody>{s.workers.map(wk => <tr key={wk.id}><td>{wk.id}</td><td data-label="Host / PID">{wk.hostname} · {wk.pid}</td><td data-label="Started">{stamp(wk.started_at)}</td><td data-label="Stopped">{wk.crashed ? <Tone value="no stop record" status="warning" /> : wk.stopped_at ? stamp(wk.stopped_at) : <Tone value="running" status="ok" />}</td><td data-label="Concurrency">{n(wk.concurrency)}</td></tr>)}</tbody></table></div>
        : <Empty>No worker was alive during this window.</Empty>}
    </Panel>
  </>;
}
