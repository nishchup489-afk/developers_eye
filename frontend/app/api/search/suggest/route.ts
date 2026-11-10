import { backend, isOk, isTimeout, searchRequestOptions } from "@/lib/axios";
import {
  forwardedFor,
  isSearchableLength,
  maxSuggestQueryLength,
  parseCorrection,
  queryLengthError,
  upstreamFailure,
} from "@/lib/search";

// "Did you mean …" for the results page. Forwards to FastAPI GET /search/suggest,
// which suggests spellings from the indexed vocabulary and never changes a search.
export async function GET(request: Request) {
  const query = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store", ...headers } });
  if (!isSearchableLength(query)) return json({ error: queryLengthError }, 400);
  const none = (mode: "demo" | "live") =>
    json({ query, suggestion: null, corrections: [], mode });

  const base = process.env.BACKEND_URL;
  // Demo fixtures have no vocabulary; pasted code and long queries are not corrected.
  if (!base) return none("demo");
  if (query.length > maxSuggestQueryLength || query.includes("\n"))
    return none("live");

  try {
    const url = new URL(`${base.replace(/\/$/, "")}/search/suggest`);
    url.searchParams.set("q", query);
    // Above FastAPI's 4 s deadline; request.signal cancels when the browser goes away.
    const response = await backend.get(url.toString(), {
      ...searchRequestOptions,
      timeout: 5000,
      signal: request.signal,
      headers: forwardedFor(request),
    });
    // The backend rejects queries its analyzer refuses; that just means no suggestion.
    if (response.status === 422) return none("live");
    if (!isOk(response.status)) {
      const failure = upstreamFailure(
        response.status,
        response.headers["retry-after"],
        "Suggestions",
      );
      return json(
        { error: failure.error },
        failure.status,
        failure.retryAfter ? { "Retry-After": failure.retryAfter } : {},
      );
    }
    const parsed = parseCorrection(response.data, query);
    if (!parsed)
      return json(
        { error: "The suggestion service returned an invalid response." },
        502,
      );
    return json({ query, ...parsed, mode: "live" });
  } catch (error) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    const timeout = isTimeout(error);
    return json(
      {
        error: timeout
          ? "Suggestions timed out."
          : "Cannot reach the suggestion service.",
      },
      timeout ? 504 : 502,
    );
  }
}
