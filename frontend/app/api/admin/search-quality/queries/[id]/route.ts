import { adminProxy, adminWriteProxy, privateJson } from "@/lib/crawler-proxy";
import { isJudgingQuery, QUERY_ID, queryBody } from "@/lib/search-quality";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: Context) {
  const { id } = await params;
  if (!QUERY_ID.test(id)) return privateJson({ error: "Invalid query id." }, 400);
  return adminProxy(`search-quality/queries/${id}`, new URLSearchParams(), isJudgingQuery);
}

export async function PUT(request: Request, { params }: Context) {
  const { id } = await params;
  if (!QUERY_ID.test(id)) return privateJson({ error: "Invalid query id." }, 400);
  const body = queryBody(await request.json().catch(() => null));
  if (!body) return privateJson({ error: "Send a query of 1-256 characters, a mode (all, text or code) and notes of at most 2,000 characters." }, 400);
  return adminWriteProxy(request, "PUT", `search-quality/queries/${id}`, body);
}

export async function DELETE(request: Request, { params }: Context) {
  const { id } = await params;
  if (!QUERY_ID.test(id)) return privateJson({ error: "Invalid query id." }, 400);
  return adminWriteProxy(request, "DELETE", `search-quality/queries/${id}`);
}
