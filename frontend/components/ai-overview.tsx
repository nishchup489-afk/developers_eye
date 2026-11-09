"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, ChevronDown, LoaderCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/axios";
import { type AIOverview } from "@/lib/ai-overview";

type State = { kind: "loading" } | { kind: "empty" } |
  { kind: "ready"; overview: AIOverview } | { kind: "error"; message: string; retryAfter: number; retryable: boolean };

/** Mounted only for a live search with server-issued evidence; never blocks results. */
export default function AIOverviewCard({ token }: { token: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [canRetry, setCanRetry] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void api.post("/search/overview", { token }, { signal: controller.signal, timeout: 20_000 })
      .then((response) => {
        if (controller.signal.aborted) return;
        if (response.status === 200) {
          setState(response.data.overview ? { kind: "ready", overview: response.data.overview } : { kind: "empty" });
        } else {
          setState({ kind: "error", message: response.data?.error || "AI overview is unavailable right now.",
            retryAfter: Math.max(1, Number(response.headers["retry-after"]) || 5),
            retryable: response.status === 429 || response.status >= 500 });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error", message: "AI overview is unavailable right now. Explore the sources below.", retryAfter: 5, retryable: true });
      });
    return () => controller.abort();
  }, [token, attempt]);

  useEffect(() => {
    if (state.kind !== "error" || !state.retryable) return;
    const timer = window.setTimeout(() => setCanRetry(true), Math.min(state.retryAfter * 1000, 2_147_483_647));
    return () => window.clearTimeout(timer);
  }, [state]);

  if (state.kind === "empty") return null;
  const paragraphs = state.kind === "ready" ? state.overview.paragraphs : [];
  return (
    <section className="ai-overview" aria-labelledby="ai-overview-title" aria-busy={state.kind === "loading"}>
      <div className="ai-overview-heading">
        <h2 id="ai-overview-title"><Sparkles size={17} aria-hidden="true" /> AI overview</h2>
        <span className="ai-overview-label">From your results</span>
      </div>
      {state.kind === "loading" ? (
        <div className="ai-overview-loading" role="status">
          <p><LoaderCircle size={14} className="spinner" aria-hidden="true" /> Connecting the dots across your sources…</p>
          <div className="ai-overview-skeleton" aria-hidden="true"><span className="skeleton line" /><span className="skeleton line" /><span className="skeleton line half" /></div>
        </div>
      ) : state.kind === "error" ? (
        <div className="ai-overview-unavailable" role="status">
          <p>{state.message}</p>
          {state.retryable && <button type="button" disabled={!canRetry} onClick={() => {
            setCanRetry(false); setState({ kind: "loading" }); setAttempt((value) => value + 1);
          }}>{canRetry ? "Try again" : "Try again later"}</button>}
        </div>
      ) : (
        <>
          <div className="ai-overview-answer" id="ai-overview-answer" aria-live="polite">
            {(expanded ? paragraphs : paragraphs.slice(0, 2)).map((paragraph, index) => (
              <p key={index}>{paragraph.text}{" "}
                <span className="ai-overview-citations">
                  {paragraph.sources.map((id) => {
                    const source = state.overview.sources.find((item) => item.id === id);
                    return source ? <a key={id} href={source.url} target="_blank" rel="noopener noreferrer"
                      aria-label={`Source ${id}: ${source.title}`} title={source.title}>{id}</a> : null;
                  })}
                </span>
              </p>
            ))}
          </div>
          {paragraphs.length > 2 && <button className="ai-overview-expand" type="button"
            aria-expanded={expanded} aria-controls="ai-overview-answer" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "Show less" : "Show more"}<ChevronDown size={14} style={{ transform: expanded ? "rotate(180deg)" : undefined }} />
          </button>}
          <div className="ai-overview-sources" aria-label="Overview sources">
            {state.overview.sources.map((source) => <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer">
              <span className="ai-overview-source-host">{source.id} · {new URL(source.url).hostname.replace(/^www\./, "")}<ArrowUpRight size={12} aria-hidden="true" /></span>
              <span className="ai-overview-source-title">{source.title}</span>
            </a>)}
          </div>
          <p className="ai-overview-footnote">AI can make mistakes. Check the linked sources.</p>
        </>
      )}
    </section>
  );
}
