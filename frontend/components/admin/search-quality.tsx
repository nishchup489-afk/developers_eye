"use client";

import { useState } from "react";
import { ChevronRight, CircleAlert, Gauge, Loader2, Pause, Play, RefreshCw, Scale, ShieldCheck, Timer, TriangleAlert } from "lucide-react";
import { api } from "@/lib/axios";
import { isEvaluationReport, isJudgingQuery, isSlowSearchReport, STAGES, type EvaluationReport, type JudgingQuery, type RankerMetrics, type SlowSearchReport } from "@/lib/search-quality";
import { Empty, Panel, usePolling } from "./crawler-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const ms = (value: number | null | undefined) => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} ms`;
const score = (value: number | null | undefined) => value == null ? "N/A" : value.toFixed(3);
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Never";
const GRADES = [["0", "Not relevant"], ["1", "Related"], ["2", "Relevant"], ["3", "Perfect answer"]] as const;
type Tab = "slow" | "metrics" | "judge";

// Admin writes go through same-origin route handlers; errors come back as { error }.
async function write(method: "put" | "post" | "delete", url: string, body?: unknown) {
  const response = await api.request({ method, url, baseURL: "", data: body });
  if (response.status >= 200 && response.status < 300) return response.data as unknown;
  const data = response.data as { error?: unknown } | null;
  throw new Error(typeof data?.error === "string" ? data.error : "The change could not be saved.");
}

export default function SearchQuality({ canEdit }: { canEdit: boolean }) {
  const [tab, setTab] = useState<Tab>("slow");
  const [selected, setSelected] = useState<string | null>(null);
  const tabs: [Tab, string][] = [["slow", "Slow searches"], ["metrics", "Relevance metrics"], ["judge", "Judge results"]];
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Search quality</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> {canEdit ? "Administrator: grading enabled" : "Read-only: grading needs an administrator"}</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><Gauge size={12} /> LATENCY AND HUMAN-JUDGED RELEVANCE</div><h1>Fast answers.<br /><span>The right ones</span><span className="admin-heading-dot">.</span></h1><p>Slow and timed-out searches with the stage that took the time, and P@10, MRR@10 and nDCG@10 from your own 0–3 grades.</p></div></div>
      <nav className="cc-tabs" aria-label="Search quality sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {tab === "slow" && <SlowSearches />}
      {tab === "metrics" && <Metrics canEdit={canEdit} onJudge={id => { setSelected(id); setTab("judge"); }} />}
      {tab === "judge" && <Judge canEdit={canEdit} selected={selected} onSelect={setSelected} />}
    </main>
  </>;
}

function ErrorBox({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{title}</strong><p>{message}</p></div>{onRetry && <button className="admin-button secondary" onClick={onRetry}>Retry</button>}</div>;
}

function SlowSearches() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [hours, setHours] = useState(24);
  const report = usePolling(`/api/admin/search-quality/slow?hours=${hours}&limit=100`, isSlowSearchReport, 30000, auto, refresh);
  const r = report.data;
  return <>
    <div className="cc-control-bar"><label><span>Window</span><select value={hours} aria-label="Slow search window" onChange={e => setHours(Number(e.target.value))}><option value={1}>Last hour</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option><option value={720}>Last 30 days</option></select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 30s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh slow searches" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
    {report.error && <ErrorBox title={r ? "Some data may be out of date" : "Slow searches are unavailable"} message={report.error} onRetry={() => setRefresh(v => v + 1)} />}
    {r ? <SlowReport report={r} /> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading slow searches.</div>}
  </>;
}

