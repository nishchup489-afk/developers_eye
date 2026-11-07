"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/axios";
import BrandEye from "./brand-eye";
import CodePreview from "./code-preview";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BookOpen,
  Code2,
  Command,
  Eye,
  GitBranch,
  GitFork,
  Globe2,
  Layers3,
  Link2,
  LoaderCircle,
  MessageCircle,
  MoreHorizontal,
  Search,
  X,
} from "lucide-react";
import {
  isSearchResult,
  shouldSuggest,
  sourceNames,
  type SearchResponse,
  type SearchResult,
  type SearchSuggestion,
  type Source,
} from "@/lib/search";

const suggestions = [
  "fastapi async",
  "react server components",
  "redis caching",
  "binary search",
];
const icons = {
  docs: BookOpen,
  github: GitFork,
  stackoverflow: Layers3,
  reddit: MessageCircle,
  articles: Code2,
  events: Globe2,
  practice: Command,
};
export type SearchFilter = Source | "discussions" | "all";
const verticals = [
  "docs",
  "github",
  "discussions",
  "articles",
  "events",
  "practice",
] as const;
function matchesSource(source: Source, filter: SearchFilter) {
  return (
    filter === "all" ||
    (filter === "discussions"
      ? source === "stackoverflow" || source === "reddit"
      : source === filter)
  );
}
const cards = [
  {
    source: "docs",
    title: "The source of truth.",
    body: "Straight from the documentation. Clear, authoritative, and to the point.",
    label: "Docs",
  },
  {
    source: "github",
    title: "See how it’s built.",
    body: "Real repositories. Real issues. The code behind your next breakthrough.",
    label: "GitHub",
  },
  {
    source: "discussions",
    title: "Someone’s been there.",
    body: "Stack Overflow answers and Reddit conversations. Learn from developers who’ve been there.",
    label: "Discussions",
  },
  {
    source: "articles",
    title: "Go a little deeper.",
    body: "Tutorials, engineering blogs, and practical lessons from the people building the web.",
    label: "Articles",
  },
] as const;
const steps = [
  {
    title: "Ask",
    body: "One question, in plain words. Press / from anywhere to start.",
  },
  {
    title: "Gather",
    body: "Docs, repositories, discussions and articles are searched together.",
  },
  {
    title: "Signal",
    body: "Ranked results, filtered by source, with the useful answer first.",
  },
];
const tickerItems = [
  "Documentation",
  "GitHub",
  "Stack Overflow",
  "Reddit",
  "Articles",
  "Events",
  "Practice",
];

// The search API accepts at most this many characters per query.
const maxQueryLength = 300;

/** Multi-line queries are pasted code, shown as a code block instead of in the input. */
function splitQuery(value: string): [text: string, code: string] {
  return value.includes("\n") ? ["", value] : [value, ""];
}

/** A readable site name from the hostname, e.g. "docs.python.org" → "Python". */
function siteName(url: URL, source: Source) {
  const parts = url.hostname.replace(/^www\./, "").split(".");
  const name = parts.length > 1 ? parts[parts.length - 2] : parts[0];
  if (!name) return sourceNames[source];
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Bolds the words of the query wherever they appear in the snippet. */
function Snippet({ text, query }: { text: string; query: string }) {
  const terms = query
    .toLowerCase()
    .split(/\W+/)
    .filter((term) => term.length > 1);
  if (!terms.length) return <p>{text}</p>;
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const parts = text.split(new RegExp(`\\b(${escaped.join("|")})`, "gi"));
  return (
    <p>
      {parts.map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))}
    </p>
  );
}

/** The suggested query, with the corrected words emphasised. */
function SuggestedQuery({ suggestion }: { suggestion: SearchSuggestion }) {
  const corrected = new Set(
    suggestion.corrections.map((c) => c.replacement.toLowerCase()),
  );
  const parts = (suggestion.suggestion ?? "").split(/(\s+)/);
  return parts.map((part, i) =>
    corrected.has(part.toLowerCase()) ? <b key={i}>{part}</b> : part,
  );
}

