"use client";
import { useState } from "react";
import { ArrowUpRight, Bookmark, Link2, MoreHorizontal } from "lucide-react";
import { breadcrumbParts, snippetParts, sourceNames, type Source, type SearchResult, type SearchSuggestion } from "@/lib/search";
import type { KnowledgeResponse } from "@/lib/knowledge";
import { icons } from "./source-icons";

/** A readable site name from the hostname, e.g. "docs.python.org" → "Python". */
function siteName(url: URL, source: Source) {
  const parts = url.hostname.replace(/^www\./, "").split(".");
  const name = parts.length > 1 ? parts[parts.length - 2] : parts[0];
  if (!name) return sourceNames[source];
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Bolds the words of the query wherever they appear in the snippet. */
function Snippet({ text, query, code }: { text: string; query: string; code?: boolean }) {
  const content = snippetParts(text, query).map((part, index) => part.matched ? <b key={index}>{part.text}</b> : part.text);
  return code ? <pre className="result-code-snippet"><code>{content}</code></pre> : <p>{content}</p>;
}

/** Google-style "about this topic" card from Wikipedia, beside the results. */
export function KnowledgePanel({ panel }: { panel: NonNullable<KnowledgeResponse["panel"]> }) {
  return (
    <aside className="knowledge-panel" aria-labelledby="knowledge-panel-title">
      {panel.thumbnail && (
        <a
          className="knowledge-image"
          href={panel.url}
          target="_blank"
          rel="noopener noreferrer"
          tabIndex={-1}
        >
          {/* Wikimedia thumbnails are already sized; next/image would proxy them for nothing. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={panel.thumbnail.url}
            width={panel.thumbnail.width}
            height={panel.thumbnail.height}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            // A thumbnail that fails to load hides its box instead of showing a broken image.
            onError={(event) => {
              const box = event.currentTarget.parentElement;
              if (box) box.hidden = true;
            }}
          />
        </a>
      )}
      <div className="knowledge-body">
        <h2 id="knowledge-panel-title">{panel.title}</h2>
        {panel.description && <p className="knowledge-description">{panel.description}</p>}
        <p className="knowledge-extract">{panel.extract}</p>
        <a
          className="knowledge-link"
          href={panel.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Read more on Wikipedia <ArrowUpRight size={14} />
        </a>
        <p className="knowledge-credit">
          Source: Wikipedia, under{" "}
          <a
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noopener noreferrer license"
          >
            CC BY-SA 4.0
          </a>
        </p>
      </div>
    </aside>
  );
}

/** The suggested query, with the corrected words emphasised. */
export function SuggestedQuery({ suggestion }: { suggestion: SearchSuggestion }) {
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
export function SearchResultRow({ result, isSaved, menuOpen, toggleSave, setMenuFor, query }: {
  result: SearchResult; isSaved: boolean; menuOpen: boolean;
  toggleSave: (result: SearchResult) => void;
  setMenuFor: (url: string | null) => void; query: string;
}) {
  const url = new URL(result.url);
  const crumbs = breadcrumbParts(url);
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
                              query={query}
                              code={result.snippet_is_code}
                            />
                            <div className="result-details">
                              {result.language && <span title="Language declared by the page or its documentation URL">{result.language.toUpperCase()}</span>}
                              {result.version && <span title="Documentation version from the source URL">Version {result.version}</span>}
                              {result.last_seen_at && <time dateTime={result.last_seen_at} title="Last successful observation by this crawler">Seen {new Date(result.last_seen_at).toISOString().slice(0, 10)}</time>}
                              {result.related_variants && <span title="Related translations, versions, or exact-content copies among matching documents">{result.related_variants} related {result.related_variants === 1 ? "variant" : "variants"}</span>}
                            </div>
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
}
