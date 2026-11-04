"use client";

import { useState } from "react";
import { ArrowDownToLine, ChevronRight, CircleAlert, Database, Gauge, HardDrive, Loader2, Pause, Play, RefreshCw, ShieldCheck, Target, Timer } from "lucide-react";
import { bytes, eta, isSystemReport, type SystemReport } from "@/lib/system-report";
import { Empty, Panel, usePolling } from "./crawler-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}${suffix}`;
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Never";
const tabs = [["capacity", "Capacity"], ["progress", "Progress & yield"], ["tables", "Tables"], ["database", "Database"]];
const tone = (status: string) => status === "critical" ? "red" : status === "warning" ? "amber" : "green";

export function Tone({ value, status }: { value: string; status: "ok" | "warning" | "critical" | "info" }) {
  return <span className={`cc-badge ${status === "info" ? "amber" : tone(status)}`}>{value}</span>;
}

function Meter({ label, value, max, mark, note }: { label: string; value: number; max: number; mark?: number; note: string }) {
  const width = max ? Math.min(100, 100 * value / max) : 0;
  return <div className="sys-meter">
    <div><span>{label}</span><strong>{note}</strong></div>
    <div className="cc-funnel-track sys-meter-track">{mark !== undefined && max > 0 && <em style={{ left: `${Math.min(100, 100 * mark / max)}%` }} aria-hidden="true" />}<i style={{ width: `${width}%` }} /></div>
  </div>;
}

export default function SystemControlCenter() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [days, setDays] = useState(7), [tab, setTab] = useState("capacity");
  // Capacity numbers move slowly; a 30 s refresh keeps catalog queries cheap on a small VM.
  const report = usePolling(`/api/admin/system/report?days=${days}`, isSystemReport, 30000, auto, refresh);
  const r = report.data;
  function download() {
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = `system-snapshot-${new Date().toISOString().slice(0, 10)}.json`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>System</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><HardDrive size={12} /> CAPACITY & PROGRESS</div><h1>Will it fit.<br /><span>On the free tier</span><span className="admin-heading-dot">.</span></h1><p>Database size against the disk budget, the road to the document goal, and which sources earn their crawl.</p></div><div className="cc-heading-actions">{r && <Tone value={`Budget ${r.budget.status}`} status={r.budget.status} />}<button className="admin-button secondary" onClick={download} disabled={!r}><ArrowDownToLine size={15} /> Export snapshot</button></div></div>
      <div className="cc-control-bar"><label><span>Yield window</span><select value={days} aria-label="Yield window" onChange={e => setDays(Number(e.target.value))}><option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option></select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 30s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "System data is unavailable"}</strong><p>{report.error}</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      {r && <Cards report={r} />}
      <nav className="cc-tabs" aria-label="System sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {r ? <>
        {tab === "capacity" && <div className="cc-grid cc-grid-equal"><Capacity report={r} /><PerDocument report={r} /></div>}
        {tab === "progress" && <><Progress report={r} /><Yield report={r} /></>}
        {tab === "tables" && <Tables report={r} />}
        {tab === "database" && <div className="cc-grid cc-grid-equal"><Connections report={r} /><Telemetry report={r} /><SlowQueries report={r} /></div>}
      </> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading system snapshot.</div>}
    </main>
  </>;
}

