import { adminProxy } from "@/lib/crawler-proxy";
import { isProblemsReport } from "@/lib/system-report";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return adminProxy("system/problems", new URLSearchParams(), isProblemsReport);
}
