import { adminProxy } from "@/lib/crawler-proxy";
import { isCorpusReport } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return adminProxy("system/corpus", new URLSearchParams(), isCorpusReport);
}
