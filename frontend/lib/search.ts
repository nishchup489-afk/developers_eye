export const sources = [
  "docs",
  "github",
  "stackoverflow",
  "reddit",
  "articles",
  "events",
  "practice",
] as const;
export type Source = (typeof sources)[number];
export const searchModes = ["all", "text", "code"] as const;
export type SearchMode = (typeof searchModes)[number];
export function isSearchMode(value: unknown): value is SearchMode {
  return typeof value === "string" && searchModes.some((mode) => mode === value);
}
export type SearchResult = {
  title: string;
  source: Source;
  url: string;
  snippet: string;
  score: number;
  tags?: string[];
};
export type SearchResponse = {
  query: string;
  results: SearchResult[];
  took_ms: number;
  mode: "demo" | "live";
  overviewToken?: string;
};
export const sourceNames: Record<Source, string> = {
  docs: "Documentation",
  github: "GitHub",
  stackoverflow: "Stack Overflow",
  reddit: "Reddit",
  articles: "Articles",
  events: "Events",
  practice: "Practice",
};

export function isSearchResult(value: unknown): value is SearchResult {
  if (!value || typeof value !== "object") return false;
  const r = value as Record<string, unknown>;
  try {
    const url = new URL(String(r.url));
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname)
      return false;
  } catch {
    return false;
  }
  return (
    typeof r.title === "string" &&
    typeof r.snippet === "string" &&
    typeof r.url === "string" &&
    /^https?:\/\//i.test(r.url) &&
    sources.includes(r.source as Source) &&
    typeof r.score === "number" &&
    Number.isFinite(r.score) &&
    (r.tags === undefined ||
      (Array.isArray(r.tags) && r.tags.every((t) => typeof t === "string")))
  );
}

// Spelling suggestions ("Did you mean …"). The backend never rewrites a search;
// the UI offers the suggestion and the user decides whether to run it.

/** Fewer results than this make the results page ask for a spelling suggestion. */
export const suggestBelowResults = 3;
/** The backend corrects at most this many characters. */
export const maxSuggestQueryLength = 256;

export type SearchCorrection = { original: string; replacement: string };
export type SearchSuggestion = {
  query: string;
  /** The corrected query, or null when there is nothing to suggest. */
  suggestion: string | null;
  corrections: SearchCorrection[];
  mode: "demo" | "live";
};

/** Only plain, short, single-line queries with few results get a suggestion. */
export function shouldSuggest(query: string, resultCount: number) {
  const value = query.trim();
  return (
    resultCount < suggestBelowResults &&
    value.length > 0 &&
    value.length <= maxSuggestQueryLength &&
    !value.includes("\n") &&
    /[a-z]{4}/i.test(value)
  );
}

/**
 * Validates FastAPI's QueryCorrection (`GET /search/suggest`). Returns null for
 * a malformed payload; a suggestion equal to the query becomes `suggestion: null`.
 */
export function parseCorrection(
  data: unknown,
  query: string,
): Pick<SearchSuggestion, "suggestion" | "corrections"> | null {
  if (!data || typeof data !== "object") return null;
  const body = data as Record<string, unknown>;
  if (
    typeof body.suggested_query !== "string" ||
    !Array.isArray(body.corrections)
  )
    return null;
  const corrections: SearchCorrection[] = [];
  for (const item of body.corrections) {
    if (!item || typeof item !== "object") return null;
    const { original, replacement } = item as Record<string, unknown>;
    if (typeof original !== "string" || typeof replacement !== "string")
      return null;
    corrections.push({ original, replacement });
  }
  const suggestion = body.suggested_query.trim().replace(/\s+/g, " ");
  const unchanged =
    !suggestion ||
    suggestion.length > maxSuggestQueryLength ||
    suggestion.toLowerCase() === query.trim().replace(/\s+/g, " ").toLowerCase() ||
    corrections.length === 0;
  return unchanged
    ? { suggestion: null, corrections: [] }
    : { suggestion, corrections };
}
