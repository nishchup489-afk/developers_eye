import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isSystemReport, redactSystemReport, type SystemReport } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URLSearchParams();
  const days = new URL(request.url).searchParams.get("days");
  if (days !== null) {
    if (!/^\d{1,2}$/.test(days) || Number(days) < 1 || Number(days) > 90) return privateJson({ error: "Invalid days parameter." }, 400);
    query.set("days", days);
  }
  return adminProxy("system/report", query, isSystemReport, (data, viewer) => redactSystemReport(data as SystemReport, viewer.role));
}
