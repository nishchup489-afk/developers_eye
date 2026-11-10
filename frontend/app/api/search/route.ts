import { backend, isOk, isTimeout, searchRequestOptions } from "@/lib/axios";
import { searchDemo } from "@/lib/demo";
import {
  forwardedFor,
  isSearchableLength,
  isSearchResult,
  queryLengthError,
  sources,
  upstreamFailure,
} from "@/lib/search";

// Above FastAPI's total search deadline (SEARCH_TOTAL_DEADLINE_MS, 4 s), so a slow
// search comes back as FastAPI's 504 rather than as this proxy giving up.
const backendTimeoutMs = 6000;

export async function GET(request: Request) {
  const started = performance.now();
  const params = new URL(request.url).searchParams;
  const query = params.get("q")?.trim() ?? "";
  const source = params.get("source") ?? "";
  const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store", ...headers } });
  if (!isSearchableLength(query)) return json({ error: queryLengthError }, 400);
  if (source && ![...sources, "discussions"].includes(source))
    return json({ error: "Unknown source filter." }, 400);
  const page = params.get("page") ?? "";
  const mode = params.get("mode") ?? "";
  const language = params.get("language") ?? "";
  const limit = params.get("limit") ?? "";
  if (language && !/^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8}){0,2}$/.test(language))
    return json({ error: "Unknown language preference." }, 400);
  if (limit && (!/^[1-9][0-9]?$/.test(limit) || Number(limit) > 50))
    return json({ error: "Page size must be between 1 and 50." }, 400);
  if ((Number(page || 1) - 1) * Number(limit || 20) > 1000)
    return json({ error: "This page is too deep." }, 400);
  if (page && !/^[1-9][0-9]{0,3}$/.test(page))
    return json({ error: "Unknown page." }, 400);
  if (mode && !["all", "text", "code"].includes(mode))
    return json({ error: "Unknown search mode." }, 400);

  const base = process.env.BACKEND_URL;
  if (!base)
    return json({
      query,
      results: searchDemo(query, source).slice((Number(page || 1) - 1) * Number(limit || 20), Number(page || 1) * Number(limit || 20)),
      took_ms: Math.round(performance.now() - started),
      mode: "demo",
    });

  try {
    const url = new URL(`${base.replace(/\/$/, "")}/search`);
    url.searchParams.set("q", query);
    if (source) url.searchParams.set("source", source);
    if (page) url.searchParams.set("page", page);
    if (mode) url.searchParams.set("mode", mode);
    if (language) url.searchParams.set("language", language);
    if (limit) url.searchParams.set("limit", limit);
    // request.signal aborts when the browser goes away (a newer search, a closed tab);
    // aborting the upstream request makes FastAPI cancel the database work too.
    const response = await backend.get(url.toString(), {
      ...searchRequestOptions,
      timeout: backendTimeoutMs,
      signal: request.signal,
      headers: forwardedFor(request),
    });
    if (!isOk(response.status)) {
      const failure = upstreamFailure(response.status, response.headers["retry-after"]);
      return json(
        { error: failure.error },
        failure.status,
        failure.retryAfter ? { "Retry-After": failure.retryAfter } : {},
      );
    }
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
      overviewToken: typeof data.overview_token === "string" ? data.overview_token : undefined,
    });
  } catch (error) {
    // Nobody is listening; 499 only shows up in logs.
    if (request.signal.aborted) return new Response(null, { status: 499 });
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
