"use client";

import { useState } from "react";
import { BookOpenText, ChevronRight, CircleAlert, Clock3, Database, FileText, Globe2, Library, Loader2, Pause, Play, RefreshCw, ShieldCheck, Type } from "lucide-react";
import { bytes, isCorpusReport, type CorpusAge, type CorpusReport, type CorpusShare } from "@/lib/system-report";
import { Empty, Panel, usePolling } from "./crawler-control-center";
import { Tone } from "./system-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}${suffix}`;
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Never";
const tabs = [["overview", "Overview"], ["sources", "Sources"], ["hosts", "Hosts"], ["storage", "Storage"]];

export default function CorpusControlCenter() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [tab, setTab] = useState("overview");
  const report = usePolling("/api/admin/system/corpus", isCorpusReport, 60000, auto, refresh);
  const r = report.data;
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Corpus</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><Library size={12} /> WHAT SEARCH CAN FIND</div><h1>The whole corpus.<br /><span>At a glance</span><span className="admin-heading-dot">.</span></h1><p>How many documents we hold, where they came from, how much space they take and how fresh they are.</p></div><div className="cc-heading-actions">{r && <Tone value={r.estimates.exact ? "Exact counts" : "Sampled estimate"} status={r.estimates.exact ? "ok" : "info"} />}</div></div>
      <div className="cc-control-bar"><span className="cc-note">{r ? `Updated ${time(r.generated_at)}` : ""}</span><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 60s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "Corpus data is unavailable"}</strong><p>{report.error}</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      {r && <Cards report={r} />}
      <nav className="cc-tabs" aria-label="Corpus sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {r ? <>
        {tab === "overview" && <><div className="cc-grid cc-grid-equal"><Freshness report={r} /><Search report={r} /></div><div className="cc-grid cc-grid-equal"><Shares title="Document types" eyebrow="FROM THE CRAWLER" rows={r.document_types} /><Shares title="Result categories" eyebrow="FROM THE INDEX" rows={r.categories} /></div></>}
        {tab === "sources" && <Sources report={r} />}
        {tab === "hosts" && <Hosts report={r} />}
        {tab === "storage" && <Storage report={r} />}
        {!r.estimates.exact && <p className="cc-note">This corpus is too large to count on every refresh. Totals come from the planner, and breakdowns scale a sample of {n(r.estimates.sampled_documents)} documents and {n(r.estimates.sampled_index_rows)} index rows, so they shift a little between refreshes and small hosts can be missing.</p>}
      </> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading corpus snapshot.</div>}
    </main>
  </>;
}

