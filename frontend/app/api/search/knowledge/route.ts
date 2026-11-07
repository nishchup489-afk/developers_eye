import { backend, isOk, isTimeout } from "@/lib/axios";
import { knowledgeQuery, pickPanel, type KnowledgePanel } from "@/lib/knowledge";

// Knowledge panel for the results page, from Wikipedia. Asks the MediaWiki action
// API for the exact title (following redirects) and for a full-text search at the
// same time, and returns a panel only for a confident match (see lib/knowledge.ts).
// Answers are cached in memory, so each topic costs Wikipedia two requests a day.

const defaultApi = "https://en.wikipedia.org/w/api.php";
// Wikimedia asks automated clients to identify themselves; set WIKIPEDIA_USER_AGENT
// to add a contact URL or email in production.
const defaultUserAgent = "developers-eye/0.1 (knowledge panel)";
const timeoutMs = 4000;
const hitTtlMs = 24 * 60 * 60 * 1000;
const missTtlMs = 60 * 60 * 1000;
const maxEntries = 500;

type Entry = { panel: KnowledgePanel | null; expires: number };
const cache = new Map<string, Entry>();
const pending = new Map<string, Promise<KnowledgePanel | null>>();

function remember(key: string, panel: KnowledgePanel | null) {
  cache.delete(key);
  cache.set(key, { panel, expires: Date.now() + (panel ? hitTtlMs : missTtlMs) });
  // Map keeps insertion order, so the first key is the least recently used.
  while (cache.size > maxEntries) cache.delete(cache.keys().next().value!);
}

const shared = {
  action: "query",
  format: "json",
  formatversion: "2",
  prop: "extracts|pageimages|description|pageprops|info",
  exintro: "1",
  explaintext: "1",
  exsentences: "4",
  piprop: "thumbnail",
  // 330 is one of Wikimedia's standard thumbnail widths; other widths can be throttled.
  pithumbsize: "330",
  // Logos are often non-free files on English Wikipedia; the default (free only) hides them.
  pilicense: "any",
  ppprop: "disambiguation",
  inprop: "url",
};

async function lookup(api: string, query: string): Promise<KnowledgePanel | null> {
  const userAgent = process.env.WIKIPEDIA_USER_AGENT || defaultUserAgent;
  const get = async (params: Record<string, string>) => {
    const url = new URL(api);
    for (const [k, v] of Object.entries({ ...shared, ...params })) url.searchParams.set(k, v);
    const response = await backend.get(url.toString(), {
      timeout: timeoutMs,
      headers: { "User-Agent": userAgent, "Api-User-Agent": userAgent },
    });
    if (!isOk(response.status)) throw new Error(`Wikipedia answered ${response.status}`);
    return response.data as unknown;
  };
  const [direct, search] = await Promise.all([
    get({ titles: query, redirects: "1" }),
    get({ generator: "search", gsrsearch: query, gsrlimit: "10", gsrnamespace: "0" }),
  ]);
  return pickPanel(direct, search, query);
}

export async function GET(request: Request) {
  const raw = new URL(request.url).searchParams.get("q") ?? "";
  const json = (body: unknown, status = 200, cacheable = false) =>
    Response.json(body, {
      status,
      headers: {
        "Cache-Control": cacheable ? "public, max-age=3600" : "no-store",
      },
    });
  if (!raw.trim() || raw.length > 300)
    return json({ error: "Enter a query between 1 and 300 characters." }, 400);
  const query = knowledgeQuery(raw);
  if (!query || process.env.KNOWLEDGE_PANEL === "off")
    return json({ query: raw.trim(), panel: null }, 200, true);

  const key = query.toLowerCase();
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now()) {
    remember(key, hit.panel);
    return json({ query, panel: hit.panel }, 200, true);
  }

  // Concurrent searches for the same topic share one pair of Wikipedia requests.
  let inflight = pending.get(key);
  if (!inflight) {
    inflight = lookup(process.env.WIKIPEDIA_API_URL || defaultApi, query).finally(() =>
      pending.delete(key),
    );
    pending.set(key, inflight);
  }
  try {
    const panel = await inflight;
    remember(key, panel);
    return json({ query, panel }, 200, true);
  } catch (error) {
    // Failures are not cached: the next search tries Wikipedia again.
    const timeout = isTimeout(error);
    return json(
      { error: timeout ? "Wikipedia timed out." : "Cannot reach Wikipedia." },
      timeout ? 504 : 502,
    );
  }
}
