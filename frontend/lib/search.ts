export const sources = ["docs", "github", "stackoverflow", "reddit", "articles", "events", "practice"] as const;
export type Source = (typeof sources)[number];
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
};
export const sourceNames: Record<Source, string> = {
  docs: "Documentation", github: "GitHub", stackoverflow: "Stack Overflow",
  reddit: "Reddit", articles: "Articles", events: "Events", practice: "Practice",
};

export function isSearchResult(value: unknown): value is SearchResult {
  if (!value || typeof value !== "object") return false;
  const r = value as Record<string, unknown>;
  try {
    const url = new URL(String(r.url));
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname) return false;
  } catch { return false; }
  return typeof r.title === "string" && typeof r.snippet === "string" &&
    typeof r.url === "string" && /^https?:\/\//i.test(r.url) &&
    sources.includes(r.source as Source) && typeof r.score === "number" && Number.isFinite(r.score) &&
    (r.tags === undefined || (Array.isArray(r.tags) && r.tags.every(t => typeof t === "string")));
}
