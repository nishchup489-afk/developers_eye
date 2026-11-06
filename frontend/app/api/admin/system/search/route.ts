import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isSearchReport, redactSearchReport, type SearchReport } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URLSearchParams();
  const hours = new URL(request.url).searchParams.get("hours");
  if (hours !== null) {
    if (!/^\d{1,3}$/.test(hours) || Number(hours) < 1 || Number(hours) > 168) return privateJson({ error: "Invalid hours parameter." }, 400);
    query.set("hours", hours);
  }
  return adminProxy("system/search", query, isSearchReport, (data, viewer) => redactSearchReport(data as SearchReport, viewer.role));
}
