import "server-only";
import { getAdmin } from "@/lib/admin-auth";

export const privateJson = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "private, no-store", Vary: "Cookie" } });

export const crawlerProxy = (path: string, query: URLSearchParams, validate: (value: unknown) => boolean) => adminProxy(`crawler/${path}`, query, validate);

// `path` is relative to the backend's /admin/ prefix, e.g. "crawler/monitor" or "indexer/report".
export async function adminProxy(path: string, query: URLSearchParams, validate: (value: unknown) => boolean) {
  if (!await getAdmin()) return privateJson({ error: "Your admin session has expired. Sign in again." }, 401);
  const base = process.env.CRAWLER_REPORT_API_URL;
  const key = process.env.CRAWLER_REPORT_API_KEY;
  if (!base || !key || key.length < 32) return privateJson({ error: "Configure CRAWLER_REPORT_API_URL and CRAWLER_REPORT_API_KEY on the frontend server." }, 503);
  try {
    const url = new URL(base);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || !url.pathname.endsWith("/crawler/report")) return privateJson({ error: "CRAWLER_REPORT_API_URL must end with /admin/crawler/report." }, 503);
    url.pathname = url.pathname.slice(0, -"crawler/report".length) + path;
    url.search = query.toString();
    const upstream = await fetch(url, { headers: { Accept: "application/json", Authorization: `Bearer ${key}` }, cache: "no-store", signal: AbortSignal.timeout(15000), redirect: "error" });
    if (!upstream.ok) return privateJson({ error: upstream.status === 404 ? "This record is no longer available." : upstream.status === 503 ? "Monitoring is unavailable. Apply the backend migration and check the database connection." : "The crawler service could not complete this request. Check the backend connection and API key." }, upstream.status === 404 ? 404 : 502);
    const data: unknown = await upstream.json();
    if (!validate(data)) return privateJson({ error: "The crawler service returned invalid monitoring data." }, 502);
    return privateJson(data);
  } catch (error) {
    const timeout = error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name);
    return privateJson({ error: timeout ? "The monitoring request timed out." : "Cannot connect to crawler monitoring. Check that the backend is running." }, timeout ? 504 : 502);
  }
}
