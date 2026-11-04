import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isHostReport } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URLSearchParams();
  const minutes = new URL(request.url).searchParams.get("minutes");
  if (minutes !== null) {
    if (!/^\d{1,4}$/.test(minutes) || Number(minutes) < 5 || Number(minutes) > 1440) return privateJson({ error: "Invalid minutes parameter." }, 400);
    query.set("minutes", minutes);
  }
  return adminProxy("system/hosts", query, isHostReport);
}
