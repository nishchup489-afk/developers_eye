"use client";

import { useEffect, useState } from "react";
import { ArrowDownToLine, ArrowRight, ChevronRight, CircleAlert, Clock3, FileSearch, Gauge, Layers3, Loader2, Pause, Play, RefreshCw, ScanSearch, ShieldCheck, Target } from "lucide-react";
import { isIndexerReport, statusLabel, type IndexerReport, type IndexedDocument, type PendingDocument } from "@/lib/indexer-report";
import CrawlInspector, { Badge, type Inspection } from "./crawl-inspector";
import { Empty, Panel, usePolling } from "./crawler-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Never";
const tabs = [["overview", "Overview"], ["backlog", "Backlog"], ["recent", "Recently indexed"], ["sources", "Source coverage"]];
const reasons: Record<PendingDocument["reason"], string> = { missing: "Never indexed", reindex_requested: "Reindex requested", old_version: "Older index version", content_changed: "Content changed" };

export default function IndexerControlCenter() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [clock, setClock] = useState(0);
  const [tab, setTab] = useState("overview"), [source, setSource] = useState("");
  const [selection, setSelection] = useState<Inspection | null>(null);
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 5000); return () => window.clearInterval(timer); }, []);
  const report = usePolling(`/api/admin/indexer/report${source ? `?source_id=${source}` : ""}`, isIndexerReport, 5000, auto, refresh);
  const r = report.data;
  const stale = !!r && clock > 0 && clock - Date.parse(r.generated_at) > 20000;
  const live = !!r && !report.error && !stale && auto;
  function download() {
    const blob = new Blob([JSON.stringify({ report: r, filters: { source_id: source || null } }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = `indexer-snapshot-${new Date().toISOString().slice(0, 10)}.json`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const inspect = (id: number) => setSelection({ type: "documents", id });
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Indexer</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><ScanSearch size={12} /> INDEXER CONTROL CENTER · LOCAL</div><h1>Every document.<br /><span>Ready to find</span><span className="admin-heading-dot">.</span></h1><p>Follow stored documents into the search index, and see what is still waiting.</p></div><div className="cc-heading-actions"><span className={`cc-worker-status ${live && r.activity.status === "indexing" ? "online" : ""}`}><span className="admin-tiny-dot" />{!r ? "Indexer status unavailable" : !live ? "Indexer status at snapshot" : statusLabel[r.activity.status]}</span><button className="admin-button secondary" onClick={download} disabled={!r}><ArrowDownToLine size={15} /> Export snapshot</button></div></div>
      <div className="cc-control-bar"><label><span>Source</span><select value={source} aria-label="Filter source" onChange={e => setSource(e.target.value)}><option value="">All sources</option>{(r?.sources ?? []).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 5s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
      <div className="cc-connection" role="status"><span className={`admin-tiny-dot ${live ? "" : "amber"}`} />{report.loading ? "Reading committed index state…" : report.error ? "Indexer reporting interrupted" : live ? "Connected to indexer reporting" : "Snapshot view"}<span>{r ? `Updated ${time(r.generated_at)} · index v${r.index_version}` : "Waiting for real index data"}</span></div>
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "Indexer data is unavailable"}</strong><p>{report.error}</p><a className="admin-text-link" href="/admin/login">Sign in again if your session expired</a></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      <Metrics report={r} />
      <nav className="cc-tabs" aria-label="Indexer sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {r ? <>
        {tab === "overview" && <>
          <div className="cc-grid"><Throughput report={r} /><Coverage report={r} /></div>
          <div className="cc-grid cc-grid-equal"><Panel title="Recently indexed" eyebrow="LATEST 8 INDEX WRITES" action={<button className="admin-text-link" onClick={() => setTab("recent")}>All recent <ArrowRight size={14} /></button>}><RecentList documents={r.recent.slice(0, 8)} onInspect={inspect} /></Panel><Panel title="Waiting to be indexed" eyebrow="NEXT 8 IN SELECTOR ORDER" action={<button className="admin-text-link" onClick={() => setTab("backlog")}>Full backlog <ArrowRight size={14} /></button>}><PendingList documents={r.pending.slice(0, 8)} onInspect={inspect} /></Panel></div>
        </>}
        {tab === "backlog" && <Panel title="Index backlog" eyebrow={`${n(r.coverage.pending_documents)} PENDING · FIRST 30 BY DOCUMENT ID`}><p className="cc-panel-intro">Available documents whose search index is missing, out of date, or from an older index version. The worker picks them up in this order.</p><PendingList documents={r.pending} onInspect={inspect} /></Panel>}
        {tab === "recent" && <Panel title="Recently indexed" eyebrow="LATEST 30 INDEX WRITES"><p className="cc-panel-intro">Open a document to see the content the indexer read from your database.</p><RecentList documents={r.recent} onInspect={inspect} /></Panel>}
        {tab === "sources" && <SourceTable report={r} onSource={value => { setSource(value); setTab("backlog"); }} />}
      </> : <div className="cc-empty">{report.loading ? <><Loader2 className="admin-spin" size={28} /><p>Loading index measurements…</p></> : <><ScanSearch size={28} /><p>Connect the backend and apply the search index migration to start inspecting the indexer.</p></>}</div>}
      <footer className="admin-footer"><span>DEVELOPER&apos;S EYE <span className="admin-accent">/</span> INDEXER CONTROL CENTER</span><span>Refresh: 5s · Activity inferred from committed index writes · Times: your browser timezone</span></footer>
    </main>{selection && <CrawlInspector selection={selection} onClose={() => setSelection(null)} onSelect={setSelection} />}
  </>;
}

function Metrics({ report: r }: { report: IndexerReport | null }) {
  const c = r?.coverage, a = r?.activity;
  const cards = [
    { label: "Index coverage", value: metric(c?.coverage_percent, "%"), note: "Current of available documents", icon: <Target size={16} /> },
    { label: "Up to date", value: c ? n(c.current_documents) : "N/A", note: c ? `of ${n(c.available_documents)} available` : "Available documents", icon: <ShieldCheck size={16} /> },
    { label: "Pending", value: c ? n(c.pending_documents) : "N/A", note: c ? `${n(c.missing_documents)} missing · ${n(c.stale_documents)} stale` : "Missing + stale", icon: <Layers3 size={16} /> },
    { label: "Index rate", value: metric(a?.docs_per_minute, "/min"), note: "Rolling 5 minutes", icon: <Gauge size={16} /> },
    { label: "Indexed last hour", value: a ? n(a.indexed_last_hour) : "N/A", note: a ? `${n(a.indexed_last_24h)} in 24 hours` : "Latest write per document", icon: <ScanSearch size={16} /> },
    { label: "Last index write", value: a?.last_indexed_at ? new Date(a.last_indexed_at).toLocaleTimeString() : a ? "Never" : "N/A", note: a?.last_indexed_at ? new Date(a.last_indexed_at).toLocaleDateString() : "Committed search_index row", icon: <Clock3 size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}
function Throughput({ report: r }: { report: IndexerReport }) {
  const max = Math.max(1, ...r.throughput.map(t => t.indexed)), total = r.throughput.reduce((sum, t) => sum + t.indexed, 0);
  return <Panel title="Index throughput" eyebrow="LAST 60 MINUTES · SELECTED SOURCE" action={<span className="cc-panel-tag">{n(total)} documents</span>}><div className="cc-chart" role="img" aria-label={`${total} documents indexed over the last 60 minute buckets. Peak ${max} in a minute.`}><div className="cc-chart-scale"><span>{max}/min</span><span>{Math.round(max / 2)}</span><span>0</span></div><div className="cc-bars">{r.throughput.map(t => <div key={t.at} title={`${time(t.at)}: ${t.indexed} indexed`}><i style={{ height: `${100 * t.indexed / max}%` }}><b style={{ height: "100%" }} /></i></div>)}</div></div><div className="cc-chart-axis"><span>{new Date(r.throughput[0].at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span>30m ago</span><span>Now</span></div><p className="cc-note">Counts each document at its most recent index write, so a document re-indexed later moves to its newer minute.</p></Panel>;
}
function Coverage({ report: r }: { report: IndexerReport }) {
  const c = r.coverage;
  const rows: [string, number][] = [["Up to date", c.current_documents], ["Never indexed", c.missing_documents], ["Stale or older version", c.stale_documents], ["Reindex requested", c.reindex_requested]];
  return <Panel title="Index coverage" eyebrow="AVAILABLE DOCUMENTS · CURRENT STATE"><div className="cc-funnel">{rows.map(([label, value], i) => <div key={label}><div><span>{label}</span><strong>{n(value)}</strong></div><div className="cc-funnel-track"><i style={{ width: `${c.available_documents ? 100 * value / c.available_documents : 0}%`, opacity: i ? .55 : 1 }} /></div></div>)}</div><p className="cc-note">{n(c.available_documents)} available of {n(c.total_documents)} stored documents · {n(c.indexed_rows)} rows in search_index.</p>{c.unavailable_index_rows > 0 && <p className="cc-note cc-warning">{n(c.unavailable_index_rows)} unavailable documents are still indexed. The worker removes them on its next removal pass.</p>}{r.activity.status === "backlog_waiting" && <p className="cc-note cc-warning">Documents are waiting but nothing was indexed in the last 2 minutes. Check that the indexer worker is running.</p>}</Panel>;
}
function RecentList({ documents, onInspect }: { documents: IndexedDocument[]; onInspect: (id: number) => void }) {
  return documents.length ? <div className="cc-documents">{documents.map(d => <button key={d.document_id} className="cc-document" onClick={() => onInspect(d.document_id)}><span className="cc-document-icon"><FileSearch size={18} /></span><span><strong>{d.title}</strong>{!d.current && <Badge value="stale" />}<small>{d.canonical_url}</small><small>{d.source} · {d.index_version} · Indexed {time(d.indexed_at)}</small></span><ChevronRight size={15} /></button>)}</div> : <Empty>Nothing has been indexed yet. Start the indexer worker to build the search index.</Empty>;
}
function PendingList({ documents, onInspect }: { documents: PendingDocument[]; onInspect: (id: number) => void }) {
  return documents.length ? <div className="cc-documents">{documents.map(d => <button key={d.document_id} className="cc-document" onClick={() => onInspect(d.document_id)}><span className="cc-document-icon"><FileSearch size={18} /></span><span><strong>{d.title}</strong><Badge value={reasons[d.reason]} /><small>{d.canonical_url}</small><small>{d.source} · Changed {time(d.updated_at)}{d.indexed_at ? ` · Last indexed ${time(d.indexed_at)}` : ""}</small></span><ChevronRight size={15} /></button>)}</div> : <Empty>The index is caught up. No available document is waiting.</Empty>;
}
function SourceTable({ report: r, onSource }: { report: IndexerReport; onSource: (value: string) => void }) {
  return <Panel title="Source coverage" eyebrow="ALL SOURCES · CURRENT STATE"><div className="cc-table-wrap" role="region" aria-label="Source coverage records" tabIndex={0}><table className="cc-table" role="table"><caption>Index coverage and backlog for each registered source.</caption><thead><tr><th scope="col">Source</th><th scope="col">Available</th><th scope="col">Up to date</th><th scope="col">Coverage</th><th scope="col">Missing / stale</th><th scope="col">Last indexed</th></tr></thead><tbody>{r.sources.map(s => <tr key={s.id}><td><button className="admin-text-link" onClick={() => onSource(String(s.id))}>{s.name}<ArrowRight size={12} /></button><small>{s.slug}</small></td><td data-label="Available">{n(s.available)}</td><td data-label="Up to date">{n(s.current)}</td><td data-label="Coverage">{metric(s.coverage_percent, "%")}</td><td data-label="Missing / stale">{n(s.missing)} / {n(s.stale)}</td><td data-label="Last indexed">{time(s.last_indexed_at)}</td></tr>)}</tbody></table></div>{!r.sources.length && <Empty>No sources are registered.</Empty>}</Panel>;
}
