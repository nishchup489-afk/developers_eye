import { crawlerProxy, privateJson } from "@/lib/crawler-proxy";
import { isAttemptDetail, isDocumentDetail } from "@/lib/crawler-monitor";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const type = query.get("type"), id = query.get("id") ?? "";
  if (!["documents", "attempts"].includes(type ?? "") || !/^\d+$/.test(id) || !Number.isSafeInteger(Number(id)) || Number(id) < 1) return privateJson({ error: "Choose a valid document or attempt ID." }, 400);
  return crawlerProxy(`${type}/${id}`, new URLSearchParams(), type === "documents" ? isDocumentDetail : isAttemptDetail);
}
