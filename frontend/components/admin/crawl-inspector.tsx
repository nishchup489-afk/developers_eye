"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ExternalLink, FileText, Loader2, X } from "lucide-react";
import { isAttemptDetail, isDocumentDetail, object, type AttemptDetail, type CrawlEvent, type DocumentDetail } from "@/lib/crawler-monitor";
import { safeHttpUrl } from "@/lib/crawler-report";
import { api } from "@/lib/api-client";

export type Inspection = { type: "documents" | "attempts"; id: number };
const time = (value: string | null) => value ? new Date(value).toLocaleString() : "Not recorded";
export function Badge({ value }: { value: string }) {
  const color = /failed|blocked|stale|offline|unavailable/.test(value) ? "red" : /duplicate|skipped|not_stored|unchanged|stopped|never indexed|reindex|older index|content changed/i.test(value) ? "amber" : "green";
  return <span className={`cc-badge ${color}`}>{value.replaceAll("_", " ")}</span>;
}
export function Url({ value }: { value: string | null }) {
  const href = safeHttpUrl(value);
  return href ? <a className="cc-url" href={href} target="_blank" rel="noreferrer noopener">{value}<ExternalLink size={12} /></a> : <span className="cc-url">{value || "Not recorded"}</span>;
}
export function EventDetails({ event }: { event: CrawlEvent }) {
  return <article className="cc-timeline-event"><div><time>{new Date(event.at).toLocaleTimeString()}</time><strong>{event.stage}</strong><Badge value={event.outcome} /></div><pre>{JSON.stringify(event.details, null, 2)}</pre></article>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="cc-field"><dt>{label}</dt><dd>{children}</dd></div>;
}