function Cards({ report: r }: { report: CorpusReport }) {
  const s = r.summary, approx = r.estimates.exact ? "" : "≈ ";
  const cards = [
    { label: "Documents", value: approx + n(s.total_documents), note: `${n(s.unavailable_documents)} no longer available`, icon: <FileText size={16} /> },
    { label: "Searchable", value: approx + n(s.indexed_documents), note: `${metric(s.indexed_percent, "%")} of available documents`, icon: <BookOpenText size={16} /> },
    { label: "Extracted text", value: bytes(s.total_body_bytes), note: `${bytes(s.average_body_bytes)} per document`, icon: <Database size={16} /> },
    { label: "Vocabulary", value: (r.vocabulary.exact ? "" : "≈ ") + n(r.vocabulary.terms), note: `${n(r.vocabulary.pending_changes)} changes waiting to apply`, icon: <Type size={16} /> },
    { label: "Sources", value: n(s.sources), note: `${n(s.enabled_sources)} enabled · ${n(s.hosts)}${s.hosts_exact ? "" : "+"} hosts`, icon: <Globe2 size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}

function Ages({ title, rows }: { title: string; rows: CorpusAge[] }) {
  return <div className="cc-funnel"><strong>{title}</strong>{rows.map(age => <div key={age.id}><div><span>{age.label}</span><strong>{n(age.documents)} · {metric(age.share_percent, "%")}</strong></div><div className="cc-funnel-track"><i style={{ width: `${age.share_percent ?? 0}%` }} /></div></div>)}</div>;
}

function Freshness({ report: r }: { report: CorpusReport }) {
  const f = r.freshness;
  return <Panel title="Freshness" eyebrow="WHEN DOCUMENTS WERE LAST TOUCHED" action={<Clock3 size={16} />}>
    <Ages title="Last seen by the crawler" rows={f.seen} /><Ages title="Last written to the index" rows={f.indexed} />
    <p className="cc-note">Last crawl: {time(f.last_crawled_at)}. Last indexer batch: {f.last_indexed_at ? time(f.last_indexed_at) : "no heartbeat recorded"}. The Indexer page has the exact backlog.</p>
  </Panel>;
}

function Search({ report: r }: { report: CorpusReport }) {
  const b = r.bm25;
  return <Panel title="Ranking snapshot" eyebrow="BM25 CORPUS STATISTICS · THIS API PROCESS" action={<Tone value={b.loaded ? "loaded" : "not loaded"} status={b.loaded ? "ok" : "critical"} />}>
    <ul className="sys-health">
      <li><span>Documents ranked against</span><strong>{metric(b.documents)}</strong></li>
      <li><span>Average text length</span><strong>{metric(b.average_text_length, " terms")}</strong></li>
      <li><span>Average code length</span><strong>{metric(b.average_code_length, " terms")}</strong></li>
      <li><span>Loaded</span><strong>{time(b.loaded_at)}</strong></li>
    </ul>
    <p className="cc-note">Each API process refreshes its own snapshot every 10 minutes, so a different process may answer the next refresh.</p>
  </Panel>;
}

function Shares({ title, eyebrow, rows }: { title: string; eyebrow: string; rows: CorpusShare[] }) {
  return <Panel title={title} eyebrow={eyebrow}>{rows.length ? <div className="cc-funnel">{rows.map(row => <div key={row.name}><div><span>{row.name}</span><strong>{n(row.documents)} · {metric(row.share_percent, "%")}</strong></div><div className="cc-funnel-track"><i style={{ width: `${row.share_percent ?? 0}%` }} /></div></div>)}</div> : <Empty>No documents yet.</Empty>}</Panel>;
}

function Sources({ report: r }: { report: CorpusReport }) {
  return <Panel title="Documents by source" eyebrow="LARGEST FIRST"><div className="cc-table-wrap" role="region" aria-label="Source records" tabIndex={0}><table className="cc-table" role="table"><caption>Documents, availability and average size for each source.</caption><thead><tr><th scope="col">Source</th><th scope="col">Documents</th><th scope="col">Available</th><th scope="col">Share</th><th scope="col">Average text</th></tr></thead>
    <tbody>{r.sources.map(s => <tr key={s.id}><td>{s.name}<small>{s.slug}{s.enabled ? "" : " · disabled"}</small></td><td data-label="Documents">{n(s.documents)}</td><td data-label="Available">{n(s.available)}</td><td data-label="Share">{metric(s.share_percent, "%")}</td><td data-label="Average text">{bytes(s.average_body_bytes)}</td></tr>)}</tbody></table></div>{!r.sources.length && <Empty>No sources registered.</Empty>}</Panel>;
}

function Hosts({ report: r }: { report: CorpusReport }) {
  return <Panel title="Documents by host" eyebrow="TOP 50 HOSTS"><div className="cc-table-wrap" role="region" aria-label="Host records" tabIndex={0}><table className="cc-table" role="table"><caption>Documents and corpus share for each host.</caption><thead><tr><th scope="col">Host</th><th scope="col">Documents</th><th scope="col">Share</th></tr></thead>
    <tbody>{r.hosts.map(h => <tr key={h.name}><td>{h.name}</td><td data-label="Documents">{n(h.documents)}</td><td data-label="Share">{metric(h.share_percent, "%")}</td></tr>)}</tbody></table></div>{!r.hosts.length && <Empty>No documents yet.</Empty>}</Panel>;
}

function Storage({ report: r }: { report: CorpusReport }) {
  return <Panel title="Space used" eyebrow="SEARCH TABLES"><div className="cc-table-wrap" role="region" aria-label="Storage records" tabIndex={0}><table className="cc-table" role="table"><caption>Disk used by each search table.</caption><thead><tr><th scope="col">Table</th><th scope="col">Total</th><th scope="col">Heap / index / TOAST</th><th scope="col">Per document</th></tr></thead>
    <tbody>{r.storage.map(t => <tr key={t.table}><td>{t.table}</td><td data-label="Total">{bytes(t.total_bytes)}</td><td data-label="Heap / index / TOAST">{bytes(t.heap_bytes)} / {bytes(t.index_bytes)} / {bytes(t.toast_bytes)}</td><td data-label="Per document">{bytes(t.bytes_per_document)}</td></tr>)}</tbody></table></div><p className="cc-note">The System page compares the whole database against the disk budget.</p></Panel>;
}
