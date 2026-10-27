import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isIndexerReport } from "@/lib/indexer-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URLSearchParams();
  const source = new URL(request.url).searchParams.get("source_id");
  if (source !== null) {
    if (!/^\d+$/.test(source) || !Number.isSafeInteger(Number(source)) || Number(source) < 1) return privateJson({ error: "Invalid source_id parameter." }, 400);
    query.set("source_id", source);
  }
  return adminProxy("indexer/report", query, isIndexerReport);
}