function SlowReport({ report: r }: { report: SlowSearchReport }) {
  const worst = [...STAGES].filter(stage => r.stage_means_ms[stage] != null).sort((a, b) => (r.stage_means_ms[b] ?? 0) - (r.stage_means_ms[a] ?? 0))[0];
  const cards = [
    { label: "Slow searches", value: n(r.total), note: `At or over ${n(r.threshold_ms)} ms`, icon: <Timer size={16} /> },
    { label: "Timed out", value: n(r.timed_out), note: Object.entries(r.timeouts_by_stage).map(([stage, count]) => `${count} in ${stage}`).join(", ") || "None in window", icon: <TriangleAlert size={16} /> },
    { label: "Slowest stage", value: worst ?? "N/A", note: worst ? `${ms(r.stage_means_ms[worst])} mean in slow searches` : "No stage timings yet", icon: <Gauge size={16} /> },
  ];
  return <>
    <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>
    <Panel title="Mean time per stage" eyebrow="SLOW SEARCHES ONLY"><div className="cc-performance">{STAGES.map(stage => <div key={stage}><span>{stage}</span><strong>{ms(r.stage_means_ms[stage])}</strong></div>)}</div><p className="cc-note">Retrieval finds candidates in PostgreSQL, ranking scores them with BM25 (including document-frequency lookups), metadata loads titles and URLs, and snippets loads body text. Set SEARCH_SLOW_QUERY_MS on the backend to change the threshold.</p></Panel>
    <Panel title="Repeated slow queries" eyebrow="GROUPED BY QUERY AND MODE"><div className="cc-table-wrap" role="region" aria-label="Repeated slow queries" tabIndex={0}><table className="cc-table" role="table"><caption>Queries that were slow more than once are the best candidates to profile.</caption><thead><tr><th scope="col">Query</th><th scope="col">Mode</th><th scope="col">Times slow</th><th scope="col">Timed out</th><th scope="col">Mean</th><th scope="col">Max</th></tr></thead><tbody>{r.repeated.map((row, i) => <tr key={`${row.query}-${row.mode}-${i}`}><td>{row.query}</td><td data-label="Mode">{row.mode}</td><td data-label="Times slow">{n(row.count)}</td><td data-label="Timed out">{n(row.timed_out)}</td><td data-label="Mean">{ms(row.mean_ms)}</td><td data-label="Max">{ms(row.max_ms)}</td></tr>)}</tbody></table></div>{!r.repeated.length && <Empty>No slow searches in this window.</Empty>}</Panel>
    <Panel title="Recent slow searches" eyebrow="NEWEST FIRST"><div className="cc-table-wrap" role="region" aria-label="Recent slow searches" tabIndex={0}><table className="cc-table" role="table"><caption>Each slow or timed-out search with its time in every stage.</caption><thead><tr><th scope="col">Query</th><th scope="col">Outcome</th><th scope="col">Total</th>{STAGES.map(stage => <th scope="col" key={stage}>{stage}</th>)}<th scope="col">Results</th><th scope="col">When</th></tr></thead><tbody>{r.queries.map((q, i) => <tr key={`${q.recorded_at}-${i}`}><td>{q.query}<small>{q.mode}{q.category ? ` · ${q.category}` : ""} · page {q.page}</small></td><td data-label="Outcome">{q.outcome}{q.stopped_in && <small>stopped in {q.stopped_in}</small>}</td><td data-label="Total">{ms(q.elapsed_ms)}</td>{STAGES.map(stage => <td key={stage} data-label={stage}>{ms(q.stages[stage])}</td>)}<td data-label="Results">{q.result_count ?? "N/A"}</td><td data-label="When">{time(q.recorded_at)}</td></tr>)}</tbody></table></div>{!r.queries.length && <Empty>No slow searches in this window.</Empty>}</Panel>
  </>;
}

function MetricRow({ label, values, k }: { label: string; values: RankerMetrics; k: number }) {
  return <tr><td>{label}</td>{["precision", "mrr", "ndcg"].map(name => <td key={name} data-label={name}>{score(values[`${name}_at_${k}`])}</td>)}</tr>;
}