function Cards({ report: r }: { report: SystemReport }) {
  const b = r.budget, p = r.progress;
  const cards = [
    { label: "Database size", value: bytes(b.used_bytes), note: `${metric(b.used_percent, "%")} of ${bytes(b.budget_bytes)} budget`, icon: <Database size={16} /> },
    { label: "Per document", value: bytes(b.bytes_per_document), note: `Target ${bytes(b.target_bytes_per_document)} to fit the goal`, icon: <Gauge size={16} /> },
    { label: "Projected at goal", value: bytes(b.projected_bytes_at_target), note: `${metric(b.projected_percent_of_budget, "%")} of budget at ${n(b.target_documents)} docs`, icon: <HardDrive size={16} /> },
    { label: "Documents", value: n(p.documents), note: `${metric(p.percent, "%")} of ${n(p.target_documents)}`, icon: <Target size={16} /> },
    { label: "New per day", value: n(p.per_day), note: `${n(p.new_last_hour)} in the last hour`, icon: <Timer size={16} /> },
    { label: "ETA to goal", value: eta(p.eta_days), note: p.eta_at ? new Date(p.eta_at).toLocaleDateString() : "Needs a crawl rate", icon: <Timer size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}

function Capacity({ report: r }: { report: SystemReport }) {
  const b = r.budget;
  const scale = Math.max(b.budget_bytes, b.projected_bytes_at_target ?? 0);
  const fits = b.documents_that_fit;
  return <Panel title="Disk budget" eyebrow={`${bytes(b.budget_bytes)} BUDGET · WARN AT 80%`} action={<Tone value={b.status} status={b.status} />}>
    <div className="cc-funnel">
      <Meter label="Used now" value={b.used_bytes} max={b.budget_bytes} mark={b.warn_at_bytes} note={`${bytes(b.used_bytes)} · ${metric(b.used_percent, "%")}`} />
      {b.projected_bytes_at_target !== null && <Meter label={`Projected at ${n(b.target_documents)} documents`} value={b.projected_bytes_at_target} max={scale} mark={b.budget_bytes} note={`${bytes(b.projected_bytes_at_target)} · ${metric(b.projected_percent_of_budget, "%")}`} />}
    </div>
    <p className="cc-note">{fits === null ? "No documents yet, so there is no per-document size to project from." : fits >= b.target_documents
      ? `At ${bytes(b.bytes_per_document)} per document the budget holds about ${n(fits)} documents, which covers the goal.`
      : `At ${bytes(b.bytes_per_document)} per document the budget holds about ${n(fits)} documents. Reaching ${n(b.target_documents)} needs about ${bytes(b.target_bytes_per_document)} per document.`}</p>
    <p className="cc-note">The marker on the first bar is the 80% warning line. On the second bar it is the budget itself. Sizes include indexes and TOAST.</p>
  </Panel>;
}

function PerDocument({ report: r }: { report: SystemReport }) {
  const rows = Object.entries(r.per_document_bytes).filter(([, v]) => v !== null).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  const max = Math.max(1, ...rows.map(([, v]) => v ?? 0));
  return <Panel title="Where each document's bytes go" eyebrow="TABLE SIZE ÷ DOCUMENTS">
    {rows.length ? <div className="cc-funnel">{rows.map(([name, value]) => <Meter key={name} label={name} value={value ?? 0} max={max} note={bytes(value)} />)}</div> : <Empty>No documents stored yet.</Empty>}
    <p className="cc-note">Crawl history (crawl_attempt, crawl_event) counts toward the budget too. Purging old events is the cheapest saving.</p>
  </Panel>;
}

function Progress({ report: r }: { report: SystemReport }) {
  const p = r.progress;
  return <Panel title="Progress to the document goal" eyebrow="NEW DOCUMENTS = DEDUP 'NEW' CHECKPOINTS">
    <div className="cc-funnel"><Meter label={`${n(p.documents)} of ${n(p.target_documents)} documents`} value={p.documents} max={p.target_documents} note={metric(p.percent, "%")} /></div>
    <p className="cc-note">{p.remaining === 0 ? "The goal is reached." : p.per_day ? `${n(p.remaining)} to go at ${n(p.per_day)} new documents per day (last 24 hours).` : "No new documents in the last 24 hours, so there is no ETA."} {n(p.available_documents)} documents are currently available for search.</p>
  </Panel>;
}

function Yield({ report: r }: { report: SystemReport }) {
  return <Panel title="Source yield" eyebrow={`STORED ATTEMPTS ÷ ATTEMPTS · LAST ${r.window_days} DAY${r.window_days === 1 ? "" : "S"}`}><div className="cc-table-wrap" role="region" aria-label="Source yield records" tabIndex={0}><table className="cc-table" role="table"><caption>Crawl attempts, how many stored content, duplicates and body size for each source.</caption><thead><tr><th scope="col">Source</th><th scope="col">Attempts</th><th scope="col">Yield</th><th scope="col">Failed / blocked</th><th scope="col">Documents</th><th scope="col">Duplicates</th><th scope="col">Avg body</th><th scope="col">Downloaded</th></tr></thead><tbody>{r.sources.map(s => <tr key={s.id}><td>{s.name}<small>{s.slug} · {s.enabled ? "enabled" : "disabled"}</small></td><td data-label="Attempts">{n(s.attempts)}</td><td data-label="Yield">{metric(s.yield_percent, "%")}<small>{n(s.stored_attempts)} stored</small></td><td data-label="Failed / blocked">{n(s.failed)} / {n(s.blocked)}</td><td data-label="Documents">{n(s.documents)}</td><td data-label="Duplicates">{n(s.duplicate_documents)}<small>{metric(s.duplicate_percent, "%")} same content hash</small></td><td data-label="Avg body">{s.average_body_characters == null ? "N/A" : `${n(s.average_body_characters)} chars`}</td><td data-label="Downloaded">{bytes(s.bytes_received)}</td></tr>)}</tbody></table></div>{!r.sources.length && <Empty>No sources are registered.</Empty>}</Panel>;
}

function Tables({ report: r }: { report: SystemReport }) {
  return <Panel title="Table sizes" eyebrow="LARGEST 30 TABLES · ROW COUNTS ARE PLANNER ESTIMATES"><div className="cc-table-wrap" role="region" aria-label="Table size records" tabIndex={0}><table className="cc-table" role="table"><caption>Size, estimated rows and vacuum state per table.</caption><thead><tr><th scope="col">Table</th><th scope="col">Total</th><th scope="col">Heap / index / TOAST</th><th scope="col">Rows (est.)</th><th scope="col">Dead rows</th><th scope="col">Last vacuum</th></tr></thead><tbody>{r.tables.map(t => <tr key={t.name}><td>{t.name}</td><td data-label="Total">{bytes(t.total_bytes)}</td><td data-label="Heap / index / TOAST">{bytes(t.heap_bytes)} / {bytes(t.index_bytes)} / {bytes(t.toast_bytes)}</td><td data-label="Rows (est.)">{n(t.estimated_rows)}</td><td data-label="Dead rows">{n(t.dead_rows)}<small>{metric(t.dead_percent, "%")}</small></td><td data-label="Last vacuum">{time(t.last_vacuum_at)}</td></tr>)}</tbody></table></div></Panel>;
}

function Connections({ report: r }: { report: SystemReport }) {
  const d = r.database;
  return <Panel title="Connections" eyebrow="THIS DATABASE · pg_stat_activity"><div className="cc-funnel"><Meter label="Open connections" value={d.connections_used} max={d.connections_max} note={`${n(d.connections_used)} of ${n(d.connections_max)}`} /></div><p className="cc-note">{n(d.connections_active)} running a query right now. Each crawler process holds its own pool, so 30 workers can approach the limit.</p></Panel>;
}

function Telemetry({ report: r }: { report: SystemReport }) {
  const t = r.telemetry;
  return <Panel title="Crawl event retention" eyebrow={`KEEP ${t.retention_days} DAYS`} action={<Tone value={t.events_past_retention ? "purge due" : "ok"} status={t.events_past_retention ? "warning" : "ok"} />}><p className="cc-note">About {n(t.estimated_event_rows)} event rows. Oldest: {time(t.oldest_event_at)}. {n(t.events_past_retention)} are older than {t.retention_days} days.</p><p className="cc-note">Purge them with <code>python -m backend.admin_services.maintenance --purge-events</code> (run daily). Attempts keep their summary, so charts are unaffected.</p></Panel>;
}

function SlowQueries({ report: r }: { report: SystemReport }) {
  return <Panel title="Slowest queries" eyebrow="pg_stat_statements · BY TOTAL TIME">{r.slow_queries === null ? <Empty>Not available. Administrators see this when pg_stat_statements is in shared_preload_libraries and the extension is created.</Empty> : r.slow_queries.length ? <div className="cc-table-wrap"><table className="cc-table"><thead><tr><th scope="col">Query</th><th scope="col">Calls</th><th scope="col">Mean</th><th scope="col">Total</th></tr></thead><tbody>{r.slow_queries.map((q, i) => <tr key={i}><td><code>{q.query}</code></td><td data-label="Calls">{n(q.calls)}</td><td data-label="Mean">{metric(q.mean_ms, " ms")}</td><td data-label="Total">{metric(q.total_ms / 1000, " s")}</td></tr>)}</tbody></table></div> : <Empty>No statements recorded yet.</Empty>}</Panel>;
}
