import { adminProxy, privateJson } from "@/lib/crawler-proxy";
import { isEvaluationReport } from "@/lib/search-quality";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const k = new URL(request.url).searchParams.get("k") ?? "10";
  if (k !== "5" && k !== "10") return privateJson({ error: "Invalid k parameter." }, 400);
  return adminProxy("search-quality/evaluation", new URLSearchParams({ k }), isEvaluationReport);
}
