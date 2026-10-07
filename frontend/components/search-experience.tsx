"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import BrandEye from "./brand-eye";
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
  LoaderCircle,
  MessageCircle,
  Search,
  X,
} from "lucide-react";
import {
  isSearchResult,
  sourceNames,
  type SearchResponse,
  type SearchResult,
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
  const [query, setQuery] = useState(initialQuery);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [filter, setFilter] = useState<SearchFilter>(initialFilter);
  const [loading, setLoading] = useState(resultsPage && !savedPage && !!initialQuery);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<SearchResult[]>([]);
  const showSaved = savedPage;
  const [storageError, setStorageError] = useState("");

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
      setQuery(value);
      setLoading(true);
      setError("");
      setFilter(source);
      setResponse(null);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(value)}`, {
          signal: active.signal,
        });
        const data = await res.json();
        if (!res.ok)
          throw new Error(
            data.error || "Search is unavailable. Please try again.",
          );
        if (!active.signal.aborted) setResponse(data);
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
          gsap.to(".orbit-spin", {
            rotation: 360,
            duration: 55,
            repeat: -1,
            ease: "none",
            transformOrigin: "50% 50%",
          });
          gsap.to(".eye-core", {
            y: -8,
            duration: 3,
            yoyo: true,
            repeat: -1,
            ease: "sine.inOut",
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
  const resultItems = showSaved ? saved : (response?.results ?? []);
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
            <h1 id="hero-title" className="reveal">
              developer’s <span>eye.</span>
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
              className="search-box"
              onSubmit={(e) => {
                e.preventDefault();
                void search(query);
              }}
            >
              <Search className="search-icon" size={23} />
              <label className="sr-only" htmlFor="search-input">
                Search developer knowledge
              </label>
              <input
                ref={input}
                id="search-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search docs, code…"
                maxLength={300}
                required
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
                      Results for <em>“{response?.query}”</em>
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
                  onClick={() => setFilter("all")}
                >
                  All sources <span>{resultItems.length}</span>
                </button>
                {verticals
                  .filter((s) =>
                    resultItems.some((item) => matchesSource(item.source, s)),
                  )
                  .map((s) => (
                    <button
                      key={s}
                      className={filter === s ? "active" : ""}
                      aria-pressed={filter === s}
                      onClick={() => setFilter(s)}
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
            {loading ? (
              <div className="loading-state">
                <LoaderCircle className="spinner" size={22} />
                <p>A little less noise. A little more signal.</p>
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
                {visible.map((result, index) => {
                  const Icon = icons[result.source];
                  const isSaved = saved.some((item) => item.url === result.url);
                  return (
                    <article className="result-row" key={result.url}>
                      <span className="result-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div className="result-content">
                        <div className="result-source">
                          <Icon size={13} />
                          <span>{sourceNames[result.source]}</span>
                          <span className="result-domain">
                            {new URL(result.url).hostname}
                          </span>
                        </div>
                        <a
                          className="result-title"
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {result.title}
                          <ArrowUpRight size={18} />
                        </a>
                        <p>{result.snippet}</p>
                        <div className="tags">
                          {result.tags?.map((tag) => (
                            <span key={tag}>{tag}</span>
                          ))}
                        </div>
                      </div>
                      <button
                        className={`bookmark-button icon-button ${isSaved ? "is-saved" : ""}`}
                        aria-label={`${isSaved ? "Unsave" : "Save"} ${result.title}`}
                        aria-pressed={isSaved}
                        onClick={() => toggleSave(result)}
                      >
                        <Bookmark
                          size={18}
                          fill={isSaved ? "currentColor" : "none"}
                        />
                      </button>
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
                  onClick={() =>
                    void search(
                      query.trim() ||
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
      </main>
      <footer className="footer shell">
        <Link
          className="brand footer-brand"
          href="/"
          onClick={() => {
            controller.current?.abort();
            setQuery("");
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
        </div>
      </footer>
    </div>
  );
}