/** The site's own favicon, falling back to the source icon if it fails to load. */
function Favicon({ url, source }: { url: URL; source: Source }) {
  const [failed, setFailed] = useState(false);
  const Icon = icons[source];
  return (
    <span className="result-favicon" aria-hidden="true">
      {failed ? (
        <Icon size={14} />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`${url.origin}/favicon.ico`}
          alt=""
          width={18}
          height={18}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}

/** Splits text into per-character spans for the headline reveal. */
function Chars({ text }: { text: string }) {
  return Array.from(text, (char, i) => (
    <span className="char" key={i}>
      {char}
    </span>
  ));
}

export default function SearchExperience({
  mode,
  resultsPage = false,
  initialQuery = "",
  initialFilter = "all",
  savedPage = false,
}: {
  mode: "demo" | "live";
  resultsPage?: boolean;
  initialQuery?: string;
  initialFilter?: SearchFilter;
  savedPage?: boolean;
}) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const [query, setQuery] = useState(() => splitQuery(initialQuery)[0]);
  const [code, setCode] = useState(() => splitQuery(initialQuery)[1]);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [suggestion, setSuggestion] = useState<SearchSuggestion | null>(null);
  const [filter, setFilter] = useState<SearchFilter>(initialFilter);
  const [loading, setLoading] = useState(resultsPage && !savedPage && !!initialQuery);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<SearchResult[]>([]);
  const showSaved = savedPage;
  const [storageError, setStorageError] = useState("");
  const [menuFor, setMenuFor] = useState<string | null>(null);

  useEffect(() => {
    if (!menuFor) return;
    const close = (event: Event) => {
      if (
        event instanceof KeyboardEvent
          ? event.key === "Escape"
          : !(event.target as HTMLElement).closest("[data-result-menu]")
      )
        setMenuFor(null);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuFor]);

  const search = useCallback(
    async (text: string, updateUrl = true, source: SearchFilter = "all") => {
      const value = text.trim();
      if (!value) {
        input.current?.focus();
        return;
      }
      if (updateUrl) {
        const params = new URLSearchParams({ q: value });
        if (source !== "all") params.set("source", source);
        const destination = `/search?${params}`;
        // Re-submitting the current query should refresh its results too.
        if (!resultsPage || window.location.search !== `?${params}`) {
          router.push(destination);
          return;
        }
      }
      controller.current?.abort();
      const active = new AbortController();
      controller.current = active;
      const [typed, snippet] = splitQuery(value);
      setQuery(typed);
      setCode(snippet);
      setLoading(true);
      setError("");
      setFilter(source);
      setResponse(null);
      setSuggestion(null);
      try {
        const res = await api.get("/search", {
          params: { q: value, ...(source !== "all" ? { source } : {}) },
          signal: active.signal,
        });
        const data = res.data;
        if (res.status < 200 || res.status >= 300)
          throw new Error(
            data?.error || "Search is unavailable. Please try again.",
          );
        if (active.signal.aborted) return;
        setResponse(data);
        // Few or no results: ask for a spelling suggestion in the background.
        // It is only offered; the search the user typed is never rewritten.
        if (shouldSuggest(value, data.results.length))
          void api.get("/search/suggest", { params: { q: value }, signal: active.signal })
            .then((res) => {
              if (
                !active.signal.aborted &&
                res.status === 200 &&
                typeof res.data?.suggestion === "string"
              )
                setSuggestion(res.data);
            })
            .catch(() => {
              /* Suggestions are optional. */
            });
      } catch (err) {
        if (!active.signal.aborted)
          setError(
            err instanceof Error
              ? err.message
              : "Search failed. Please try again.",
          );
      } finally {
        if (!active.signal.aborted) setLoading(false);
      }
    },
    [router, resultsPage],
  );

  useEffect(() => {
    const initialize = window.setTimeout(() => {
      try {
        const stored: unknown = JSON.parse(
          localStorage.getItem("developers-eye-saved") || "[]",
        );
        if (Array.isArray(stored)) setSaved(stored.filter(isSearchResult));
      } catch {
        /* Session bookmarks still work. */
      }
      if (resultsPage && initialQuery && !savedPage)
        void search(initialQuery, false, initialFilter);
    }, 0);
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        (event.key === "k" && (event.metaKey || event.ctrlKey)) ||
        (event.key === "/" &&
          !["INPUT", "TEXTAREA"].includes(target.tagName) &&
          !target.isContentEditable)
      ) {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(initialize);
      controller.current?.abort();
      window.removeEventListener("keydown", onKey);
    };
  }, [search, resultsPage, initialQuery, initialFilter, savedPage]);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const context = gsap.context(() => {
        gsap.from(".reveal", {
          y: 30,
          opacity: 0,
          stagger: 0.11,
          duration: 0.85,
          ease: "power3.out",
          clearProps: "all",
        });
        if (!resultsPage) {
          gsap.from(".hero-title .char", {
            yPercent: 80,
            opacity: 0,
            filter: "blur(8px)",
            stagger: 0.035,
            duration: 0.9,
            delay: 0.25,
            ease: "power4.out",
            clearProps: "all",
          });
          gsap.from(".steps-line", {
            scaleX: 0,
            transformOrigin: "left center",
            duration: 1.4,
            ease: "power3.inOut",
            scrollTrigger: { trigger: ".steps", start: "top 85%", once: true },
          });
          gsap.from(".step", {
            y: 24,
            opacity: 0,
            stagger: 0.15,
            duration: 0.8,
            ease: "power3.out",
            scrollTrigger: { trigger: ".steps", start: "top 85%", once: true },
            clearProps: "all",
          });
        }
        gsap.utils.toArray<HTMLElement>(".scroll-reveal").forEach((el) =>
          gsap.from(el, {
            y: 32,
            opacity: 0,
            duration: 0.7,
            scrollTrigger: { trigger: el, start: "top 94%", once: true },
            clearProps: "all",
          }),
        );
      }, root);
      return () => context.revert();
    });
    return () => media.revert();
  }, [resultsPage]);
  useEffect(() => {
    ScrollTrigger.refresh();
    if (!root.current?.querySelector(".result-row")) return;
    if (
      (!response && !showSaved) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const context = gsap.context(
      () =>
        gsap.from(".result-row", {
          y: 15,
          opacity: 0,
          stagger: 0.055,
          duration: 0.4,
          clearProps: "all",
        }),
      root,
    );
    return () => context.revert();
  }, [response, filter, showSaved, loading, error]);

  function toggleSave(result: SearchResult) {
    const next = saved.some((item) => item.url === result.url)
      ? saved.filter((item) => item.url !== result.url)
      : [...saved, result];
    setSaved(next);
    try {
      localStorage.setItem("developers-eye-saved", JSON.stringify(next));
      setStorageError("");
    } catch {
      setStorageError(
        "Saved for this session. Your browser could not store this collection permanently.",
      );
    }
  }
  const fullQuery = [query.trim(), code].filter(Boolean).join("\n");
  const resultItems = showSaved ? saved : (response?.results ?? []);
  // Saved results live in the browser. Live results are filtered by the server,
  // so a filter finds every match in the index, not just the current page.
  const applyFilter = (next: SearchFilter) => {
    if (showSaved || !response) setFilter(next);
    else void search(response.query, true, next);
  };
  const visible = resultItems.filter((item) =>
    matchesSource(item.source, filter),
  );

  return (
    <div ref={root} className={`search-home${resultsPage ? " search-results-page" : ""}`}>
      <a className="skip-link" href="#search-input">
        Skip to search
      </a>
      <header className="header shell">
        <Link
          className="brand"
          href="/"
          onClick={() => {
            controller.current?.abort();
            setQuery("");
            setCode("");
            setLoading(false);
            setError("");
            setResponse(null);
          }}
          aria-label="Developer’s Eye home"
        >
          <span className="brand-mark">
            <Eye size={24} />
          </span>
          <span>
            developer’s<span className="brand-light">eye</span>
            <span className="brand-dot">.</span>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          <a className="nav-link" href={resultsPage ? "/#sources" : "#sources"}>
            The sources
          </a>
          <a
            className="nav-link"
            href="#search-input"
            onClick={() => input.current?.focus()}
          >
            Search
          </a>
          <a className="nav-link" href="/docs">
            API docs <ArrowUpRight size={12} />
          </a>
        </nav>
        <Link
          href="/search?saved=1"
          aria-label={`Saved results (${saved.length})`}
          className={`saved-button ${showSaved ? "selected" : ""}`}
          data-magnetic
        >
          <Bookmark size={15} />
          <span>Saved</span>
          <span className="saved-count">{saved.length}</span>
        </Link>
      </header>
      <main>
        <section className="hero shell" aria-label={resultsPage ? "Search" : undefined} aria-labelledby={resultsPage ? undefined : "hero-title"}>
          {!resultsPage && <BrandEye />}
          {!resultsPage && <div className="hero-copy">
            <h1 id="hero-title" className="hero-title" aria-label="developer’s eye.">
              <span className="word" aria-hidden="true">
                <Chars text="developer’s" />
              </span>{" "}
              <span className="word accent" aria-hidden="true">
                <Chars text="eye." />
              </span>
            </h1>
            <p className="hero-description reveal">
              Less searching. More building.
            </p>
          </div>}
          <section
            className="search-section reveal"
            aria-label="Developer search"
          >
            <form
              className={`search-box${code ? " has-code" : ""}`}
              onSubmit={(e) => {
                e.preventDefault();
                void search(fullQuery.slice(0, maxQueryLength));
              }}
            >
              {code && (
                <CodePreview
                  code={code}
                  note={
                    fullQuery.length > maxQueryLength
                      ? `Only the first ${maxQueryLength} characters are searched.`
                      : undefined
                  }
                  onRemove={() => {
                    setCode("");
                    input.current?.focus();
                  }}
                />
              )}
              <Search className="search-icon" size={23} />
              <label className="sr-only" htmlFor="search-input">
                Search developer knowledge
              </label>
              <input
                ref={input}
                id="search-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onPaste={(e) => {
                  const pasted = e.clipboardData
                    .getData("text")
                    .replace(/\r\n?/g, "\n")
                    .replace(/^\n+|\s+$/g, "");
                  // A single-line paste stays in the input as usual.
                  if (!pasted.includes("\n")) return;
                  e.preventDefault();
                  setCode(pasted);
                }}
                placeholder={
                  code ? "Ask about this code (optional)…" : "Search docs, code…"
                }
                maxLength={maxQueryLength}
                required={!code}
                autoComplete="off"
              />
              {query && (
                <button
                  type="button"
                  className="clear-search icon-button"
                  aria-label="Clear search"
                  onClick={() => {
                    setQuery("");
                    input.current?.focus();
                  }}
                >
                  <X size={16} />
                </button>
              )}
              <kbd className="search-shortcut">⌘ K</kbd>
              <button
                className="search-submit"
                data-magnetic
                type="submit"
                aria-label="Search"
                disabled={loading}
              >
                {loading ? (
                  <LoaderCircle className="spinner" size={19} />
                ) : (
                  <>
                    <span>Search</span>
                    <ArrowUpRight size={19} />
                  </>
                )}
              </button>
            </form>
            {!resultsPage && <div className="search-meta">
              <div className="suggestions">
                <span>Try</span>
                {suggestions.map((s) => (
                  <button key={s} onClick={() => void search(s)}>
                    {s}
                    <ArrowUpRight size={11} />
                  </button>
                ))}
              </div>
              <span className="demo-label">
                <span className="status-dot" />
                {mode === "demo" ? "Demo playground" : "Live search configured"}
              </span>
            </div>}
          </section>
        </section>

        {resultsPage && (
          <section
            id="results"
            className="results-section shell"
            aria-label="Search results"
            aria-busy={loading}
          >
            <div className="section-heading">
              <div>
                <span className="eyebrow">
                  {showSaved
                    ? "YOUR PERSONAL INDEX"
                    : mode === "demo"
                      ? "CURATED DEMO RESULTS"
                      : "THE SIGNAL"}
                </span>
                <h1>
                  {showSaved ? (
                    "Worth keeping."
                  ) : loading ? (
                    "Connecting the dots…"
                  ) : error ? (
                    "A break in the signal."
                  ) : !initialQuery ? (
                    "What are you building?"
                  ) : (
                    <>
                      Results for{" "}
                      {response?.query.includes("\n") ? (
                        "your code"
                      ) : (
                        <em>“{response?.query}”</em>
                      )}
                    </>
                  )}
                </h1>
              </div>
              <Link className="text-button" href="/">
                Back home <ArrowUpRight size={15} />
              </Link>
            </div>
            {storageError && (
              <p role="status" className="result-notice">
                {storageError}
              </p>
            )}
            {!loading && !error && (
              <div className="filter-bar" aria-label="Filter results by source">
                <button
                  className={filter === "all" ? "active" : ""}
                  aria-pressed={filter === "all"}
                  onClick={() => applyFilter("all")}
                >
                  All sources <span>{resultItems.length}</span>
                </button>
                {verticals
                  .filter(
                    (s) =>
                      !showSaved ||
                      resultItems.some((item) => matchesSource(item.source, s)),
                  )
                  .map((s) => (
                    <button
                      key={s}
                      className={filter === s ? "active" : ""}
                      aria-pressed={filter === s}
                      onClick={() => applyFilter(s)}
                    >
                      {s === "discussions" ? "Discussions" : sourceNames[s]}
                    </button>
                  ))}
              </div>
            )}
            <div aria-live="polite" aria-atomic="true" className="sr-only">
              {loading
                ? "Searching"
                : error ||
                  `${visible.length} results${showSaved ? " saved" : " found"}`}
            </div>
            {!loading &&
              !error &&
              !showSaved &&
              response &&
              suggestion?.suggestion &&
              suggestion.query === response.query && (
                <p className="did-you-mean" role="status">
                  Did you mean{" "}
                  <button
                    type="button"
                    className="did-you-mean-link"
                    onClick={() => void search(suggestion.suggestion!, true, filter)}
                  >
                    <SuggestedQuery suggestion={suggestion} />
                  </button>
                  ?
                </p>
              )}
            {loading ? (
              <div className="loading-state">
                <p>
                  <LoaderCircle className="spinner" size={14} />A little less
                  noise. A little more signal.
                </p>
                {[0, 1, 2].map((i) => (
                  <div className="skeleton-row" key={i} aria-hidden="true">
                    <span className="skeleton short" />
                    <span className="skeleton title" />
                    <span className="skeleton line" />
                    <span className="skeleton line half" />
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="empty-state">
                <p>{error}</p>
                <button
                  className="text-button"
                  onClick={() => void search(query, false, filter)}
                >
                  Try again <ArrowRight size={16} />
                </button>
              </div>
            ) : visible.length === 0 ? (
              <div className="empty-state">
                <Search size={30} />
                <h3>
                  {showSaved
                    ? "Your next great find belongs here."
                    : !initialQuery
                      ? "Start with a question or a topic."
                    : "No signal on this frequency."}
                </h3>
                <p>
                  {showSaved
                    ? "Bookmark a result to keep it in this browser."
                    : !initialQuery
                      ? "Search the docs, code, and conversations above."
                    : mode === "demo"
                      ? "Try Python, React, or Redis. Demo mode searches a small curated collection."
                      : "Try a broader query or choose a different source."}
                </p>
              </div>
            ) : (
              <div className="result-list">
                {visible.map((result) => {
                  const isSaved = saved.some((item) => item.url === result.url);
                  const url = new URL(result.url);
                  const crumbs = url.pathname
                    .split("/")
                    .filter(Boolean)
                    .map((part) => decodeURIComponent(part));
                  const menuOpen = menuFor === result.url;
                  return (
                    <article className="result-row" key={result.url}>
                      <div className="result-content">
                        <a
                          className="result-site"
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          tabIndex={-1}
                        >
                          <Favicon url={url} source={result.source} />
                          <span className="result-site-text">
                            <span className="result-site-name">
                              {siteName(url, result.source)}
                            </span>
                            <cite className="result-breadcrumb">
                              {url.origin}
                              {crumbs.length > 0 && ` › ${crumbs.join(" › ")}`}
                            </cite>
                          </span>
                        </a>
                        <a
                          className="result-title"
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {result.title}
                        </a>
                        <Snippet
                          text={result.snippet}
                          query={showSaved ? "" : (response?.query ?? "")}
                        />
                      </div>
                      <div className="result-menu" data-result-menu>
                        <button
                          className={`result-menu-button icon-button ${isSaved ? "is-saved" : ""}`}
                          aria-label={`More options for ${result.title}`}
                          aria-haspopup="menu"
                          aria-expanded={menuOpen}
                          onClick={() => setMenuFor(menuOpen ? null : result.url)}
                        >
                          <MoreHorizontal size={18} />
                        </button>
                        {menuOpen && (
                          <div className="result-menu-list" role="menu">
                            <button
                              role="menuitem"
                              onClick={() => {
                                toggleSave(result);
                                setMenuFor(null);
                              }}
                            >
                              <Bookmark
                                size={15}
                                fill={isSaved ? "currentColor" : "none"}
                              />
                              {isSaved ? "Unsave" : "Save"}
                            </button>
                            <button
                              role="menuitem"
                              onClick={() => {
                                void navigator.clipboard
                                  ?.writeText(result.url)
                                  .catch(() => {});
                                setMenuFor(null);
                              }}
                            >
                              <Link2 size={15} />
                              Copy link
                            </button>
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
            {response && !showSaved && (
              <p className="result-notice">
                {response.mode === "demo"
                  ? "You’re exploring curated sample data. Open a source to explore its current content."
                  : `Search completed in ${response.took_ms} ms.`}
              </p>
            )}
          </section>
        )}
        {!resultsPage && (
          <div className="ticker" aria-hidden="true">
            <div className="ticker-track">
              {[0, 1].map((copy) => (
                <div className="ticker-group" key={copy}>
                  {tickerItems.map((item) => (
                    <span key={item}>
                      {item}
                      <Eye size={14} />
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
        {!resultsPage && <section id="sources" className="sources-section shell scroll-reveal">
          <div className="section-heading">
            <div>
              <span className="eyebrow">
                GOOD ANSWERS START WITH GOOD SOURCES
              </span>
              <h2>
                Your entire ecosystem.
                <br />
                <span className="muted">Finally, in one place.</span>
              </h2>
            </div>
            <p>
              From the official word to the hard-won fix.
              <br />
              Every perspective has its place.
            </p>
          </div>
          <div className="source-grid">
            {cards.map((card, index) => {
              const Icon =
                card.source === "discussions"
                  ? MessageCircle
                  : icons[card.source];
              return (
                <button
                  className={`source-card source-${card.source}`}
                  key={card.source}
                  data-spotlight
                  onClick={() =>
                    void search(
                      fullQuery.slice(0, maxQueryLength) ||
                        (card.source === "github" ? "react" : "python"),
                      true,
                      card.source,
                    )
                  }
                >
                  <div className="source-card-top">
                    <span className="source-symbol">
                      <Icon size={19} />
                    </span>
                    <span className="source-index">
                      0{index + 1}
                      <ArrowUpRight size={17} />
                    </span>
                  </div>
                  <span className="source-label">{card.label}</span>
                  <h3>{card.title}</h3>
                  <p>{card.body}</p>
                  <span className="source-card-bottom">
                    Explore the {mode === "demo" ? "demo" : "index"}
                    <ArrowRight size={15} />
                  </span>
                </button>
              );
            })}
          </div>
          <div className="ecosystem-note">
            <span>
              <GitBranch size={14} /> A growing field of view
            </span>
            <span>
              Events <span>/</span> Practice{" "}
              <span className="small-pill">
                {mode === "demo" ? "IN THE DEMO" : "SOURCE CATEGORIES"}
              </span>
            </span>
          </div>
        </section>}
        {!resultsPage && (
          <section className="steps-section shell" aria-labelledby="steps-title">
            <span className="eyebrow">HOW IT SEES</span>
            <h2 id="steps-title">
              Three steps from question
              <br />
              <span className="muted">to the answer worth reading.</span>
            </h2>
            <div className="steps">
              <span className="steps-line" aria-hidden="true" />
              <ol>
              {steps.map((step, index) => (
                <li className="step" key={step.title} data-spotlight>
                  <span className="step-index">0{index + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </li>
              ))}
              </ol>
            </div>
            <button
              className="steps-cta"
              data-magnetic
              onClick={() => {
                input.current?.focus();
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              Start searching <ArrowUpRight size={16} />
            </button>
          </section>
        )}
      </main>
      <div className="footer-wordmark" aria-hidden="true">
        developer’s eye<span>.</span>
      </div>
      <footer className="footer shell">
        <Link
          className="brand footer-brand"
          href="/"
          onClick={() => {
            controller.current?.abort();
            setQuery("");
            setCode("");
            setLoading(false);
            setError("");
            setResponse(null);
          }}
        >
          <Eye size={22} />
          developer’s eye.
        </Link>
        <p>Made for the beautifully curious.</p>
        <div>
          <span className="footer-mode">
            ● {mode === "demo" ? "Demo mode" : "Live search configured"}
          </span>
          <a href="/docs">
            Under the hood <ArrowUpRight size={12} />
          </a>
          <Link href="/admin">
            Admin <ArrowUpRight size={12} />
          </Link>
        </div>
      </footer>
    </div>
  );
}
