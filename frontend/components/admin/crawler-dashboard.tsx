"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { Activity, ArrowDownToLine, ArrowUpRight, Check, CheckCheck, ChevronDown, ChevronRight, CircleAlert, Clock3, Copy, Database, ExternalLink, FileText, Globe2, Layers3, Loader2, Pause, Play, Radio, RefreshCw, Search, ShieldCheck, Waypoints, X } from "lucide-react";
import { isCrawlerReport, safeHttpUrl, type CrawlerReport, type DailyAttempts } from "@/lib/crawler-report";
import { api, isCancelled } from "@/lib/api-client";

const number = new Intl.NumberFormat("en-US");
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const percent = (value: number | null) => value === null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
function dateTime(value: string | null) {
  return value ? new Date(value).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }) + " UTC" : "No activity recorded";
}
function shortDate(value: string) { return new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }); }

export default function CrawlerDashboard() {
  const [days, setDays] = useState(7);
  const [snapshot, setSnapshot] = useState<{ days: number; report: CrawlerReport } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [tab, setTab] = useState("overview");
  const [exportNotice, setExportNotice] = useState("");
  const report = snapshot?.days === days ? snapshot.report : null;

  useEffect(() => {
    let stopped = false;
    let busy = false;
    let controller: AbortController | null = null;
    async function load() {
      if (busy || stopped) return;
      busy = true;
      controller = new AbortController();
      setLoading(true);
      try {
        const response = await api.get("/admin/crawler/report", { params: { days, top_sources: 100, recent_errors: 100 }, signal: controller.signal });
        const data = response.data;
        if (response.status !== 200) {
          if (response.status === 401) setExpired(true);
          throw new Error(typeof data?.error === "string" ? data.error : "The report couldn't be loaded. Please retry.");
        }
        if (!isCrawlerReport(data)) throw new Error("The report response is invalid.");
        if (!stopped) { setSnapshot({ days, report: data }); setError(null); setExpired(false); }
      } catch (err) {
        if (!stopped && !isCancelled(err)) setError(err instanceof Error ? err.message : "Couldn't load the report.");
      } finally { busy = false; if (!stopped) setLoading(false); }
    }
    void load();
    const timer = autoRefresh ? window.setInterval(() => { if (document.visibilityState === "visible") void load(); }, 30000) : undefined;
    return () => { stopped = true; controller?.abort(); if (timer) window.clearInterval(timer); };
  }, [days, refresh, autoRefresh]);

  function download() {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `developers-eye-crawler-${report.generated_at.slice(0, 10)}-${days}d.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setExportNotice("Snapshot exported");
    window.setTimeout(() => setExportNotice(""), 3000);
  }

  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Crawler</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only access</span></header>
    <main className="admin-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><span className="admin-tiny-dot" /> YOUR DISCOVERY ENGINE</div><h1>Crawler <span>overview</span><span className="admin-heading-dot">.</span></h1><p>A clear view of what&apos;s discovered, collected, and ready to search.</p></div><button className="admin-button secondary" onClick={download} disabled={!report}><ArrowDownToLine size={15} /> Export report</button></div>
      <div className="admin-toolbar"><div className="admin-tabs" role="tablist" aria-label="Crawler report sections">{[["overview", "Overview"], ["sources", "Sources"], ["failures", "Failures"]].map(([id, label]) => <button key={id} role="tab" id={`tab-${id}`} aria-selected={tab === id} aria-controls="crawler-panel" onClick={() => setTab(id)}>{label}{id === "failures" && report && report.recent_errors.length > 0 && <span>{report.recent_errors.length}{report.recent_errors.length === 100 ? "+" : ""}</span>}</button>)}</div><div className="admin-toolbar-actions"><label className="admin-range"><Clock3 size={14} /><select aria-label="Report date range" value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>Last 7 days</option><option value={14}>Last 14 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select><ChevronDown size={13} /></label><button className={`admin-icon-button ${autoRefresh ? "is-active" : ""}`} onClick={() => setAutoRefresh(!autoRefresh)} aria-pressed={autoRefresh} aria-label={autoRefresh ? "Pause automatic refresh" : "Enable automatic refresh"} title={autoRefresh ? "Auto-refresh every 30s. Click to pause." : "Enable 30-second auto-refresh"}>{autoRefresh ? <Pause size={14} /> : <Play size={14} />}</button><button className="admin-icon-button" disabled={loading} onClick={() => setRefresh((value) => value + 1)} aria-label="Refresh report" title="Refresh report"><RefreshCw size={15} className={loading ? "admin-spin" : ""} /></button></div></div>
      <div className="admin-snapshot-status" aria-live="polite"><span className={`admin-tiny-dot ${error ? "amber" : loading ? "muted" : ""}`} /><span>{loading ? "Fetching snapshot…" : error ? report ? "Connection interrupted · showing last successful snapshot" : "Reporting connection unavailable" : "Snapshot connected"}</span><span className="admin-snapshot-time">{report ? `Updated ${dateTime(report.generated_at)}` : "PostgreSQL report"}</span><span className="admin-auto-label">{autoRefresh ? "AUTO / 30s" : "AUTO / PAUSED"}</span></div>
      {error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{report ? "This snapshot may be out of date" : "We couldn't load your crawler report"}</strong><p>{error}</p></div>{expired ? <a href="/admin/login" className="admin-button secondary">Sign in</a> : <button className="admin-button secondary" onClick={() => setRefresh((value) => value + 1)} disabled={loading}>Retry <RefreshCw size={13} /></button>}</div>}
      {!report && loading && <DashboardSkeleton />}
      {!report && !loading && <div className="admin-empty-connection"><div className="admin-empty-icon"><Waypoints size={36} strokeWidth={1.2} /></div><span className="admin-kicker">WAITING FOR A CONNECTION</span><h2>Your next discovery starts here.</h2><p>Once the reporting service is connected, this space fills with your crawler&apos;s real activity, queue state, sources, and failures.</p><button className="admin-button primary" onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={15} /> Try connection again</button><a href="/docs" className="admin-text-link">View project documentation <ArrowUpRight size={14} /></a></div>}
      {report && <div role="tabpanel" id="crawler-panel" aria-labelledby={`tab-${tab}`}>
        <div className="admin-metrics">
          <Metric label="Documents collected" value={number.format(report.documents.total)} icon={<FileText size={17} />} detail={<><span className="admin-accent">{number.format(report.documents.updated_in_window)}</span> updated in this window</>} />
          <Metric label="Crawl attempts" value={number.format(report.attempts.total_in_window)} icon={<Activity size={17} />} detail={<>{number.format(report.attempts.finished_in_window)} finished <span className="admin-separator">/</span> {number.format(report.attempts.by_outcome.unfinished)} unfinished</>} />
          <Metric label="Success rate" value={percent(report.attempts.success_rate_percent)} icon={<CheckCheck size={17} />} detail={<>Success + not modified <span className="admin-separator">/</span> finished</>} accent />
          <Metric label="Enabled sources" value={number.format(report.sources.enabled)} suffix={`/ ${number.format(report.sources.total)}`} icon={<Globe2 size={17} />} detail={<>{number.format(report.sources.disabled)} disabled in the registry</>} />
        </div>
        {tab === "overview" && <><div className="admin-chart-grid"><ActivityChart report={report} /><IndexCoverage report={report} /></div><Frontier report={report} /><SourceTable report={report} compactView onViewAll={() => setTab("sources")} /><ErrorTable report={report} compactView onViewAll={() => setTab("failures")} /></>}
        {tab === "sources" && <SourceTable report={report} />}
        {tab === "failures" && <ErrorTable report={report} />}
        <div className="admin-report-footnote"><Database size={12} /><p>Committed PostgreSQL records · {days} UTC calendar days, including today · Queue and index counts are all-time snapshots. Active leases do not indicate worker uptime.</p></div>
      </div>}
      <footer className="admin-footer"><span>DEVELOPER&apos;S EYE <span className="admin-accent">/</span> CRAWLER INTELLIGENCE</span><span>Every discovery, accounted for.</span></footer>
      {exportNotice && <div className="admin-toast" role="status"><Check size={16} />{exportNotice}</div>}
    </main>
  </>;
}

function Metric({ label, value, suffix, icon, detail, accent }: { label: string; value: string; suffix?: string; icon: React.ReactNode; detail: React.ReactNode; accent?: boolean }) {
  return <section className={`admin-metric ${accent ? "accent" : ""}`}><div className="admin-metric-label">{label}<span>{icon}</span></div><div className="admin-metric-value">{value}{suffix && <small>{suffix}</small>}</div><div className="admin-metric-detail">{detail}</div></section>;
}

function PanelHeading({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: React.ReactNode }) {
  return <div className="admin-panel-heading"><div>{eyebrow && <span className="admin-kicker">{eyebrow}</span>}<h2>{title}</h2></div>{children}</div>;
}

function ActivityChart({ report }: { report: CrawlerReport }) {
  const [selected, setSelected] = useState<string | null>(null);
  const chartId = useId();
  const max = Math.max(1, ...report.daily_attempts.map((day) => day.attempts));
  const active = report.daily_attempts.find((day) => day.date === selected);
  const labelStep = Math.max(1, Math.ceil(report.daily_attempts.length / 7));
  return <section className="admin-panel admin-activity"><PanelHeading eyebrow="THE BIG PICTURE" title="Discovery over time"><span className="admin-panel-tag">DAILY / UTC</span></PanelHeading><div className="admin-chart-summary"><strong>{number.format(report.attempts.total_in_window)}</strong><span>crawl attempts<br />in the last {report.window.days} days</span><div className="admin-chart-legend"><span><i className="lime" /> Successful</span><span><i className="red" /> Failed</span><span><i className="amber" /> Blocked</span><span><i className="gray" /> Unfinished</span></div></div>
      <div className="admin-bar-chart" aria-label="Daily crawl attempts"><div className="admin-chart-axis"><span>{compact.format(max)}</span><span>{compact.format(Math.round(max / 2))}</span><span>0</span></div><div className="admin-chart-plot"><div className="admin-chart-gridlines" aria-hidden="true"><i /><i /><i /></div><div className="admin-chart-bars">{report.daily_attempts.map((day, index) => <DayBar key={day.date} day={day} max={max} selected={selected === day.date} onSelect={() => setSelected(selected === day.date ? null : day.date)} label={index % labelStep === 0 || index === report.daily_attempts.length - 1} chartId={chartId} />)}</div></div></div>
      <div className="admin-chart-caption" id={chartId}>{active ? <><strong>{shortDate(active.date)}</strong><span>{number.format(active.attempts)} attempts</span><span className="admin-accent">{number.format(active.successful)} successful</span><span>{number.format(active.failed)} failed</span><span>{number.format(active.blocked)} blocked</span><button aria-label="Clear selected day" onClick={() => setSelected(null)}><X size={12} /></button></> : <><span className="admin-tiny-dot muted" />{report.attempts.total_in_window ? "Select a day to inspect its activity." : "No crawl attempts recorded in this window."}</>}</div>
    </section>;
}

function DayBar({ day, max, selected, onSelect, label, chartId }: { day: DailyAttempts; max: number; selected: boolean; onSelect: () => void; label: boolean; chartId: string }) {
  const height = day.attempts / max * 100;
  const unfinished = Math.max(0, day.attempts - day.successful - day.failed - day.blocked);
  return <div className="admin-day-column"><button className={`admin-day-bar ${selected ? "selected" : ""}`} onClick={onSelect} aria-pressed={selected} aria-describedby={selected ? chartId : undefined} aria-label={`${shortDate(day.date)}: ${day.attempts} attempts, ${day.successful} successful, ${day.failed} failed, ${day.blocked} blocked, ${unfinished} unfinished`} title={`${shortDate(day.date)} · ${number.format(day.attempts)} attempts`}><span className="admin-day-stack" style={{ height: `${height}%`, minHeight: day.attempts ? 3 : 1 }}>{[[unfinished, "gray"], [day.blocked, "amber"], [day.failed, "red"], [day.successful, "lime"]].map(([value, color]) => Number(value) > 0 && <i key={String(color)} className={String(color)} style={{ flexGrow: Number(value) }} />)}</span></button><span className="admin-day-label">{label ? shortDate(day.date) : ""}</span></div>;
}

function IndexCoverage({ report }: { report: CrawlerReport }) {
  const docs = report.documents;
  const coverage = docs.total ? Math.min(100, docs.indexed / docs.total * 100) : null;
  const fresh = Math.max(0, docs.indexed - docs.stale_index_hashes);
  const segments = [{ value: fresh, color: "#d1f58d", label: "Current index" }, { value: docs.stale_index_hashes, color: "#d8ac6b", label: "Stale index" }, { value: docs.not_indexed, color: "#343a31", label: "Not indexed" }];
  let offset = 0;
  return <section className="admin-panel admin-index"><PanelHeading eyebrow="SEARCH READINESS" title="Index coverage"><Layers3 size={18} /></PanelHeading><div className="admin-donut"><svg viewBox="0 0 160 160" role="img" aria-label={`${percent(coverage)} of collected documents have an index entry`}><circle cx="80" cy="80" r="64" fill="none" stroke="#2b3028" strokeWidth="12" />{segments.map((segment) => { const length = docs.total ? segment.value / docs.total * 100 : 0; const start = offset; offset += length; return length > 0 && <circle key={segment.label} cx="80" cy="80" r="64" pathLength="100" fill="none" stroke={segment.color} strokeWidth="12" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} transform="rotate(-90 80 80)" />; })}</svg><div><strong>{percent(coverage)}</strong><span>INDEXED</span></div></div><div className="admin-index-legend">{segments.map((segment) => <div key={segment.label}><span><i style={{ background: segment.color }} />{segment.label}</span><strong>{number.format(segment.value)}</strong></div>)}</div><div className="admin-index-foot"><Database size={12} />{number.format(docs.seen_in_window)} documents seen in this window</div></section>;
}

function Frontier({ report }: { report: CrawlerReport }) {
  const frontier = report.frontier;
  const states = [{ label: "Queued", value: frontier.by_state.queued, color: "lime" }, { label: "Leased", value: frontier.by_state.leased, color: "blue" }, { label: "Blocked", value: frontier.by_state.blocked, color: "amber" }, { label: "Disabled", value: frontier.by_state.disabled, color: "gray" }];
  return <section className="admin-panel admin-frontier"><div className="admin-frontier-main"><PanelHeading eyebrow="WHAT'S NEXT" title="The crawl frontier"><span className="admin-panel-tag">{number.format(frontier.total)} TARGETS</span></PanelHeading><div className="admin-frontier-track" role="img" aria-label={states.map((state) => `${state.label}: ${state.value}`).join(", ")}>{states.map((state) => state.value > 0 && <span key={state.label} className={state.color} style={{ flexGrow: state.value }} />)}</div><div className="admin-frontier-legend">{states.map((state) => <div key={state.label}><span><i className={state.color} />{state.label}</span><strong>{number.format(state.value)}</strong></div>)}</div><div className="admin-queue-detail"><span><Radio size={13} /><strong>{number.format(frontier.queued_due)}</strong> due now</span><span><Clock3 size={13} /><strong>{number.format(frontier.queued_scheduled)}</strong> scheduled</span><span><Waypoints size={13} /><strong>{number.format(frontier.leases_active)}</strong> active leases</span></div></div><div className="admin-health-panel"><div className="admin-health-row"><span className={`admin-health-icon ${frontier.leases_expired ? "warning" : ""}`}>{frontier.leases_expired ? <CircleAlert size={17} /> : <Check size={17} />}</span><div><strong>{frontier.leases_expired ? `${number.format(frontier.leases_expired)} expired leases` : "No expired leases"}</strong><p>{frontier.leases_expired ? "Awaiting worker lease recovery" : "No lease recovery pending"}</p></div></div><div className="admin-health-row"><span className="admin-health-icon neutral"><ShieldCheck size={17} /></span><div><strong>Robots cache</strong><p>{number.format(report.robots_cache.valid)} valid <span>·</span> {number.format(report.robots_cache.expired)} expired</p></div></div><div className="admin-last-success"><span>LAST SUCCESSFUL CRAWL</span><strong>{dateTime(report.attempts.last_success_at)}</strong></div></div></section>;
}

function SourceTable({ report, compactView = false, onViewAll }: { report: CrawlerReport; compactView?: boolean; onViewAll?: () => void }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("targets");
  const rows = useMemo(() => report.top_sources.filter((source) => `${source.name} ${source.slug} ${source.kind}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || source.enabled === (filter === "enabled"))).sort((a, b) => sort === "name" ? a.name.localeCompare(b.name) : b[sort as "targets" | "attempts" | "documents"] - a[sort as "targets" | "attempts" | "documents"] || a.id - b.id), [report.top_sources, search, filter, sort]);
  const visible = compactView ? rows.slice(0, 5) : rows;
  return <section className="admin-panel admin-table-panel"><PanelHeading eyebrow="WHERE KNOWLEDGE COMES FROM" title="Source performance">{compactView ? <button className="admin-text-link" onClick={onViewAll}>All sources <ArrowUpRight size={14} /></button> : <span className="admin-panel-tag">{number.format(report.sources.total)} REGISTERED</span>}</PanelHeading>{!compactView && <div className="admin-table-toolbar"><label className="admin-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search sources…" aria-label="Search sources" /></label><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Source status"><option value="all">All statuses</option><option value="enabled">Enabled</option><option value="disabled">Disabled</option></select><select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort sources"><option value="targets">Most targets</option><option value="attempts">Most attempts</option><option value="documents">Most documents</option><option value="name">Name A–Z</option></select></div>}<div className="admin-table-scroll"><table className="admin-table"><thead><tr><th>Source</th><th>Status</th><th className="numeric">Targets</th><th className="numeric">Documents</th><th className="numeric">Attempts</th><th className="numeric">Successful / attempts</th></tr></thead><tbody>{visible.map((source) => <tr key={source.id}><td><div className="admin-source-name"><span className="admin-source-icon">{source.kind === "website" ? <Globe2 size={16} /> : <Waypoints size={16} />}</span><div><strong>{source.name}</strong><small>{source.slug} <span>·</span> {source.kind}</small></div></div></td><td><span className={`admin-badge ${source.enabled ? "green" : "neutral"}`}><i />{source.enabled ? "Enabled" : "Disabled"}</span></td><td className="numeric">{number.format(source.targets)}</td><td className="numeric">{number.format(source.documents)}</td><td className="numeric">{number.format(source.attempts)}</td><td className="numeric"><div className="admin-source-rate"><span>{source.attempts ? percent(source.successful / source.attempts * 100) : "N/A"}</span><div><i style={{ width: `${source.attempts ? Math.min(100, source.successful / source.attempts * 100) : 0}%` }} /></div></div></td></tr>)}</tbody></table></div>{visible.length === 0 && <div className="admin-table-empty"><Search size={22} /><strong>{report.top_sources.length ? "No sources match your filters" : "No sources registered yet"}</strong><p>{report.top_sources.length ? "Try another name or status." : "Register a source to begin discovering content."}</p></div>}<div className="admin-table-foot"><span>Showing {visible.length} of {report.top_sources.length} returned sources{report.sources.total > report.top_sources.length ? ` · ${report.sources.total} registered, top 100 by target count` : ""}</span><span>Attempts use the selected UTC window</span></div></section>;
}

