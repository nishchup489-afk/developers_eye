import { crawlerProxy, privateJson } from "@/lib/crawler-proxy";
import { isCrawlSessionsReport } from "@/lib/crawler-sessions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  const limit = params.get("limit");
  if (limit !== null) {
    if (!/^\d{1,2}$/.test(limit) || Number(limit) < 1 || Number(limit) > 50) return privateJson({ error: "Invalid limit parameter." }, 400);
    query.set("limit", limit);
  }
  const start = params.get("start"), end = params.get("end");
  for (const [name, value] of [["start", start], ["end", end]] as const) {
    if (value === null) continue;
    const at = Date.parse(value);
    if (value.length > 40 || Number.isNaN(at)) return privateJson({ error: `Invalid ${name} time.` }, 400);
    query.set(name, new Date(at).toISOString());
  }
  if (end !== null && start === null) return privateJson({ error: "Choose a start time." }, 400);
  if (start !== null && end !== null && Date.parse(end) <= Date.parse(start)) return privateJson({ error: "The end time must be after the start time." }, 400);
  return crawlerProxy("sessions", query, isCrawlSessionsReport);
}
