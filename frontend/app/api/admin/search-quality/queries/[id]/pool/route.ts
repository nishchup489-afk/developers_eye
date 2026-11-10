import { adminWriteProxy, privateJson } from "@/lib/crawler-proxy";
import { QUERY_ID } from "@/lib/search-quality";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Re-runs both rankers and adds their top results to the pool; grades already given are kept.
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!QUERY_ID.test(id)) return privateJson({ error: "Invalid query id." }, 400);
  return adminWriteProxy(request, "POST", `search-quality/queries/${id}/pool`);
}
