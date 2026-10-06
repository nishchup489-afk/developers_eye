import { searchDemo } from "@/lib/demo";
import { isSearchResult, sources } from "@/lib/search";

export async function GET(request: Request) {
  const started = performance.now();
  const params = new URL(request.url).searchParams;
  const query = params.get("q")?.trim() ?? "";
  const source = params.get("source") ?? "";
  const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  if (!query || query.length > 300) return json({ error: "Enter a query between 1 and 300 characters." }, 400);
  if (source && !sources.includes(source as typeof sources[number])) return json({ error: "Unknown source filter." }, 400);

  const base = process.env.BACKEND_URL;
  if (!base) return json({ query, results: searchDemo(query, source), took_ms: Math.round(performance.now() - started), mode: "demo" });

  try {
    const url = new URL(`${base.replace(/\/$/, "")}/search`);
    url.searchParams.set("q", query);
    if (source) url.searchParams.set("source", source);
    const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(10000), headers: { Accept: "application/json" } });
    if (!response.ok) return json({ error: "The search service is unavailable. Please try again." }, 502);
    const data = await response.json();
    if (!data || !Array.isArray(data.results) || !data.results.every(isSearchResult)) {
      return json({ error: "The search service returned an invalid response." }, 502);
    }
    return json({ query, results: data.results, took_ms: Math.round(performance.now() - started), mode: "live" });
  } catch (error) {
    const timeout = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return json({ error: timeout ? "Search timed out. Please try again." : "Cannot reach the search service. Please try again." }, timeout ? 504 : 502);
  }
}
