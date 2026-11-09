/**
 * Longest query the backend searches: SearchConfig.max_query_length (SEARCH_MAX_QUERY_LENGTH),
 * measured after normalizing. The UI, every /api/search route and FastAPI agree on it.
 */
export const maxQueryLength = 256;
/** FastAPI refuses a longer `q` before normalizing it: SearchConfig.max_raw_query_length. */
export const maxRawQueryLength = 1024;
export const queryLengthError = `Enter a query between 1 and ${maxQueryLength} characters.`;

/**
 * A query's length as FastAPI's analyzer counts it (`_normalize_whitespace` in analyzer.py):
 * NFC code points, with whitespace runs collapsed outside double quotes.
 */
export function normalizedQueryLength(query: string): number {
  let length = 0;
  let inQuotes = false;
  let pendingSpace = false;
  for (const char of query.normalize("NFC")) {
    if (char !== '"' && /\s/.test(char)) {
      if (inQuotes) length += 1;
      else pendingSpace = true;
      continue;
    }
    if (pendingSpace && length > 0) length += 1;
    pendingSpace = false;
    length += 1;
    if (char === '"') inQuotes = !inQuotes;
  }
  return length;
}

/** Whether FastAPI's length limits accept this (already trimmed) query. */
export function isSearchableLength(query: string): boolean {
  if (!query || query.length > maxRawQueryLength) return false;
  const length = normalizedQueryLength(query);
  return length > 0 && length <= maxQueryLength;
}

/** The error this app returns for a failed FastAPI search or suggestion request. */
export type UpstreamFailure = { status: number; error: string; retryAfter?: string };

/**
 * Map a FastAPI failure status to this app's response. Overload and timeouts keep their
 * meaning (and Retry-After) so the browser can tell "slow down" from "broken".
 */
export function upstreamFailure(
  status: number,
  retryAfter?: unknown,
  what: "Search" | "Suggestions" = "Search",
): UpstreamFailure {
  const wait =
    typeof retryAfter === "string" && /^[0-9]{1,4}$/.test(retryAfter) ? retryAfter : undefined;
  if (status === 429)
    return { status, error: "Too many searches. Wait a moment and try again.", retryAfter: wait ?? "1" };
  if (status === 503)
    return { status, error: `${what} is busy right now. Please try again shortly.`, retryAfter: wait };
  if (status === 504) return { status, error: `${what} timed out. Please try again.` };
  if (status === 422) return { status: 400, error: "The search service cannot search this query." };
  return { status: 502, error: "The search service is unavailable. Please try again." };
}

/**
 * The browser's address to forward to FastAPI for per-client rate limiting: the last
 * X-Forwarded-For entry, which the nearest proxy (Caddy in production) wrote.
 */
export function forwardedFor(request: Request): Record<string, string> {
  const last = request.headers.get("x-forwarded-for")?.split(",").at(-1)?.trim() ?? "";
  return /^[0-9A-Fa-f:.]{2,45}$/.test(last) ? { "X-Forwarded-For": last } : {};
}

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
export const maxSuggestQueryLength = maxQueryLength;

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
