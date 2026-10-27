"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { Activity, ArrowDownToLine, ArrowRight, ChevronRight, CircleAlert, Database, FileSearch, Gauge, Layers3, Loader2, Pause, Play, Radio, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { isCrawlerReport, type CrawlerReport } from "@/lib/crawler-report";
import { isCrawlMonitor, object, type CrawlEvent, type CrawlMonitor } from "@/lib/crawler-monitor";
import { isIndexerReport, statusLabel, type IndexerReport } from "@/lib/indexer-report";
import CrawlInspector, { Badge, Url, type Inspection } from "./crawl-inspector";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "No activity";
const duration = (seconds: number) => seconds < 60 ? `${Math.floor(seconds)}s` : seconds < 3600 ? `${Math.floor(seconds / 60)}m` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
const tabs = [["overview", "Overview"], ["activity", "Live activity"], ["documents", "Documents"], ["frontier", "URL frontier"], ["sources", "Source health"], ["errors", "Errors"], ["workers", "Workers"]];

export function usePolling<T>(url: string, validate: (v: unknown) => v is T, interval: number, enabled: boolean, refresh: number) {
  const [snapshot, setSnapshot] = useState<{ url: string; data: T } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let stopped = false, busy = false;
    let controller: AbortController | null = null;
    async function load() {
      if (stopped || busy) return;
      busy = true; controller = new AbortController(); setLoading(true);
      try {
        const response = await fetch(url, { cache: "no-store", signal: controller.signal });
        const data: unknown = await response.json();
        if (!response.ok) throw new Error(response.status === 401 ? "Your admin session expired. Sign in again." : object(data) && typeof data.error === "string" ? data.error : "The report is unavailable.");
        if (!validate(data)) throw new Error("The service returned an invalid snapshot.");
        if (!stopped) { setSnapshot({ url, data }); setError(""); }
      } catch (e) { if (!stopped) setError(e instanceof Error ? e.message : "Could not load snapshot."); }
      finally { busy = false; if (!stopped) setLoading(false); }
    }
    void load();
    const timer = enabled ? window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, interval) : undefined;
    return () => { stopped = true; controller?.abort(); if (timer) window.clearInterval(timer); };
  }, [url, validate, interval, enabled, refresh]);
  return { data: snapshot?.url === url ? snapshot.data : null, error, loading };
}

export function Panel({ title, eyebrow, action, children, className = "" }: { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`admin-panel cc-panel ${className}`}><div className="cc-panel-heading"><div>{eyebrow && <span className="admin-kicker">{eyebrow}</span>}<h2>{title}</h2></div>{action}</div>{children}</section>;
}
export function Empty({ children }: { children: ReactNode }) { return <div className="cc-empty"><FileSearch size={25} /><p>{children}</p></div>; }
function Pager({ page, more, onChange }: { page: number; more: boolean; onChange: (page: number) => void }) {
  return <div className="cc-pagination"><button className="admin-button secondary" disabled={!page} onClick={() => onChange(page - 1)}>Previous</button><span>Page {page + 1} · up to 30 records</span><button className="admin-button secondary" disabled={!more || page >= 10000} onClick={() => onChange(page + 1)}>Next</button></div>;
}
function eventSummary(event: CrawlEvent) {
  const d = event.details;
  return [d.http_status != null ? `HTTP ${d.http_status}` : null, typeof d.duration_ms === "number" ? `${Math.round(d.duration_ms)}ms` : null,
    typeof d.words === "number" ? `${n(d.words)} words` : null,
    typeof d.error === "string" ? d.error : typeof d.reason === "string" ? d.reason : null,
    typeof d.enqueued === "number" ? `${d.enqueued} links queued` : null].filter(Boolean).join(" · ") || `Attempt #${event.attempt_id}`;
}
function EventList({ events, onInspect }: { events: CrawlEvent[]; onInspect: (selection: Inspection) => void }) {
  return events.length ? <div className="cc-events">{events.map(event => <button className="cc-event" key={event.id} onClick={() => onInspect({ type: "attempts", id: event.attempt_id })}><span className="cc-event-time">{new Date(event.at).toLocaleTimeString()}</span><span className={`cc-stage ${event.stage.toLowerCase()}`}>{event.stage}</span><span className="cc-event-main"><strong>{event.url}</strong><small>{event.source} · {eventSummary(event)}</small></span><Badge value={event.outcome} /><ChevronRight size={14} /></button>)}</div> : <Empty>No matching events. Restart the worker after applying the monitoring migration to record stage activity.</Empty>;
}

