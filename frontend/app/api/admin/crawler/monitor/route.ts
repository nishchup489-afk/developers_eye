import { crawlerProxy, privateJson } from "@/lib/crawler-proxy";
import { isCrawlMonitor } from "@/lib/crawler-monitor";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const incoming = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  const ranges: Record<string, [number, number]> = { days: [1, 365], source_id: [1, Number.MAX_SAFE_INTEGER], document_page: [0, 10000], frontier_page: [0, 10000], before_event_id: [1, Number.MAX_SAFE_INTEGER] };
  for (const [name, [min, max]] of Object.entries(ranges)) {
    const value = incoming.get(name);
    if (value === null) continue;
    if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < min || Number(value) > max) return privateJson({ error: `Invalid ${name} parameter.` }, 400);
    query.set(name, value);
  }
  const choices: Record<string, string[]> = {
    status: ["running", "success", "failed", "blocked", "accepted", "skipped", "persisted", "not_stored", "duplicate", "new", "updated", "unchanged", "not_modified", "stale", "complete"],
    category: ["fetch", "parse", "process", "processing", "dedup", "store", "discover", "finalize", "worker"],
    frontier_state: ["due", "scheduled", "expired", "retry", "queued", "leased", "blocked", "disabled"],
  };
  for (const [name, values] of Object.entries(choices)) {
    const value = incoming.get(name);
    if (value === null) continue;
    if (!values.includes(value)) return privateJson({ error: `Invalid ${name} parameter.` }, 400);
    query.set(name, value);
  }
  const search = incoming.get("q");
  if (search !== null) {
    if (search.length > 200) return privateJson({ error: "Search must be 200 characters or fewer." }, 400);
    query.set("q", search);
  }
  return crawlerProxy("monitor", query, isCrawlMonitor);
}
