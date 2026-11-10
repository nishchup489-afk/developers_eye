import { adminWriteProxy, privateJson } from "@/lib/crawler-proxy";
import { judgmentBody, QUERY_ID } from "@/lib/search-quality";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ id: string }> };

export async function PUT(request: Request, { params }: Context) {
  const { id } = await params;
  if (!QUERY_ID.test(id)) return privateJson({ error: "Invalid query id." }, 400);
  const body = judgmentBody(await request.json().catch(() => null));
  if (!body) return privateJson({ error: "Send an http(s) URL, a grade of 0-3 or null, and a note of at most 2,000 characters." }, 400);
  return adminWriteProxy(request, "PUT", `search-quality/queries/${id}/judgments`, body);
}

// Removes a page the judge added by hand; pooled pages stay so the pool remains complete.
export async function DELETE(request: Request, { params }: Context) {
  const { id } = await params;
  const url = new URL(request.url).searchParams.get("url") ?? "";
  if (!QUERY_ID.test(id) || !/^https?:\/\//.test(url) || url.length > 2048) return privateJson({ error: "Invalid query id or URL." }, 400);
  return adminWriteProxy(request, "DELETE", `search-quality/queries/${id}/judgments`, undefined, new URLSearchParams({ url }));
}
