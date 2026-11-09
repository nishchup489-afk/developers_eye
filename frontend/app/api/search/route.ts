import { backend, isOk, isTimeout } from "@/lib/axios";
import { searchDemo } from "@/lib/demo";
import { isSearchResult, sources } from "@/lib/search";
import { signOverviewContext } from "@/lib/ai-overview-context";

export async function GET(request: Request) {
  const started = performance.now();
  const params = new URL(request.url).searchParams;
  const query = params.get("q")?.trim() ?? "";
  const source = params.get("source") ?? "";
  const json = (body: unknown, status = 200) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  if (!query || query.length > 300)
    return json({ error: "Enter a query between 1 and 300 characters." }, 400);
  if (source && ![...sources, "discussions"].includes(source))
    return json({ error: "Unknown source filter." }, 400);
  const page = params.get("page") ?? "";
  const mode = params.get("mode") ?? "";
  if (page && !/^[1-9][0-9]{0,3}$/.test(page))
    return json({ error: "Unknown page." }, 400);
  if (mode && !["all", "text", "code"].includes(mode))
    return json({ error: "Unknown search mode." }, 400);

  const base = process.env.BACKEND_URL;
  if (!base)
    return json({
      query,
      results: searchDemo(query, source),
      took_ms: Math.round(performance.now() - started),
      mode: "demo",
    });

  try {
    const url = new URL(`${base.replace(/\/$/, "")}/search`);
    url.searchParams.set("q", query);
    if (source) url.searchParams.set("source", source);
    if (page) url.searchParams.set("page", page);
    if (mode) url.searchParams.set("mode", mode);
    const response = await backend.get(url.toString(), { timeout: 10000 });
    if (!isOk(response.status))
      return json(
        { error: "The search service is unavailable. Please try again." },
        502,
      );
    const data = response.data;
    if (
      !data ||
      !Array.isArray(data.results) ||
      !data.results.every(isSearchResult)
    ) {
      return json(
        { error: "The search service returned an invalid response." },
        502,
      );
    }
    return json({
      query,
      results: data.results,
      took_ms: Math.round(performance.now() - started),
      mode: "live",
      overviewToken: signOverviewContext(query, data.results),
    });
  } catch (error) {
    const timeout = isTimeout(error);
    return json(
      {
        error: timeout
          ? "Search timed out. Please try again."
          : "Cannot reach the search service. Please try again.",
      },
      timeout ? 504 : 502,
    );
  }
}
