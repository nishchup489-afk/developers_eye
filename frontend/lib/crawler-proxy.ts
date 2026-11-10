import "server-only";
import { getAdmin, getViewer } from "@/lib/admin-auth";
import { adminConfig, type Viewer } from "@/lib/admin-session";
import { adminGet, adminWrite, isOk, isTimeout } from "@/lib/axios";

export const privateJson = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "private, no-store", Vary: "Cookie" } });

export const crawlerProxy = (path: string, query: URLSearchParams, validate: (value: unknown) => boolean) => adminProxy(`crawler/${path}`, query, validate);

// `path` is relative to the backend's /admin/ prefix, e.g. "crawler/monitor" or "indexer/report".
// Every proxied report is a GET, so viewers may read them. `redact` trims fields viewers should not see.
function backendUrl(path: string, query: URLSearchParams) {
  const base = process.env.CRAWLER_REPORT_API_URL;
  const key = process.env.CRAWLER_REPORT_API_KEY;
  if (!base || !key || key.length < 32) return { error: "Configure CRAWLER_REPORT_API_URL and CRAWLER_REPORT_API_KEY on the frontend server." } as const;
  const url = new URL(base);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || !url.pathname.endsWith("/crawler/report")) return { error: "CRAWLER_REPORT_API_URL must end with /admin/crawler/report." } as const;
  url.pathname = url.pathname.slice(0, -"crawler/report".length) + path;
  url.search = query.toString();
  return { url, key } as const;
}

// Writes are for administrators only (never viewers or guests), and must come from this app's own
// origin so another site cannot submit them with the admin's cookie. The admin's login is passed as
// `judge` so the backend records who changed what.
export async function adminWriteProxy(request: Request, method: "PUT" | "POST" | "DELETE", path: string, body?: Record<string, unknown>, query = new URLSearchParams()) {
  const { origin } = adminConfig();
  if (!origin || request.headers.get("origin") !== origin) return privateJson({ error: "Invalid request origin." }, 403);
  const admin = await getAdmin();
  if (!admin) return privateJson({ error: "Only administrators can change search judgments. Sign in again." }, 401);
  try {
    const target = backendUrl(path, query);
    if ("error" in target) return privateJson({ error: target.error }, 503);
    const upstream = await adminWrite(method, target.url, target.key, body === undefined ? undefined : { ...body, judge: admin.login });
    const data = upstream.data as { detail?: unknown } | null;
    if (isOk(upstream.status)) return privateJson(data);
    if (upstream.status === 422) return privateJson({ error: typeof data?.detail === "string" ? data.detail : "The backend rejected this change." }, 422);
    return privateJson({ error: upstream.status === 404 ? "This judging query no longer exists." : upstream.status === 503 ? "Search quality storage is unavailable. Apply the backend migration." : "The backend could not save this change." }, upstream.status === 404 ? 404 : 502);
  } catch (error) {
    const timeout = isTimeout(error);
    return privateJson({ error: timeout ? "The request timed out." : "Cannot connect to the backend." }, timeout ? 504 : 502);
  }
}

export async function adminProxy(path: string, query: URLSearchParams, validate: (value: unknown) => boolean, redact?: (data: unknown, viewer: Viewer) => unknown) {
  const viewer = await getViewer();
  if (!viewer) return privateJson({ error: "Your admin session has expired. Sign in again." }, 401);
  try {
    const target = backendUrl(path, query);
    if ("error" in target) return privateJson({ error: target.error }, 503);
    const upstream = await adminGet(target.url, target.key);
    if (!isOk(upstream.status)) return privateJson({ error: upstream.status === 404 ? "This record is no longer available." : upstream.status === 503 ? "Monitoring is unavailable. Apply the backend migration and check the database connection." : "The crawler service could not complete this request. Check the backend connection and API key." }, upstream.status === 404 ? 404 : 502);
    const data = upstream.data;
    if (!validate(data)) return privateJson({ error: "The crawler service returned invalid monitoring data." }, 502);
    return privateJson(redact ? redact(data, viewer) : data);
  } catch (error) {
    const timeout = isTimeout(error);
    return privateJson({ error: timeout ? "The monitoring request timed out." : "Cannot connect to crawler monitoring. Check that the backend is running." }, timeout ? 504 : 502);
  }
}
