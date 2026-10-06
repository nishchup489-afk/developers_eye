"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, ArrowUpRight, Bookmark, BookOpen, Code2, Command, Eye, GitBranch, GitFork, Globe2, Layers3, LoaderCircle, MessageCircle, Search, X } from "lucide-react";
import { isSearchResult, sourceNames, sources, type SearchResponse, type SearchResult, type Source } from "@/lib/search";

const suggestions = ["fastapi async", "react server components", "redis caching", "binary search"];
const icons = { docs: BookOpen, github: GitFork, stackoverflow: Layers3, reddit: MessageCircle, articles: Code2, events: Globe2, practice: Command };
const cards = [
  { source: "docs", title: "The source of truth.", body: "Straight from the documentation. Clear, authoritative, and to the point.", label: "Official documentation" },
  { source: "github", title: "See how it’s built.", body: "Real repositories. Real issues. The code behind your next breakthrough.", label: "GitHub" },
  { source: "stackoverflow", title: "Someone’s been there.", body: "The edge case. The elusive bug. Answers from developers in the trenches.", label: "Stack Overflow" },
  { source: "reddit", title: "Beyond the docs.", body: "Honest discussions, fresh perspectives, and lessons from the community.", label: "Reddit & community" },
] as const;

export default function SearchExperience({ mode }: { mode: "demo" | "live" }) {
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const resultsRegion = useRef<HTMLElement>(null);
  const controller = useRef<AbortController | null>(null);
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [filter, setFilter] = useState<Source | "all">("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<SearchResult[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [storageError, setStorageError] = useState("");

  const search = useCallback(async (text: string, updateUrl = true, source: Source | "all" = "all") => {
    const value = text.trim();
    if (!value) { input.current?.focus(); return; }
    controller.current?.abort();
    const active = new AbortController(); controller.current = active;
    setQuery(value); setLoading(true); setError(""); setShowSaved(false); setFilter(source); setResponse(null);
    if (updateUrl) window.history.pushState({}, "", `/?q=${encodeURIComponent(value)}#results`);
    requestAnimationFrame(() => resultsRegion.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" }));
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(value)}`, { signal: active.signal });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Search is unavailable. Please try again.");
      if (!active.signal.aborted) setResponse(data);
    } catch (err) {
      if (!active.signal.aborted) setError(err instanceof Error ? err.message : "Search failed. Please try again.");
    } finally { if (!active.signal.aborted) setLoading(false); }
  }, []);

  useEffect(() => {
    const initialize = window.setTimeout(() => {
      try { const stored: unknown = JSON.parse(localStorage.getItem("developers-eye-saved") || "[]"); if (Array.isArray(stored)) setSaved(stored.filter(isSearchResult)); } catch { /* Session bookmarks still work. */ }
      const q = new URLSearchParams(window.location.search).get("q"); if (q) void search(q, false);
    }, 0);
    const onPop = () => {
      const q = new URLSearchParams(window.location.search).get("q");
      if (q) void search(q, false);
      else { controller.current?.abort(); setQuery(""); setResponse(null); setError(""); setLoading(false); setShowSaved(false); }
    };
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !["INPUT", "TEXTAREA"].includes(target.tagName) && !target.isContentEditable)) { event.preventDefault(); input.current?.focus(); }
    };
    window.addEventListener("keydown", onKey); window.addEventListener("popstate", onPop);
    return () => { clearTimeout(initialize); controller.current?.abort(); window.removeEventListener("keydown", onKey); window.removeEventListener("popstate", onPop); };
  }, [search]);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const context = gsap.context(() => {
        gsap.from(".reveal", { y: 30, opacity: 0, stagger: 0.11, duration: 0.85, ease: "power3.out", clearProps: "all" });
        gsap.to(".orbit-spin", { rotation: 360, duration: 55, repeat: -1, ease: "none", transformOrigin: "50% 50%" });
        gsap.to(".eye-core", { y: -8, duration: 3, yoyo: true, repeat: -1, ease: "sine.inOut" });
        gsap.utils.toArray<HTMLElement>(".scroll-reveal").forEach(el => gsap.from(el, { y: 32, opacity: 0, duration: 0.7, scrollTrigger: { trigger: el, start: "top 94%", once: true }, clearProps: "all" }));
      }, root);
      return () => context.revert();
    });
    return () => media.revert();
  }, []);
  useEffect(() => {
    ScrollTrigger.refresh();
    if ((!response && !showSaved) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const context = gsap.context(() => gsap.from(".result-row", { y: 15, opacity: 0, stagger: 0.055, duration: 0.4, clearProps: "all" }), root);
    return () => context.revert();
  }, [response, filter, showSaved, loading, error]);

  function toggleSave(result: SearchResult) {
    const next = saved.some(item => item.url === result.url) ? saved.filter(item => item.url !== result.url) : [...saved, result];
    setSaved(next);
    try { localStorage.setItem("developers-eye-saved", JSON.stringify(next)); setStorageError(""); }
    catch { setStorageError("Saved for this session. Your browser could not store this collection permanently."); }
  }
  const resultItems = showSaved ? saved : response?.results ?? [];
  const visible = resultItems.filter(item => filter === "all" || item.source === filter);
  const hasResults = loading || error || response || showSaved;

  return <div ref={root}>
    <a className="skip-link" href="#search-input">Skip to search</a>
    <header className="header shell">
      <Link className="brand" href="/" onClick={() => { controller.current?.abort(); setQuery(""); setLoading(false); setError(""); setResponse(null); setShowSaved(false); }} aria-label="Developer’s Eye home"><span className="brand-mark"><Eye size={24} /></span><span>developer’s<span className="brand-light">eye</span><span className="brand-dot">.</span></span></Link>
      <nav aria-label="Main navigation"><a className="nav-link" href="#sources">The sources</a><a className="nav-link" href="#how-it-works">How it works</a><a className="nav-link" href="/docs">API docs <ArrowUpRight size={12} /></a></nav>
      <button className={`saved-button ${showSaved ? "selected" : ""}`} onClick={() => { controller.current?.abort(); setLoading(false); setError(""); setShowSaved(true); setFilter("all"); requestAnimationFrame(() => resultsRegion.current?.scrollIntoView({ behavior: "smooth" })); }}><Bookmark size={15} /><span>Saved</span><span className="saved-count">{saved.length}</span></button>
    </header>
    <main>
      <section className="hero shell" aria-labelledby="hero-title">
        <div className="hero-copy"><div className="eyebrow reveal"><span className="status-dot" /> A SEARCH ENGINE WITH A DEVELOPER’S INSTINCT</div><h1 id="hero-title" className="reveal">Less searching.<br /><span>More building.</span><span className="title-asterisk">✳</span></h1><p className="hero-description reveal">The docs, the code, the conversation.<br />One search. A clearer way forward.</p><div className="hero-note reveal"><span className="tiny-line" /> BUILT FOR CURIOSITY. DESIGNED FOR FLOW.</div></div>
        <div className="eye-art reveal" aria-hidden="true"><div className="art-grid" /><span className="art-coordinate coordinate-top">DE—01 / SIGNAL FOUND</span>
          <svg viewBox="0 0 500 400" className="eye-svg" fill="none"><defs><radialGradient id="iris"><stop stopColor="#d6fc81" /><stop offset=".5" stopColor="#91aa60" /><stop offset="1" stopColor="#344625" /></radialGradient><linearGradient id="eyeLine"><stop stopColor="#586044" stopOpacity=".1" /><stop offset=".5" stopColor="#d6fc81" /><stop offset="1" stopColor="#586044" stopOpacity=".1" /></linearGradient></defs><ellipse cx="250" cy="200" rx="213" ry="158" stroke="#414737" strokeDasharray="2 8" /><g className="orbit-spin"><circle cx="250" cy="200" r="184" stroke="#34392c" /><circle cx="250" cy="16" r="5" fill="#d6fc81" /><circle cx="250" cy="384" r="3" fill="#849664" /></g>{Array.from({ length: 12 }, (_, i) => <ellipse key={i} cx="250" cy="200" rx={206 - i * 6} ry={122 - i * 7} stroke="url(#eyeLine)" strokeWidth=".8" />)}<g className="eye-core"><circle cx="250" cy="200" r="72" fill="url(#iris)" />{Array.from({ length: 56 }, (_, i) => <line key={i} x1="250" y1="132" x2="250" y2="163" stroke="#17200e" opacity=".45" transform={`rotate(${i * (360 / 56)} 250 200)`} />)}<circle cx="250" cy="200" r="34" fill="#11150e" /><circle cx="250" cy="200" r="25" stroke="#b4d578" strokeOpacity=".3" /><circle cx="266" cy="180" r="9" fill="#e8ffc3" /><circle cx="236" cy="215" r="3" fill="#b6d680" /></g><path d="M20 200h25m410 0h25M250 0v20m0 360v20" stroke="#a1b67b" /><path d="M62 67V52h15m346 0h15v15M62 333v15h15m346 0h15v-15" stroke="#52613e" /></svg>
          <span className="art-label label-docs"><BookOpen size={12} /> docs</span><span className="art-label label-code"><Code2 size={12} /> code</span><span className="art-label label-community"><MessageCircle size={12} /> community</span><span className="art-coordinate coordinate-bottom">A LITTLE PERSPECTIVE CHANGES EVERYTHING.</span>
        </div>
      </section>
      <section className="search-section shell reveal" aria-label="Developer search"><form className="search-box" onSubmit={e => { e.preventDefault(); void search(query); }}><Search className="search-icon" size={23} /><label className="sr-only" htmlFor="search-input">Search developer knowledge</label><input ref={input} id="search-input" value={query} onChange={e => setQuery(e.target.value)} placeholder="What are you building next?" maxLength={300} required autoComplete="off" />{query && <button type="button" className="clear-search icon-button" aria-label="Clear search" onClick={() => { setQuery(""); input.current?.focus(); }}><X size={16} /></button>}<kbd className="search-shortcut">⌘ K</kbd><button className="search-submit" type="submit" aria-label="Find your answer" disabled={loading}>{loading ? <LoaderCircle className="spinner" size={19} /> : <><span>Find your answer</span><ArrowUpRight size={19} /></>}</button></form><div className="search-meta"><div className="suggestions"><span>TRY A LITTLE CURIOSITY</span>{suggestions.map(s => <button key={s} onClick={() => void search(s)}>{s}<ArrowUpRight size={11} /></button>)}</div><span className="demo-label"><span className="status-dot" />{mode === "demo" ? "Demo playground" : "Live search configured"}</span></div></section>
      {hasResults && <section ref={resultsRegion} id="results" className="results-section shell" aria-label="Search results" aria-busy={loading}>
        <div className="section-heading"><div><span className="eyebrow">{showSaved ? "YOUR PERSONAL INDEX" : mode === "demo" ? "CURATED DEMO RESULTS" : "THE SIGNAL"}</span><h2>{showSaved ? "Worth keeping." : loading ? "Connecting the dots…" : error ? "A break in the signal." : <>Results for <em>“{response?.query}”</em></>}</h2></div><button className="text-button" onClick={() => { controller.current?.abort(); setLoading(false); setShowSaved(false); setResponse(null); setError(""); window.history.pushState({}, "", "/"); }}>Close <X size={15} /></button></div>
        {storageError && <p role="status" className="result-notice">{storageError}</p>}
        {!loading && !error && <div className="filter-bar" aria-label="Filter results by source"><button className={filter === "all" ? "active" : ""} aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All sources <span>{resultItems.length}</span></button>{sources.filter(s => resultItems.some(item => item.source === s)).map(s => <button key={s} className={filter === s ? "active" : ""} aria-pressed={filter === s} onClick={() => setFilter(s)}>{sourceNames[s]}</button>)}</div>}
        <div aria-live="polite" aria-atomic="true" className="sr-only">{loading ? "Searching" : error || `${visible.length} results${showSaved ? " saved" : " found"}`}</div>
        {loading ? <div className="loading-state"><LoaderCircle className="spinner" size={22} /><p>A little less noise. A little more signal.</p></div> : error ? <div className="empty-state"><p>{error}</p><button className="text-button" onClick={() => void search(query)}>Try again <ArrowRight size={16} /></button></div> : visible.length === 0 ? <div className="empty-state"><Search size={30} /><h3>{showSaved ? "Your next great find belongs here." : "No signal on this frequency."}</h3><p>{showSaved ? "Bookmark a result to keep it in this browser." : "Try Python, React, or Redis. Demo mode searches a small curated collection."}</p></div> : <div className="result-list">{visible.map((result, index) => { const Icon = icons[result.source]; const isSaved = saved.some(item => item.url === result.url); return <article className="result-row" key={result.url}><span className="result-number">{String(index + 1).padStart(2, "0")}</span><div className="result-content"><div className="result-source"><Icon size={13} /><span>{sourceNames[result.source]}</span><span className="result-domain">{new URL(result.url).hostname}</span></div><a className="result-title" href={result.url} target="_blank" rel="noopener noreferrer">{result.title}<ArrowUpRight size={18} /></a><p>{result.snippet}</p><div className="tags">{result.tags?.map(tag => <span key={tag}>{tag}</span>)}</div></div><button className={`bookmark-button icon-button ${isSaved ? "is-saved" : ""}`} aria-label={`${isSaved ? "Unsave" : "Save"} ${result.title}`} aria-pressed={isSaved} onClick={() => toggleSave(result)}><Bookmark size={18} fill={isSaved ? "currentColor" : "none"} /></button></article>; })}</div>}
        {response && !showSaved && <p className="result-notice">{response.mode === "demo" ? "You’re exploring curated sample data. Open a source to explore its current content." : `Search completed in ${response.took_ms} ms.`}</p>}
      </section>}
      <section id="sources" className="sources-section shell scroll-reveal"><div className="section-heading"><div><span className="eyebrow">GOOD ANSWERS START WITH GOOD SOURCES</span><h2>Your entire ecosystem.<br /><span className="muted">Finally, in one place.</span></h2></div><p>From the official word to the hard-won fix.<br />Every perspective has its place.</p></div><div className="source-grid">{cards.map((card, index) => { const Icon = icons[card.source]; return <button className={`source-card source-${card.source}`} key={card.source} onClick={() => void search(card.source === "github" ? "react" : "python", true, card.source)}><div className="source-card-top"><span className="source-symbol"><Icon size={19} /></span><span className="source-index">0{index + 1}<ArrowUpRight size={17} /></span></div><span className="source-label">{card.label}</span><h3>{card.title}</h3><p>{card.body}</p><span className="source-card-bottom">Explore the {mode === "demo" ? "demo" : "index"}<ArrowRight size={15} /></span></button>; })}</div><div className="ecosystem-note"><span><GitBranch size={14} /> A growing field of view</span><span>Articles <span>/</span> Events <span>/</span> Practice <span className="small-pill">{mode === "demo" ? "IN THE DEMO" : "SOURCE CATEGORIES"}</span></span></div></section>
      <section id="how-it-works" className="how-section shell scroll-reveal"><div className="how-intro"><span className="eyebrow">A SIMPLE IDEA. A BETTER WORKFLOW.</span><h2>Stay in the flow.<br /><span className="muted">We’ll find the signal.</span></h2><p>Built around the way developers think.<br />No detours. Just a path to what matters.</p><a className="text-button" href="#search-input" onClick={() => input.current?.focus()}>Follow your curiosity <ArrowUpRight size={16} /></a></div><div className="steps"><div><span>01</span><div><h3>Start with a question.</h3><p>A framework, an error, a half-formed idea.<br />Search the way you think.</p></div><Search size={20} /></div><div><span>02</span><div><h3>Find a wider perspective.</h3><p>Explore docs, code, and discussions.<br />Filter down to the sources you need.</p></div><Eye size={21} /></div><div><span>03</span><div><h3>Get back to building.</h3><p>Open the original. Save the useful bits.<br />Make the next thing happen.</p></div><Code2 size={21} /></div></div></section>
      <section className="closing shell scroll-reveal"><span className="closing-mark">✳</span><p>The answer is out there.<br /><span>Let’s bring it into focus.</span></p><a href="#search-input" className="round-link" aria-label="Back to search" onClick={() => input.current?.focus()}><ArrowUpRight size={27} /></a></section>
    </main>
    <footer className="footer shell"><Link className="brand footer-brand" href="/" onClick={() => { controller.current?.abort(); setQuery(""); setLoading(false); setError(""); setResponse(null); setShowSaved(false); }}><Eye size={22} />developer’s eye.</Link><p>Made for the beautifully curious.</p><div><span className="footer-mode">● {mode === "demo" ? "Demo mode" : "Live search configured"}</span><a href="/docs">Under the hood <ArrowUpRight size={12} /></a></div></footer>
  </div>;
}