export default function CrawlInspector({ selection, onClose, onSelect }: { selection: Inspection; onClose: () => void; onSelect: (value: Inspection) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [loaded, setLoaded] = useState<{ type: string; id: number; data: AttemptDetail | DocumentDetail } | null>(null);
  const [failure, setFailure] = useState<{ type: string; id: number; message: string } | null>(null);
  const [retry, setRetry] = useState(0);
  const [attemptOrigin, setAttemptOrigin] = useState<number | null>(null);
  const data = loaded?.type === selection.type && loaded.id === selection.id ? loaded.data : null;
  const error = failure?.type === selection.type && failure.id === selection.id ? failure.message : "";
  const { type, id } = selection;
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    async function load() {
      try {
        const response = await api.get<unknown>("/admin/crawler/inspect", { params: { type, id }, signal: controller.signal });
        const result = response.data;
        if (response.status !== 200) throw new Error(object(result) && typeof result.error === "string" ? result.error : "Could not load this record.");
        if (!(type === "documents" ? isDocumentDetail(result) : isAttemptDetail(result))) throw new Error("The inspection response is incomplete.");
        if (!cancelled) { setLoaded({ type, id, data: result as AttemptDetail | DocumentDetail }); setFailure(null); }
      } catch (e) { if (!cancelled) setFailure({ type, id, message: e instanceof Error ? e.message : "Could not load record." }); }
    }
    void load();
    return () => { cancelled = true; controller.abort(); };
  }, [id, type, retry]);
  const attempt = selection.type === "attempts" ? data as AttemptDetail | null : null;
  const document = selection.type === "documents" ? data as DocumentDetail | null : null;
  const references = attempt?.telemetry && Array.isArray(attempt.telemetry.documents) ? attempt.telemetry.documents.filter((d): d is Record<string, unknown> => object(d) && typeof d.id === "number") : [];
  return <dialog ref={dialog} className="cc-inspector" aria-labelledby="inspector-title" onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="cc-inspector-inner">
      <header><div><span className="admin-kicker">{selection.type === "documents" ? "PERSISTED CONTENT" : "CRAWL ATTEMPT"}</span><h2 id="inspector-title">{selection.type === "documents" ? "Document inspector" : "Attempt inspector"} <small>#{selection.id}</small></h2></div><button className="admin-icon-button" aria-label="Close inspector" onClick={onClose}><X size={18} /></button></header>
      {selection.type === "documents" && attemptOrigin && <button className="admin-text-link cc-back" onClick={() => onSelect({ type: "attempts", id: attemptOrigin })}><ArrowLeft size={14} /> Back to attempt #{attemptOrigin}</button>}
      {error ? <div className="cc-empty" role="alert"><p>{error}</p><button className="admin-button secondary" onClick={() => setRetry(v => v + 1)}>Retry</button></div> : !data ? <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading record.</div> : null}
      {attempt && <>
        <div className="cc-inspector-status"><Badge value={attempt.outcome ?? "unfinished"} /><span>{attempt.source}</span><span>Target #{attempt.target_id}</span></div>
        <dl className="cc-fields"><Field label="Original URL"><Url value={attempt.url} /></Field><Field label="Normalized URL">{attempt.normalized_url}</Field><Field label="Final URL">{String(attempt.telemetry?.final_url ?? "Not recorded")}</Field><Field label="Redirect chain"><pre>{JSON.stringify(attempt.telemetry?.redirects ?? null, null, 2)}</pre></Field><Field label="HTTP / content type">{attempt.http_status ?? "No response"} � {String(attempt.telemetry?.content_type ?? "Not recorded")}</Field><Field label="Started / finished">{time(attempt.started_at)} / {time(attempt.finished_at)}</Field><Field label="Response size">{attempt.bytes_received === null ? "Not recorded" : `${attempt.bytes_received.toLocaleString()} bytes`}</Field></dl>
        {attempt.error && <p className="cc-inline-error">{attempt.error}</p>}
        <section className="cc-inspector-section"><h3>Persisted documents</h3>{references.length ? references.map((reference, index) => <button key={`${reference.id}-${index}`} className="cc-reference" onClick={() => { setAttemptOrigin(attempt.id); onSelect({ type: "documents", id: reference.id as number }); }}><FileText size={16} /><span>Document #{String(reference.id)}<small>{String(reference.canonical_url)}</small></span><Badge value={reference.duplicate_of ? "duplicate stored" : String(reference.decision)} /></button>) : <p>No document reference was recorded for this attempt.</p>}</section>
        <section className="cc-inspector-section"><h3>Pipeline timeline</h3>{attempt.events.length ? attempt.events.map(event => <EventDetails key={event.id} event={event} />) : <p>This attempt predates stage instrumentation.</p>}</section>
        <details className="cc-details"><summary>Attempt measurements</summary><pre>{JSON.stringify(attempt.telemetry, null, 2)}</pre></details>
      </>}
      {document && <>
        {document.is_available === false && <p className="cc-inline-error">This URL returned HTTP {document.unavailable_http_status}. The stored content is retained for inspection and its search entry has been removed. First observed unavailable: {time(document.unavailable_at ?? null)}.</p>}
        <div className="cc-inspector-status"><Badge value="persisted" /><Badge value={document.matching_content.length ? "matching content" : "unique content hash"} /><span>{document.document_type}</span></div>
        <h3 className="cc-document-title">{document.title}</h3><p className="cc-description">{document.description || "No description stored."}</p>
        <dl className="cc-fields"><Field label="Canonical URL"><Url value={document.canonical_url} /></Field><Field label="Original URL"><Url value={document.original_url} /></Field><Field label="Normalized URL">{document.normalized_url || "Not recorded"}</Field></dl>
        {document.latest_attempt && <button className="cc-reference" onClick={() => onSelect({ type: "attempts", id: document.latest_attempt!.id })}>Latest attempt for this URL: #{document.latest_attempt.id} � HTTP {document.latest_attempt.http_status ?? "not recorded"}<ExternalLink size={13} /></button>}
        <div className="cc-document-stats"><div><strong>{document.word_count.toLocaleString()}</strong><span>Words</span></div><div><strong>{document.body_characters.toLocaleString()}</strong><span>Characters</span></div><div><strong>{document.source}</strong><span>Source</span></div></div>
        {!document.word_count && <p className="cc-inline-error">This stored document has an empty body. Inspect the extractor and processing rules.</p>}
        <section className="cc-inspector-section"><h3>Extracted body</h3><pre className="cc-body">{document.body || "(empty)"}</pre>{document.body_truncated && <p>Preview capped at 200,000 characters. Word count covers the full stored body.</p>}</section>
        <dl className="cc-fields"><Field label="Content hash">{document.content_hash}</Field><Field label="Last observed">{time(document.last_seen_at)}</Field><Field label="Last changed">{time(document.updated_at)}</Field><Field label="Published">{time(document.published_at)}</Field><Field label="Author">{document.author || "Not stored"}</Field></dl>
        {!!document.matching_content.length && <section className="cc-inspector-section"><h3>Matching content at other URLs</h3><p>The writer retains these canonical URLs. Matching hashes are flagged for investigation.</p>{document.matching_content.map(match => <button className="cc-reference" key={match.id} onClick={() => onSelect({ type: "documents", id: match.id })}>#{match.id} � {match.canonical_url}</button>)}</section>}
        <details className="cc-details"><summary>Stored metadata</summary><pre>{JSON.stringify(document.metadata, null, 2)}</pre></details>
        <details className="cc-details"><summary>Raw HTML</summary><p>Raw HTML is not retained by the crawler. This inspector shows the text and metadata actually stored in PostgreSQL.</p></details>
      </>}
    </div>
  </dialog>;
}