function Metrics({ canEdit, onJudge }: { canEdit: boolean; onJudge: (id: string) => void }) {
  const [k, setK] = useState(10), [refresh, setRefresh] = useState(0), [busy, setBusy] = useState(""), [message, setMessage] = useState("");
  const report = usePolling(`/api/admin/search-quality/evaluation?k=${k}`, isEvaluationReport, 60000, false, refresh);
  const r: EvaluationReport | null = report.data;
  async function run(label: string, action: () => Promise<unknown>) {
    setBusy(label); setMessage("");
    try { await action(); setRefresh(v => v + 1); } catch (e) { setMessage(e instanceof Error ? e.message : "The action failed."); } finally { setBusy(""); }
  }
  async function poolAll() {
    for (const q of r?.queries ?? []) {
      setBusy(`Pooling ${q.id}`);
      await write("post", `/api/admin/search-quality/queries/${encodeURIComponent(q.id)}/pool`);
    }
  }
  return <>
    <div className="cc-control-bar"><label><span>Cut-off</span><select value={k} aria-label="Metric cut-off" onChange={e => setK(Number(e.target.value))}><option value={10}>@10</option><option value={5}>@5</option></select></label><div className="cc-refresh-controls">{canEdit && <><button className="admin-button secondary" disabled={!!busy} onClick={() => run("Importing", () => write("post", "/api/admin/search-quality/queries/import"))}>Import the 36-query set</button><button className="admin-button secondary" disabled={!!busy || !r?.queries.length} onClick={() => run("Pooling", poolAll)}>Capture pools for all</button></>}<button className="admin-icon-button" disabled={report.loading} aria-label="Refresh metrics" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
    {busy && <p className="cc-note" role="status"><Loader2 size={13} className="admin-spin" /> {busy}…</p>}
    {message && <ErrorBox title="Action failed" message={message} />}
    {report.error && <ErrorBox title="Metrics are unavailable" message={report.error} onRetry={() => setRefresh(v => v + 1)} />}
    {r ? <>
      <Panel title="BM25 against PostgreSQL ranking" eyebrow={`${r.aggregate.complete_queries} OF ${r.aggregate.total_queries} QUERIES FULLY JUDGED`}>
        <div className="cc-table-wrap" role="region" aria-label="Aggregate relevance metrics" tabIndex={0}><table className="cc-table" role="table"><caption>Means over fully judged queries only. Grades: 0 not relevant, 1 related, 2 relevant, 3 perfect.</caption><thead><tr><th scope="col">Ranker</th><th scope="col">P@{k}</th><th scope="col">MRR@{k}</th><th scope="col">nDCG@{k}</th></tr></thead><tbody><MetricRow label="BM25 (production)" values={r.aggregate.bm25} k={k} /><MetricRow label="PostgreSQL ts_rank_cd" values={r.aggregate.postgresql} k={k} /></tbody></table></div>
        <p className="cc-note">Candidate recall (judged positives that reached the candidate pool): {score(r.aggregate.candidate_recall)}. {r.aggregate.status === "complete" ? "Every query is fully judged." : "These numbers are provisional until every query has a pool and at least one positive grade (or is marked as having none)."}</p>
      </Panel>
      <Panel title="Judging queries" eyebrow="PER QUERY">
        <div className="cc-table-wrap" role="region" aria-label="Judging queries" tabIndex={0}><table className="cc-table" role="table"><caption>Open a query to grade its pooled results.</caption><thead><tr><th scope="col">Query</th><th scope="col">Status</th><th scope="col">Graded</th><th scope="col">BM25 nDCG@{k}</th><th scope="col">PG nDCG@{k}</th><th scope="col">Pooled</th></tr></thead><tbody>{r.queries.map(q => <tr key={q.id}><td><button className="admin-text-link" onClick={() => onJudge(q.id)}>{q.id}: {q.query}</button><small>{q.mode}{q.source ? ` · ${q.source}` : ""}{q.stratum ? ` · ${q.stratum}` : ""}</small></td><td data-label="Status">{q.status.replaceAll("_", " ")}{q.reason && <small>{q.reason}</small>}</td><td data-label="Graded">{q.graded} / {q.pooled}<small>{q.positives} positive</small></td><td data-label="BM25 nDCG">{score(q.bm25?.[`ndcg_at_${k}`])}</td><td data-label="PG nDCG">{score(q.postgresql?.[`ndcg_at_${k}`])}</td><td data-label="Pooled">{time(q.last_pooled_at)}</td></tr>)}</tbody></table></div>
        {!r.queries.length && <Empty>No judging queries yet. {canEdit ? "Import the prepared 36-query set to start." : "An administrator needs to import the judging set."}</Empty>}
      </Panel>
    </> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading metrics.</div>}
  </>;
}

function Judge({ canEdit, selected, onSelect }: { canEdit: boolean; selected: string | null; onSelect: (id: string) => void }) {
  const list = usePolling("/api/admin/search-quality/evaluation?k=10", isEvaluationReport, 60000, false, 0);
  const id = selected ?? list.data?.queries[0]?.id ?? null;
  return <>
    <div className="cc-control-bar"><label><span>Query</span><select value={id ?? ""} aria-label="Judging query" onChange={e => onSelect(e.target.value)}>{list.data?.queries.map(q => <option key={q.id} value={q.id}>{q.id}: {q.query} ({q.graded}/{q.pooled})</option>)}</select></label></div>
    {list.error && <ErrorBox title="Judging queries are unavailable" message={list.error} />}
    {list.data && !list.data.queries.length && <Empty>No judging queries yet. Import the set from the Relevance metrics tab.</Empty>}
    {id && <QueryEditor key={id} id={id} canEdit={canEdit} />}
  </>;
}

