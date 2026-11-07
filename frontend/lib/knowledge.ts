// Knowledge panel ("About this topic") for the results page, filled from Wikipedia.
// The route at app/api/search/knowledge asks the MediaWiki action API twice in
// parallel (an exact title lookup that follows redirects, and a full-text search)
// and these pure helpers decide whether either answer is a confident match.

export type KnowledgePanel = {
  title: string;
  /** Wikidata short description, e.g. "General-purpose programming language". */
  description: string | null;
  /** Plain-text lead, cut at a sentence boundary. */
  extract: string;
  /** The article on Wikipedia. */
  url: string;
  thumbnail: { url: string; width: number; height: number } | null;
};

export type KnowledgeResponse = {
  query: string;
  panel: KnowledgePanel | null;
};

/** Longest query that can get a panel. Topics are short; sentences are not. */
export const maxKnowledgeQueryLength = 60;
/** Most words a query can have and still name one topic. */
export const maxKnowledgeQueryWords = 5;
/** Longest extract shown in the panel. */
export const maxExtractLength = 420;

/**
 * Normalizes a query for a Wikipedia lookup, or returns null when it should not
 * get a panel: pasted code, long or many-word queries, and queries without letters.
 */
export function knowledgeQuery(raw: string): string | null {
  if (raw.includes("\n")) return null;
  const value = raw.trim().replace(/\s+/g, " ");
  if (value.length < 2 || value.length > maxKnowledgeQueryLength) return null;
  if (value.split(" ").length > maxKnowledgeQueryWords) return null;
  if (!/\p{L}/u.test(value)) return null;
  // Operators and code punctuation mean a code search, not a topic.
  if (/[{}()[\];=<>|\\`"$]/.test(value)) return null;
  return value;
}

/** Lowercase, accent-free words for comparing a title with a query ("C++" and "C#" survive). */
export function normalizeTitle(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}+#]+/gu, " ")
    .trim();
}

/** "Rust (programming language)" -> "Rust". */
export function baseTitle(title: string): string {
  return title.replace(/\s*\([^)]*\)\s*$/, "");
}

// Words that mark an article as being about software or computing, so "rust"
// finds the language and not iron oxide on a developer search engine.
const devHint =
  /\b(programming|software|framework|library|database|computing|computer|algorithm|data structure|protocol|operating system|language|markup|query|compiler|interpreter|runtime|web|javascript|python|api|cloud|container|version control|open[- ]source|file format|toolkit|engine|server|cryptograph|machine learning|data serialization)/i;

type WikiPage = {
  title: string;
  index?: number;
  missing?: boolean;
  invalid?: boolean;
  ns?: number;
  extract?: unknown;
  description?: unknown;
  fullurl?: unknown;
  thumbnail?: unknown;
  pageprops?: { disambiguation?: unknown };
};

/** Pages from a `formatversion=2` action API response, or [] for anything else. */
function pagesOf(data: unknown): WikiPage[] {
  if (!data || typeof data !== "object") return [];
  const query = (data as { query?: unknown }).query;
  if (!query || typeof query !== "object") return [];
  const pages = (query as { pages?: unknown }).pages;
  if (!Array.isArray(pages)) return [];
  return pages.filter(
    (p): p is WikiPage =>
      !!p && typeof p === "object" && typeof (p as WikiPage).title === "string",
  );
}

/** A real article with a usable lead: not missing, not a disambiguation or list page. */
function isArticle(page: WikiPage) {
  if (page.missing || page.invalid || (page.ns ?? 0) !== 0) return false;
  if (page.pageprops && "disambiguation" in page.pageprops) return false;
  if (/^(list|index|outline) of /i.test(page.title)) return false;
  const extract = typeof page.extract === "string" ? page.extract.trim() : "";
  return extract.length >= 40 && !/\bmay (also )?refer to:?\s*$/i.test(extract);
}

function isDev(page: WikiPage) {
  const parenthetical = page.title.match(/\(([^)]*)\)\s*$/)?.[1] ?? "";
  const description = typeof page.description === "string" ? page.description : "";
  return devHint.test(parenthetical) || devHint.test(description);
}

/** Cuts the lead to whole sentences within `max` characters. */
export function trimExtract(text: string, max = maxExtractLength): string {
  const value = text.replace(/\s+/g, " ").trim();
  if (value.length <= max) return value;
  const cut = value.slice(0, max);
  const end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "), cut.lastIndexOf("! "));
  if (end > max / 3) return cut.slice(0, end + 1);
  return `${cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:]$/, "")}…`;
}

function safeUrl(value: unknown, hosts: RegExp): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && hosts.test(url.hostname)
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

function toPanel(page: WikiPage): KnowledgePanel | null {
  const url = safeUrl(page.fullurl, /^([a-z-]+\.)?(m\.)?wikipedia\.org$/);
  if (!url) return null;
  const description =
    typeof page.description === "string" && page.description.trim()
      ? page.description.trim()
      : null;
  let thumbnail: KnowledgePanel["thumbnail"] = null;
  if (page.thumbnail && typeof page.thumbnail === "object") {
    const t = page.thumbnail as Record<string, unknown>;
    const src = safeUrl(t.source, /^upload\.wikimedia\.org$/);
    if (
      src &&
      typeof t.width === "number" &&
      typeof t.height === "number" &&
      t.width > 0 &&
      t.height > 0
    )
      thumbnail = { url: src, width: t.width, height: t.height };
  }
  return {
    title: page.title,
    description,
    extract: trimExtract(String(page.extract)),
    url,
    thumbnail,
  };
}

/**
 * Picks the panel for `query` from the two Wikipedia answers, or null when
 * neither is a confident match. Confident means:
 *  - the exact title (or a redirect to it, e.g. "postgres" -> "PostgreSQL") is a
 *    real article, or
 *  - a search hit whose title without its parenthetical equals the query and that
 *    is about computing ("go" -> "Go (programming language)").
 * A computing search hit wins over an exact article that is not about computing
 * ("rust" shows the language, not iron oxide). Fuzzy search hits never qualify.
 */
export function pickPanel(direct: unknown, search: unknown, query: string): KnowledgePanel | null {
  const wanted = normalizeTitle(query);
  if (!wanted) return null;
  const exact = pagesOf(direct).find(isArticle) ?? null;
  const devMatch =
    pagesOf(search)
      .filter((p) => isArticle(p) && normalizeTitle(baseTitle(p.title)) === wanted && isDev(p))
      .sort((a, b) => (a.index ?? Infinity) - (b.index ?? Infinity))[0] ?? null;
  const page = exact && (isDev(exact) || !devMatch) ? exact : devMatch;
  return page ? toPanel(page) : null;
}

/** Validates this app's `/api/search/knowledge` body in the browser. */
export function isKnowledgeResponse(value: unknown): value is KnowledgeResponse {
  if (!value || typeof value !== "object") return false;
  const body = value as Record<string, unknown>;
  if (typeof body.query !== "string") return false;
  if (body.panel === null) return true;
  const p = body.panel as Record<string, unknown> | undefined;
  return (
    !!p &&
    typeof p.title === "string" &&
    typeof p.extract === "string" &&
    (p.description === null || typeof p.description === "string") &&
    safeUrl(p.url, /^([a-z-]+\.)?(m\.)?wikipedia\.org$/) !== null &&
    (p.thumbnail === null ||
      (!!p.thumbnail &&
        typeof p.thumbnail === "object" &&
        safeUrl((p.thumbnail as Record<string, unknown>).url, /^upload\.wikimedia\.org$/) !== null))
  );
}
