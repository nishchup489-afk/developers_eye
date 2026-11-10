import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isSlowSearchReport, redactSlowSearchReport, type SlowSearchReport } from "@/lib/search-quality";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  for (const [name, max] of [["hours", 720], ["limit", 500]] as const) {
    const raw = params.get(name);
    if (raw === null) continue;
    if (!/^\d{1,3}$/.test(raw) || Number(raw) < 1 || Number(raw) > max) return privateJson({ error: `Invalid ${name} parameter.` }, 400);
    query.set(name, raw);
  }
  return adminProxy("search-quality/slow", query, isSlowSearchReport, (data, viewer) => redactSlowSearchReport(data as SlowSearchReport, viewer.role));
}
