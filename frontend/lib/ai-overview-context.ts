import { createHmac, timingSafeEqual } from "node:crypto";
import type { SearchResult } from "./search";
import type { OverviewSource } from "./ai-overview";

export type OverviewContext = { query: string; sources: OverviewSource[]; expires: number };
export const overviewEnabled = () => !!process.env.GROQ_API_KEY?.trim() && process.env.AI_OVERVIEW !== "off";
const signature = (payload: string) => createHmac("sha256", process.env.GROQ_API_KEY || "")
  .update(`developers-eye-overview-v1:${payload}`).digest();

/** Reuse these exact results without a second search or trusting browser-supplied snippets. */
export function signOverviewContext(query: string, results: SearchResult[]): string | undefined {
  if (!overviewEnabled()) return undefined;
  const seen = new Set<string>();
  const sources: OverviewSource[] = [];
  for (const result of results) {
    if (sources.length === 4) break;
    if (!result.snippet.trim() || Buffer.byteLength(result.url, "utf8") > 1500 || seen.has(result.url)) continue;
    seen.add(result.url);
    sources.push({ id: sources.length + 1, title: result.title.slice(0, 120),
      url: result.url, snippet: result.snippet.slice(0, 350), kind: result.source });
  }
  if (!sources.length) return undefined;
  const payload = Buffer.from(JSON.stringify({ query, sources, expires: Date.now() + 10 * 60_000 })).toString("base64url");
  return `${payload}.${signature(payload).toString("base64url")}`;
}

export function verifyOverviewContext(token: unknown): OverviewContext | null {
  if (!overviewEnabled() || typeof token !== "string" || token.length > 24000) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const supplied = Buffer.from(parts[1], "base64url");
  const expected = signature(parts[0]);
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return null;
  try {
    const context = JSON.parse(Buffer.from(parts[0], "base64url").toString()) as OverviewContext;
    return context.expires > Date.now() ? context : null;
  } catch { return null; }
}