function QueryEditor({ id, canEdit }: { id: string; canEdit: boolean }) {
  const [reload, setReload] = useState(0), [error, setError] = useState(""), [saving, setSaving] = useState(""), [addUrl, setAddUrl] = useState("");
  const base = `/api/admin/search-quality/queries/${encodeURIComponent(id)}`;
  const loaded = usePolling(base, isJudgingQuery, 60000, false, reload);
  const query: JudgingQuery | null = loaded.data;
  async function save(label: string, action: () => Promise<unknown>) {
    setSaving(label); setError("");
    try { await action(); setReload(v => v + 1); return true; } catch (e) { setError(e instanceof Error ? e.message : "The change could not be saved."); return false; } finally { setSaving(""); }
  }
  const grade = (url: string, value: number | null, note: string) => save("Saving grade", () => write("put", `${base}/judgments`, { url, grade: value, note }));
  const updateQuery = (patch: Partial<JudgingQuery>) => query && save("Saving query", () => write("put", base, { query: query.query, mode: query.mode, source: query.source, stratum: query.stratum, note: query.note, no_relevant_documents: query.no_relevant_documents, ...patch }));
  const graded = query?.judgments.filter(j => j.grade !== null).length ?? 0;
  return <>
    {saving && <p className="cc-note" role="status"><Loader2 size={13} className="admin-spin" /> {saving}…</p>}
    {(error || loaded.error) && <ErrorBox title="Judging problem" message={error || loaded.error} />}
    {!query && !loaded.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading query.</div>}
    {query && <>
      <Panel title={`“${query.query}”`} eyebrow={`${query.mode.toUpperCase()}${query.source ? ` · ${query.source.toUpperCase()}` : ""} · ${graded} OF ${query.judgments.length} GRADED`}>
        <p className="cc-panel-intro">Grade each page by how well it answers this query: 0 not relevant, 1 related, 2 relevant, 3 perfect answer. Pages are listed alphabetically by URL, without either ranker&apos;s position, so the order cannot bias a grade.</p>
        <div className="sq-query-fields">
          <label><span>Query note</span><textarea defaultValue={query.note} key={`note-${query.id}-${query.note}`} maxLength={2000} disabled={!canEdit} onBlur={e => e.target.value !== query.note && updateQuery({ note: e.target.value })} /></label>
          <label className="sq-check"><input type="checkbox" checked={query.no_relevant_documents} disabled={!canEdit} onChange={e => updateQuery({ no_relevant_documents: e.target.checked })} /> The corpus has no relevant page for this query</label>
        </div>
      </Panel>
      <Panel title="Pooled results" eyebrow="TOP 10 FROM BOTH RANKERS, PLUS PAGES YOU ADDED" action={canEdit ? <button className="admin-button secondary" disabled={!!saving} onClick={() => save("Capturing pool", () => write("post", `${base}/pool`))}><Scale size={13} /> Capture pool</button> : undefined}>
        <ul className="sq-judgments">{query.judgments.map(j => <li key={j.url}>
          <div className="sq-doc"><a className="admin-text-link" href={j.url} target="_blank" rel="noreferrer noopener">{j.title || j.url}</a><small>{j.url}{j.origin === "added" ? " · added by hand" : ""}{j.judged_by ? ` · graded by ${j.judged_by}` : ""}</small></div>
          <div className="sq-grades" role="group" aria-label={`Grade for ${j.title || j.url}`}>{GRADES.map(([value, label]) => <button key={value} className={`sq-grade${j.grade === Number(value) ? " active" : ""}`} aria-pressed={j.grade === Number(value)} title={label} disabled={!canEdit || !!saving} onClick={() => grade(j.url, j.grade === Number(value) ? null : Number(value), j.note)}>{value}</button>)}</div>
          <textarea className="sq-note" aria-label={`Note for ${j.title || j.url}`} placeholder="Why this grade (optional)" defaultValue={j.note} key={`${j.url}-${j.note}`} maxLength={2000} disabled={!canEdit} onBlur={e => e.target.value !== j.note && grade(j.url, j.grade, e.target.value)} />
          {canEdit && j.origin === "added" && <button className="admin-text-link" disabled={!!saving} onClick={() => save("Removing page", () => write("delete", `${base}/judgments?url=${encodeURIComponent(j.url)}`))}>Remove</button>}
        </li>)}</ul>
        {!query.judgments.length && <Empty>{canEdit ? "No pool yet. Capture a pool to list the pages both rankers return." : "No pool has been captured for this query yet."}</Empty>}
        {canEdit && <form className="sq-add" onSubmit={e => { e.preventDefault(); const url = addUrl.trim(); if (url) void save("Adding page", () => write("put", `${base}/judgments`, { url, grade: null, note: "", add: true })).then(ok => { if (ok) setAddUrl(""); }); }}><label><span>Add a relevant page that neither ranker found</span><input type="url" value={addUrl} required maxLength={2048} placeholder="https://…" onChange={e => setAddUrl(e.target.value)} /></label><button className="admin-button secondary" disabled={!!saving}>Add page</button></form>}
      </Panel>
    </>}
  </>;
}
