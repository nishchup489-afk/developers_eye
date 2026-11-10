import { adminWriteProxy } from "@/lib/crawler-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Adds the prepared 36-query judging set; existing queries and their grades are kept.
export async function POST(request: Request) {
  return adminWriteProxy(request, "POST", "search-quality/queries/import");
}
