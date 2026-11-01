"use client";

import { useEffect, useState } from "react";
import { CircleAlert, Loader2, Search, SpellCheck } from "lucide-react";
import { isVocabularyReport, type VocabularyReport, type VocabularyTerm } from "@/lib/vocabulary-report";
import { Empty, Panel, usePolling } from "./crawler-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;

// The vocabulary changes slowly and its counts scan every term, so poll gently.
export default function VocabularyReportView({ auto, refresh }: { auto: boolean; refresh: number }) {
  const [search, setSearch] = useState(""), [query, setQuery] = useState("");
  useEffect(() => { const timer = window.setTimeout(() => setQuery(search.trim()), 350); return () => window.clearTimeout(timer); }, [search]);
  const report = usePolling(`/api/admin/indexer/vocabulary${query ? `?q=${encodeURIComponent(query)}` : ""}`, isVocabularyReport, 30000, auto, refresh);
  const r = report.data;
  return <>
    {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Vocabulary data may be out of date" : "Vocabulary data is unavailable"}</strong><p>{report.error}</p></div></div>}
    {r ? <>
      <Metrics report={r} />
      <div className="cc-grid cc-grid-equal"><Distribution report={r} /><Health report={r} /></div>
      <Panel title="Look up a term" eyebrow="TRIGRAM MATCHES · SAME LOOKUP AS FUZZY SEARCH">
        <p className="cc-panel-intro">Type a word, including a misspelling, to see which indexed terms fuzzy search can suggest for it. Terms are stems, so “running” is stored as “run”.</p>
        <div className="cc-filters" style={{ padding: "0 26px" }}><label className="admin-search"><Search size={15} /><input value={search} maxLength={64} onChange={e => setSearch(e.target.value)} placeholder="Try pyhton or kubernets" aria-label="Look up a vocabulary term" /></label>{search && <button className="admin-text-link" onClick={() => setSearch("")}>Clear</button>}</div>
        {r.query ? <TermTable terms={r.matches ?? []} similarity caption={`Vocabulary terms similar to ${r.query}.`} empty={`No indexed term is similar to “${r.query}”.`} /> : <Empty>Enter a term to compare it with the vocabulary.</Empty>}
      </Panel>
      <Panel title="Most common terms" eyebrow="TOP 30 BY DOCUMENT FREQUENCY"><p className="cc-panel-intro">Terms found in the most indexed documents. Very common terms carry little signal for ranking or spelling suggestions.</p><TermTable terms={r.top_terms} caption="The most common vocabulary terms." empty="The vocabulary is empty. Index documents or run the vocabulary rebuild." /></Panel>
    </> : <div className="cc-empty">{report.loading ? <><Loader2 className="admin-spin" size={28} /><p>Counting vocabulary terms…</p></> : <><SpellCheck size={28} /><p>Apply the search_terms migration and run the indexer to build the vocabulary.</p></>}</div>}
  </>;
}

function Metrics({ report: r }: { report: VocabularyReport }) {
  const s = r.summary;
  const cards = [
    { label: "Unique terms", value: n(s.total_terms), note: "Rows in search_terms" },
    { label: "Indexed documents", value: n(s.indexed_documents), note: "Rows in search_index" },
    { label: "Terms per document", value: metric(s.average_terms_per_document), note: `${n(s.total_postings)} term-document pairs` },
    { label: "Single-document terms", value: metric(s.singleton_percent, "%"), note: `${n(s.singleton_terms)} terms seen once` },
    { label: "Most common term", value: r.top_terms[0]?.term ?? "N/A", note: r.top_terms[0] ? `${n(r.top_terms[0].document_frequency)} documents` : "No terms yet" },
    { label: "Updated", value: new Date(r.generated_at).toLocaleTimeString(), note: "Refreshes every 30s" },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}<SpellCheck size={16} /></div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}
function Distribution({ report: r }: { report: VocabularyReport }) {
  const total = r.summary.total_terms;
  return <Panel title="Document frequency" eyebrow="HOW MANY DOCUMENTS EACH TERM APPEARS IN"><div className="cc-funnel">{r.distribution.map(b => <div key={b.label}><div><span>{b.label} {b.label === "1" ? "document" : "documents"}</span><strong>{n(b.terms)}</strong></div><div className="cc-funnel-track"><i style={{ width: `${total ? 100 * b.terms / total : 0}%` }} /></div></div>)}</div><p className="cc-note">Bars show the share of all {n(total)} terms. A long tail of single-document terms is normal and often holds typos from source pages.</p></Panel>;
}
function Health({ report: r }: { report: VocabularyReport }) {
  const s = r.summary, healthy = !s.zero_frequency_terms && !s.overcounted_terms;
  return <Panel title="Consistency" eyebrow="DRIFT CHECKS AGAINST SEARCH_INDEX"><div className="cc-funnel">{([["Zero-frequency terms", s.zero_frequency_terms], ["Terms counted in more documents than exist", s.overcounted_terms]] as [string, number][]).map(([label, value]) => <div key={label}><div><span>{label}</span><strong>{n(value)}</strong></div></div>)}</div>{healthy ? <p className="cc-note">No drift detected. Highest document frequency is {n(s.max_document_frequency)} of {n(s.indexed_documents)} indexed documents.</p> : <p className="cc-note cc-warning">The vocabulary has drifted from the search index. Stop the workers and run <code>python -m indexer.vocabulary_rebuild</code> to recount it.</p>}</Panel>;
}
function TermTable({ terms, similarity = false, caption, empty }: { terms: (VocabularyTerm & { similarity?: number })[]; similarity?: boolean; caption: string; empty: string }) {
  if (!terms.length) return <Empty>{empty}</Empty>;
  return <div className="cc-table-wrap" role="region" aria-label={caption} tabIndex={0}><table className="cc-table" role="table"><caption>{caption}</caption><thead><tr><th scope="col">Term</th><th scope="col">Documents</th><th scope="col">Share of index</th>{similarity && <th scope="col">Similarity</th>}</tr></thead><tbody>{terms.map(t => <tr key={t.term}><td><code>{t.term}</code></td><td data-label="Documents">{n(t.document_frequency)}</td><td data-label="Share of index">{metric(t.document_percent, "%")}</td>{similarity && <td data-label="Similarity">{metric(t.similarity)}</td>}</tr>)}</tbody></table></div>;
}