function ErrorTable({ report, compactView = false, onViewAll }: { report: CrawlerReport; compactView?: boolean; onViewAll?: () => void }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [copyError, setCopyError] = useState("");
  const rows = report.recent_errors.filter((item) => (filter === "all" || item.outcome === filter) && `${item.source} ${item.url} ${item.error ?? ""} ${item.http_status ?? ""}`.toLowerCase().includes(search.toLowerCase()));
  const visible = compactView ? rows.slice(0, 3) : rows;
  async function copy(id: number, url: string) {
    try { await navigator.clipboard.writeText(url); setCopied(id); setCopyError(""); window.setTimeout(() => setCopied(null), 2000); }
    catch { setCopyError("Clipboard unavailable. Open the details to select and copy the URL."); }
  }
  return <section className="admin-panel admin-error-panel"><PanelHeading eyebrow="A LITTLE ATTENTION GOES A LONG WAY" title="Recent failures & blocks">{compactView ? <button className="admin-text-link" onClick={onViewAll}>Inspect all <ArrowUpRight size={14} /></button> : <span className="admin-panel-tag">LATEST {report.recent_errors.length}{report.recent_errors.length === 100 ? "+" : ""}</span>}</PanelHeading>{!compactView && <div className="admin-table-toolbar"><label className="admin-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search URLs, sources, errors…" aria-label="Search failures" /></label><select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Failure outcome"><option value="all">All outcomes</option><option value="failed">Failed</option><option value="blocked">Blocked</option></select></div>}{copyError && <p className="admin-copy-error" role="status">{copyError}</p>}<div className="admin-errors">{visible.map((item) => <article key={item.attempt_id} className="admin-error-item"><div className="admin-error-summary"><button className="admin-error-toggle" aria-expanded={expanded === item.attempt_id} aria-controls={`error-${item.attempt_id}`} onClick={() => setExpanded(expanded === item.attempt_id ? null : item.attempt_id)}><span className={`admin-error-marker ${item.outcome}`}><CircleAlert size={16} /></span><span className="admin-error-description"><strong>{item.source}<span className={`admin-badge ${item.outcome === "failed" ? "red" : "amber"}`}>{item.outcome}</span>{item.http_status !== null && <small>HTTP {item.http_status}</small>}</strong><span>{item.url}</span></span><span className="admin-error-date">{dateTime(item.started_at)}</span><ChevronDown size={14} className={expanded === item.attempt_id ? "expanded" : ""} /></button><button className="admin-icon-button" aria-label={`Copy URL for attempt ${item.attempt_id}`} onClick={() => void copy(item.attempt_id, item.url)} title={copied === item.attempt_id ? "Copied" : "Copy URL"}>{copied === item.attempt_id ? <Check size={14} /> : <Copy size={14} />}</button></div>{expanded === item.attempt_id && <div className="admin-error-details" id={`error-${item.attempt_id}`}><p>{item.error || "No error message was recorded for this attempt."}</p><code>{item.url}</code><div><span>Attempt #{item.attempt_id} · Target #{item.target_id} · Finished: {dateTime(item.finished_at)}</span>{safeHttpUrl(item.url) && <a href={safeHttpUrl(item.url)!} target="_blank" rel="noreferrer noopener">Open URL <ExternalLink size={12} /></a>}</div></div>}</article>)}</div>{!visible.length && <div className="admin-table-empty"><span className="admin-clear-icon">{report.recent_errors.length ? <Search size={23} /> : <CheckCheck size={25} />}</span><strong>{report.recent_errors.length ? "No matching failures" : "Nothing to investigate"}</strong><p>{report.recent_errors.length ? "Try a different search or outcome." : "No failed or blocked attempts were recorded in this window."}</p></div>}<div className="admin-table-foot"><span>Showing {visible.length} of {report.recent_errors.length} returned attempts{report.recent_errors.length === 100 ? " · limited to latest 100" : ""}</span><span>Newest first · UTC</span></div></section>;
}

function DashboardSkeleton() {
  return <div className="admin-loading" role="status" aria-label="Loading crawler report"><div className="admin-metrics">{[1, 2, 3, 4].map((id) => <div className="admin-metric admin-skeleton" key={id}><i /><b /><i /></div>)}</div><div className="admin-chart-grid"><div className="admin-panel admin-skeleton large" /><div className="admin-panel admin-skeleton large" /></div><span className="admin-loading-text"><Loader2 size={15} className="admin-spin" /> Reading your crawler snapshot…</span></div>;
}
