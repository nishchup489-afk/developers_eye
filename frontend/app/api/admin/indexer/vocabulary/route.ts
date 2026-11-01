import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isVocabularyReport } from "@/lib/vocabulary-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URLSearchParams();
  const term = new URL(request.url).searchParams.get("q")?.trim();
  if (term) {
    if (term.length > 64) return privateJson({ error: "Search terms are at most 64 characters." }, 400);
    query.set("q", term);
  }
  return adminProxy("indexer/vocabulary", query, isVocabularyReport);
}