export default function CrawlerControlCenter() {
  const [days, setDays] = useState(7), [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0);
  const [tab, setTab] = useState("documents"), [source, setSource] = useState("");
  const [status, setStatus] = useState(""), [category, setCategory] = useState("");
  const [search, setSearch] = useState(""), [query, setQuery] = useState("");
  const [documentPage, setDocumentPage] = useState(0), [frontierPage, setFrontierPage] = useState(0);
  const [frontierState, setFrontierState] = useState(""), [beforeEvent, setBeforeEvent] = useState<number | null>(null);
  const [selection, setSelection] = useState<Inspection | null>(null), [clock, setClock] = useState(0);
  useEffect(() => { const timer = window.setTimeout(() => { setQuery(search); setDocumentPage(0); setFrontierPage(0); setBeforeEvent(null); }, 300); return () => window.clearTimeout(timer); }, [search]);
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 5000); return () => window.clearInterval(timer); }, []);
  const params = new URLSearchParams({ days: String(days), document_page: String(documentPage), frontier_page: String(frontierPage) });
  if (source) params.set("source_id", source);
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  if (query) params.set("q", query);
  if (frontierState) params.set("frontier_state", frontierState);
  if (beforeEvent) params.set("before_event_id", String(beforeEvent));
  const monitor = usePolling(`/api/admin/crawler/monitor?${params}`, isCrawlMonitor, 5000, auto && !beforeEvent, refresh);
  const report = usePolling(`/api/admin/crawler/report?days=${days}&top_sources=100&recent_errors=100`, isCrawlerReport, 30000, auto, refresh);
  const indexer = usePolling("/api/admin/indexer/report", isIndexerReport, 15000, auto, refresh);
  const m = monitor.data, r = report.data, ix = indexer.data;
  const stale = !!m && clock > 0 && clock - Date.parse(m.generated_at) > 20000;
  const live = !!m && !monitor.error && !stale && auto;
  const errors = m?.events.filter(e => ["failed", "blocked", "stale"].includes(e.outcome)) ?? [];
  function resetSource(value: string) { setSource(value); setDocumentPage(0); setFrontierPage(0); setBeforeEvent(null); }
  function download() {
    const blob = new Blob([JSON.stringify({ report: r, monitoring: m, filters: Object.fromEntries(params) }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = `crawler-snapshot-${new Date().toISOString().slice(0, 10)}.json`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Crawler</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><Radio size={12} /> CRAWLER CONTROL CENTER · LOCAL</div><h1>Every crawl.<br /><span>In clear sight</span><span className="admin-heading-dot">.</span></h1><p>Follow the pipeline from a URL in the queue to the content you actually keep.</p></div><div className="cc-heading-actions"><span className={`cc-worker-status ${live && m.active_workers ? "online" : ""}`}><span className="admin-tiny-dot" />{!m ? "Worker status unavailable" : !live ? "Worker status at snapshot" : m.active_workers ? `${m.active_workers} worker${m.active_workers === 1 ? "" : "s"} online` : "No worker online"}</span><Link href="/admin/indexer" className={`cc-worker-status ${auto && ix?.activity.status === "indexing" ? "online" : ""}`}><span className="admin-tiny-dot" />{ix ? `Indexer: ${statusLabel[ix.activity.status].toLowerCase()}` : "Indexer status unavailable"}</Link><button className="admin-button secondary" onClick={download} disabled={!m && !r}><ArrowDownToLine size={15} /> Export snapshot</button></div></div>
      <div className="cc-control-bar"><label><span>Window</span><select value={days} aria-label="Report window" onChange={e => { setDays(Number(e.target.value)); setBeforeEvent(null); }}><option value={1}>Today (UTC)</option><option value={7}>7 UTC days</option><option value={30}>30 UTC days</option><option value={90}>90 UTC days</option></select></label><label><span>Source</span><select value={source} aria-label="Filter source" onChange={e => resetSource(e.target.value)}><option value="">All sources</option>{(m?.sources ?? []).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 5s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={monitor.loading || report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={monitor.loading ? "admin-spin" : ""} /></button></div></div>
      <div className="cc-connection" role="status"><span className={`admin-tiny-dot ${live ? "" : "amber"}`} />{monitor.loading ? "Reading committed activity…" : monitor.error ? "Monitoring connection interrupted" : live ? "Connected to crawler monitoring" : "Snapshot view"}<span>{m ? `Updated ${time(m.generated_at)}` : "Waiting for real crawler data"}</span></div>
      {(monitor.error || report.error) && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{m || r ? "Some data may be out of date" : "Crawler data is unavailable"}</strong><p>{monitor.error || report.error}</p><a className="admin-text-link" href="/admin/login">Sign in again if your session expired</a></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      <Metrics monitor={m} report={r} filtered={!!source} />
      <nav className="cc-tabs" aria-label="Crawler sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {m ? <>
        {tab === "overview" && <>
          <div className="cc-grid"><Throughput monitor={m} /><Pipeline monitor={m} /></div>
          <Panel title="Fetching right now" eyebrow="ACTIVE TASKS · HEARTBEAT EVERY 5s" action={<Badge value={live ? "live" : "snapshot"} />}><ActiveWorkers monitor={m} /></Panel>
          <div className="cc-grid cc-grid-equal"><Panel title="Live crawl activity" eyebrow="LATEST 12 STAGE EVENTS" action={<button className="admin-text-link" onClick={() => setTab("activity")}>All activity <ArrowRight size={14} /></button>}><EventList events={m.events.slice(0, 12)} onInspect={setSelection} /></Panel><Panel title="Look inside your content" eyebrow="DOCUMENT INSPECTOR" action={<FileSearch size={20} />}><p className="cc-panel-intro">A successful request is only the beginning. Open a document to inspect the exact text and metadata in your database.</p><DocumentList monitor={m} onInspect={setSelection} compact /><button className="cc-panel-link" onClick={() => setTab("documents")}>Browse persisted documents <ArrowRight size={14} /></button></Panel></div>
          <Performance monitor={m} /><FrontierSummary report={r} /><IndexerSummary report={ix} error={indexer.error} />
        </>}
        {["activity", "errors", "documents", "frontier"].includes(tab) && <div className="cc-filters"><label className="admin-search"><Search size={15} /><input value={search} maxLength={200} onChange={e => setSearch(e.target.value)} placeholder={tab === "documents" ? "Search stored titles or canonical URLs" : "Search URLs"} aria-label="Search crawler records" /></label>{["activity", "errors"].includes(tab) && <><select aria-label="Event outcome" value={status} onChange={e => { setStatus(e.target.value); setBeforeEvent(null); }}><option value="">All outcomes</option>{["running", "success", "failed", "blocked", "skipped", "persisted", "not_stored", "duplicate", "unchanged", "not_modified", "stale"].map(s => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}</select><select aria-label="Pipeline stage" value={category} onChange={e => { setCategory(e.target.value); setBeforeEvent(null); }}><option value="">All stages</option>{["fetch", "parse", "process", "dedup", "store", "discover", "finalize", "worker"].map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}</select></>}{tab === "frontier" && <select value={frontierState} aria-label="Frontier state" onChange={e => { setFrontierState(e.target.value); setFrontierPage(0); }}><option value="">All targets</option>{["due", "scheduled", "leased", "expired", "retry", "blocked", "disabled"].map(s => <option key={s} value={s}>{s}</option>)}</select>}<button className="admin-text-link" onClick={() => { setSearch(""); setStatus(""); setCategory(""); setFrontierState(""); setBeforeEvent(null); }}>Clear filters</button></div>}
        {tab === "activity" && <Panel title={beforeEvent ? "Earlier crawl activity" : "Live crawl activity"} eyebrow="ACTUAL WORKER CHECKPOINTS"><EventList events={m.events} onInspect={setSelection} /><div className="cc-pagination"><span>Latest {m.events.length} matching stage events</span>{beforeEvent && <button className="admin-button secondary" onClick={() => setBeforeEvent(null)}>Back to latest</button>}<button className="admin-button secondary" disabled={!m.events_has_more} onClick={() => { setAuto(false); setBeforeEvent(m.events.at(-1)?.id ?? null); }}>Earlier events</button></div></Panel>}
        {tab === "documents" && <Panel title="Document inspector" eyebrow="CURRENT DATABASE CONTENT · ALL TIME"><p className="cc-panel-intro">Select a document to read its extracted text, metadata and crawl history.</p><DocumentList monitor={m} onInspect={setSelection} /><Pager page={documentPage} more={m.documents_has_more} onChange={setDocumentPage} /></Panel>}
        {tab === "frontier" && <><FrontierSummary report={r} /><Panel title="URL frontier" eyebrow="ORDERED BY PRIORITY, THEN NEXT FETCH"><div className="cc-table-wrap" role="region" aria-label="URL frontier records" tabIndex={0}><table className="cc-table" role="table"><caption>Every queued or leased URL, with its scheduling and retry details.</caption><thead><tr><th scope="col">URL / source</th><th scope="col">State</th><th scope="col">Priority</th><th scope="col">Retries</th><th scope="col">Next fetch</th><th scope="col">Lease expires</th></tr></thead><tbody>{m.frontier.map(t => <tr key={t.id}><td><Url value={t.url} /><small>{t.source} · Target #{t.id}</small></td><td data-label="State"><Badge value={t.state} /></td><td data-label="Priority">{t.priority}</td><td data-label="Retries">{t.retries}</td><td data-label="Next fetch">{time(t.next_fetch_at)}</td><td data-label="Lease expires">{t.lease_until ? time(t.lease_until) : "None"}</td></tr>)}</tbody></table></div>{!m.frontier.length && <Empty>No targets match these filters.</Empty>}<Pager page={frontierPage} more={m.frontier_has_more} onChange={setFrontierPage} /></Panel></>}
        {tab === "sources" && <SourceTable monitor={m} onSource={value => { resetSource(value); setTab("activity"); }} />}
        {tab === "errors" && <><Panel title="Error explorer" eyebrow="FAILED, BLOCKED & STALE STAGE EVENTS"><EventList events={errors} onInspect={setSelection} /><p className="cc-note">Showing errors from the returned event page. Choose Failed or Blocked above to search that outcome across the whole selected window.</p><div className="cc-pagination">{beforeEvent && <button className="admin-button secondary" onClick={() => setBeforeEvent(null)}>Latest events</button>}<button className="admin-button secondary" disabled={!m.events_has_more} onClick={() => { setAuto(false); setBeforeEvent(m.events.at(-1)?.id ?? null); }}>Earlier events</button></div></Panel>{r && <Panel title="Attempt failures & blocks" eyebrow="INCLUDES ATTEMPTS BEFORE INSTRUMENTATION"><div className="cc-events">{r.recent_errors.filter(e => (!source || r.top_sources.find(s => s.id === Number(source))?.slug === e.source) && e.url.toLowerCase().includes(query.toLowerCase())).map(e => <button className="cc-event cc-legacy-event" key={e.attempt_id} onClick={() => setSelection({ type: "attempts", id: e.attempt_id })}><span className="cc-event-main"><strong>{e.url}</strong><small>{e.source} · {e.error || "No reason recorded"}</small></span><Badge value={e.outcome} /><span>{e.http_status ?? "No HTTP"}</span></button>)}</div><p className="cc-note">Latest {r.recent_errors.length} failed or blocked attempts returned by the report, up to 100.</p></Panel>}</>}
        {tab === "workers" && <><Panel title="Worker monitor" eyebrow="ONLINE REQUIRES A HEARTBEAT WITHIN 20s"><ActiveWorkers monitor={m} />{!m.workers.length ? <Empty>No worker heartbeat has been recorded. Start the updated runner to register a worker.</Empty> : <div className="cc-worker-grid">{m.workers.map(w => <article className="cc-worker" key={w.id}><div><strong>{w.hostname}</strong><Badge value={w.status} /></div><code>{w.id}</code><dl><FieldPair label="Process" value={`PID ${w.pid}`} /><FieldPair label="Concurrency / batch size" value={`${w.concurrency} / ${w.batch_size}`} /><FieldPair label="Uptime" value={duration(w.uptime_seconds)} /><FieldPair label="Idle duration" value={duration(w.idle_seconds)} /><FieldPair label="Heartbeat" value={time(w.heartbeat_at)} /><FieldPair label="Active tasks" value={String(w.active_targets.length)} /></dl></article>)}</div>}</Panel><p className="cc-note">Each runner process is one worker. Concurrency counts simultaneous target jobs within that process. Worker state shown here is the last committed heartbeat.</p></>}
      </> : <div className="cc-empty">{monitor.loading ? <><Loader2 className="admin-spin" size={28} /><p>Loading crawler measurements…</p></> : <><Radio size={28} /><p>Connect the backend and apply the crawler monitoring migration to start inspecting activity.</p></>}</div>}
      <footer className="admin-footer"><span>DEVELOPER&apos;S EYE <span className="admin-accent">/</span> CRAWLER CONTROL CENTER</span><span>Events: 5s · Totals: 30s · Times: your browser timezone</span></footer>
    </main>{selection && <CrawlInspector selection={selection} onClose={() => setSelection(null)} onSelect={setSelection} />}
  </>;
}

function Metrics({ monitor: m, report: r, filtered }: { monitor: CrawlMonitor | null; report: CrawlerReport | null; filtered: boolean }) {
  const cards = [
    { label: "URLs attempted", value: m ? n(m.summary.attempted) : "N/A", note: "Selected window & source", icon: <Activity size={16} /> },
    { label: "Fetch success", value: metric(m?.summary.fetch_success_percent, "%"), note: "2xx / 304 of HTTP responses", icon: <ShieldCheck size={16} /> },
    { label: "Crawl rate", value: metric(m?.summary.urls_per_second, "/s"), note: "Completed URLs · rolling 5m", icon: <Gauge size={16} /> },
    { label: "Documents stored", value: r ? n(r.documents.total) : "N/A", note: filtered ? "All sources · current database" : "Current database · all time", icon: <Database size={16} /> },
    { label: "Queued / due", value: r ? n(r.frontier.queued_due) : "N/A", note: "All sources · eligible now", icon: <Layers3 size={16} /> },
    { label: "Active workers", value: m ? String(m.active_workers) : "N/A", note: "All sources · heartbeat ≤20s", icon: <Radio size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}
function Throughput({ monitor: m }: { monitor: CrawlMonitor }) {
  const max = Math.max(1, ...m.throughput.map(t => t.attempts)), total = m.throughput.reduce((sum, t) => sum + t.attempts, 0);
  return <Panel title="Crawl throughput" eyebrow="LAST 60 MINUTES · SELECTED SOURCE" action={<span className="cc-panel-tag">{n(total)} attempts</span>}><div className="cc-chart" role="img" aria-label={`${total} attempts over the last 60 minute buckets. Peak ${max} attempts in a minute.`}><div className="cc-chart-scale"><span>{max}/min</span><span>{Math.round(max / 2)}</span><span>0</span></div><div className="cc-bars">{m.throughput.map(t => <div key={t.at} title={`${time(t.at)}: ${t.attempts} attempted, ${t.successful} HTTP 2xx/304`}><i style={{ height: `${100 * t.attempts / max}%` }}><b style={{ height: `${t.attempts ? 100 * t.successful / t.attempts : 0}%` }} /></i></div>)}</div></div><div className="cc-chart-axis"><span>{new Date(m.throughput[0].at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span>30m ago</span><span>Now</span></div><div className="cc-chart-legend"><span><i />HTTP 2xx / 304</span><span><i />Other / unfinished</span></div></Panel>;
}
function Pipeline({ monitor: m }: { monitor: CrawlMonitor }) {
  const s = m.summary;
  const stages: [string, number][] = [["URLs attempted", s.instrumented], ["Fetched successfully", s.fetched], ["Parsed successfully", s.parsed], ["Content accepted", s.accepted], ["Persisted documents", s.persisted]];
  return <Panel title="Pipeline conversion" eyebrow="INSTRUMENTED URL ATTEMPTS"><div className="cc-funnel">{stages.map(([label, value], i) => <div key={label}><div><span>{label}</span><strong>{n(value)}</strong></div><div className="cc-funnel-track"><i style={{ width: `${s.instrumented ? 100 * value / s.instrumented : 0}%`, opacity: 1 - i * .12 }} /></div></div>)}</div><p className="cc-note">Each stage counts attempts reaching it, including in-progress attempts. Persisted counts attempts writing ≥1 document, including unchanged refreshes.</p>{s.historical_uninstrumented > 0 && <p className="cc-note cc-warning">{n(s.historical_uninstrumented)} older attempts have no stage measurements.</p>}<details className="cc-dispositions"><summary>Reconcile all {n(s.attempted)} attempts</summary>{Object.entries(s.dispositions).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{n(value)}</strong></div>)}</details></Panel>;
}
function DocumentList({ monitor: m, onInspect, compact = false }: { monitor: CrawlMonitor; onInspect: (selection: Inspection) => void; compact?: boolean }) {
  const documents = compact ? m.documents.slice(0, 5) : m.documents;
  return documents.length ? <div className="cc-documents">{documents.map(d => <button key={d.id} className="cc-document" onClick={() => onInspect({ type: "documents", id: d.id })}><span className="cc-document-icon"><FileSearch size={18} /></span><span><strong>{d.title}</strong>{d.is_available === false && <Badge value={`unavailable HTTP ${d.unavailable_http_status}`} />}<small>{d.canonical_url}</small><small>{d.source} · {d.document_type} · Seen {time(d.last_seen_at)}</small></span><ChevronRight size={15} /></button>)}</div> : <Empty>No stored documents match these filters. A fetch can succeed without producing accepted content.</Empty>;
}
function ActiveWorkers({ monitor: m }: { monitor: CrawlMonitor }) {
  const active = m.workers.flatMap(w => w.active_targets.map(t => ({ ...t, worker: `${w.hostname} / ${w.pid}` })));
  return <div className="cc-active-targets">{active.length ? active.map(t => <div key={`${t.worker}-${t.target_id}`}><span className="cc-live-dot" /><span><Url value={t.url} /><small>{t.worker} · Target #{t.target_id}</small></span><Badge value="running" /></div>) : <p>{m.active_workers ? "Workers are online with no active tasks in the latest heartbeat." : "No online worker is reporting active tasks."}</p>}</div>;
}
function Performance({ monitor: m }: { monitor: CrawlMonitor }) {
  const s = m.summary;
  return <Panel title="Efficiency & latency" eyebrow="SELECTED WINDOW & SOURCE"><div className="cc-performance">{[["Fetch p50", metric(s.fetch_p50_ms, "ms")], ["Fetch p95", metric(s.fetch_p95_ms, "ms")], ["Storage mean", metric(s.storage_avg_ms, "ms")], ["Response mean", metric(s.response_avg_bytes == null ? null : s.response_avg_bytes / 1024, " KB")]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><p className="cc-note">{n(s.fetch_samples)} measured fetches. Fetch timing includes policy checks, redirects and politeness waits. Storage timing measures finalization transaction work before commit.</p></Panel>;
}
function IndexerSummary({ report: x, error }: { report: IndexerReport | null; error: string }) {
  if (!x) return error ? <Panel title="Search indexing" eyebrow="INDEXER"><p className="cc-note cc-warning">{error}</p></Panel> : null;
  const c = x.coverage, a = x.activity;
  return <Panel title="Search indexing" eyebrow="INDEXER · CURRENT STATE · ALL SOURCES" action={<Link className="admin-text-link" href="/admin/indexer">Indexer reports <ArrowRight size={14} /></Link>}><div className="cc-frontier-summary">{[["Coverage", metric(c.coverage_percent, "%")], ["Up to date", n(c.current_documents)], ["Pending", n(c.pending_documents)], ["Indexed / min", metric(a.docs_per_minute)], ["Indexed last hour", n(a.indexed_last_hour)]].map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>{a.status === "backlog_waiting" && <p className="cc-note cc-warning">{n(c.pending_documents)} documents are waiting and nothing was indexed in the last 2 minutes. Check that the indexer worker is running.</p>}</Panel>;
}
function FrontierSummary({ report: r }: { report: CrawlerReport | null }) {
  if (!r) return null;
  return <Panel title="Frontier health" eyebrow="CURRENT STATE · ALL SOURCES"><div className="cc-frontier-summary">{[["Due now", r.frontier.queued_due], ["Scheduled", r.frontier.queued_scheduled], ["Leases active", r.frontier.leases_active], ["Leases expired", r.frontier.leases_expired], ["Blocked", r.frontier.by_state.blocked], ["Disabled", r.frontier.by_state.disabled]].map(([label, value]) => <div key={label}><strong>{n(value as number)}</strong><span>{label}</span></div>)}</div>{r.frontier.leases_expired > 0 && <p className="cc-note cc-warning">Expired leases require recovery by a running worker. A lease alone does not establish worker liveness.</p>}</Panel>;
}
function SourceTable({ monitor: m, onSource }: { monitor: CrawlMonitor; onSource: (value: string) => void }) {
  return <Panel title="Source health" eyebrow="ALL SOURCES · SELECTED WINDOW"><div className="cc-table-wrap" role="region" aria-label="Source health records" tabIndex={0}><table className="cc-table" role="table"><caption>Fetch outcomes and stored content for each registered source.</caption><thead><tr><th scope="col">Source</th><th scope="col">Documents</th><th scope="col">Attempts</th><th scope="col">HTTP success</th><th scope="col">Failed / blocked</th><th scope="col">Mean fetch</th><th scope="col">Last activity</th></tr></thead><tbody>{m.sources.map(s => <tr key={s.id}><td><button className="admin-text-link" onClick={() => onSource(String(s.id))}>{s.name}<ArrowRight size={12} /></button><small>{s.slug} · {s.is_enabled ? "enabled" : "disabled"}</small></td><td data-label="Documents">{n(s.documents)}</td><td data-label="Attempts">{n(s.attempts)}</td><td data-label="HTTP success">{s.attempts ? metric(100 * s.successful / s.attempts, "%") : "N/A"}<small>of all attempts</small></td><td data-label="Failed / blocked">{s.failed} / {s.blocked}</td><td data-label="Mean fetch">{metric(s.avg_fetch_ms, "ms")}</td><td data-label="Last activity">{time(s.last_activity_at)}</td></tr>)}</tbody></table></div>{!m.sources.length && <Empty>No sources are registered.</Empty>}</Panel>;
}
function FieldPair({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }
