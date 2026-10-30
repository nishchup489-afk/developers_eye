import { getAdmin } from "@/lib/admin-auth";
import { adminGet, isOk, isTimeout } from "@/lib/backend-client";
import { isCrawlerReport } from "@/lib/crawler-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "private, no-store", Vary: "Cookie" } });
  if (!await getAdmin()) return json({ error: "Your admin session has expired. Sign in again." }, 401);
  const params = new URL(request.url).searchParams;
  const limits = { days: [1, 365, 7], top_sources: [1, 100, 20], recent_errors: [0, 100, 20] };
  const query = new URLSearchParams();
  for (const [name, [min, max, fallback]] of Object.entries(limits)) {
    const raw = params.get(name) ?? String(fallback);
    const number = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isInteger(number) || number < min || number > max) return json({ error: `Invalid ${name} parameter.` }, 400);
    query.set(name, String(number));
  }
  const base = process.env.CRAWLER_REPORT_API_URL;
  const key = process.env.CRAWLER_REPORT_API_KEY;
  if (!base || !key || key.length < 32) return json({ error: "The reporting connection is not configured. Set CRAWLER_REPORT_API_URL and CRAWLER_REPORT_API_KEY on the frontend server." }, 503);
  try {
    const url = new URL(base);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("Invalid reporting URL");
    for (const [name, value] of query) url.searchParams.set(name, value);
    const upstream = await adminGet(url, key);
    if (!isOk(upstream.status)) return json({ error: upstream.status === 401 || upstream.status === 403 ? "The reporting service rejected the connection. Check that both servers use the same API key." : "The reporting service is unavailable. Check the backend and database, then retry." }, 502);
    const data = upstream.data;
    if (!isCrawlerReport(data)) return json({ error: "The reporting service returned an incomplete or invalid snapshot." }, 502);
    return json(data);
  } catch (error) {
    const timeout = isTimeout(error);
    return json({ error: timeout ? "The report took too long to generate. Try a shorter date range." : "Cannot connect to the reporting service. Check that the backend is running." }, timeout ? 504 : 502);
  }
}
