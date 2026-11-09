import { createHash } from "node:crypto";
import { overviewEnabled, verifyOverviewContext } from "@/lib/ai-overview-context";
import { generateOverview } from "@/lib/ai-overview-server";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const json = (body: unknown, status = 200, retryAfter?: number) => Response.json(body, {
    status, headers: { "Cache-Control": "no-store", ...(retryAfter ? { "Retry-After": String(retryAfter) } : {}) },
  });
  // Reject cross-origin browser calls even when they have obtained a search token.
  const origin = request.headers.get("origin");
  // Next may reconstruct request.url with its internal hostname behind a proxy.
  // Host is the browser-facing authority; never accept arbitrary forwarded hosts.
  let sameHost = !origin;
  try {
    const parsed = new URL(origin!);
    sameHost = ["http:", "https:"].includes(parsed.protocol) &&
      parsed.host === (request.headers.get("host") || new URL(request.url).host);
  } catch { /* Invalid Origin is rejected. */ }
  if (!sameHost || request.headers.get("sec-fetch-site") === "cross-site")
    return json({ error: "Use AI overview from this site." }, 403);
  if (!overviewEnabled()) return json({ overview: null });
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return json({ error: "Expected JSON." }, 415);
  // Bound streaming bodies too; Content-Length alone can be omitted or forged.
  const reader = request.body?.getReader();
  if (!reader) return json({ error: "Missing search context." }, 400);
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 25000) { await reader.cancel(); return json({ error: "Search context too large." }, 413); }
      chunks.push(value);
    }
    const body = JSON.parse(Buffer.concat(chunks).toString());
    const context = verifyOverviewContext(body?.token);
    if (!context) return json({ error: "Refresh your search to generate an overview." }, 400);
    // Only enable a header that your reverse proxy OVERWRITES. Otherwise everyone
    // shares an anonymous bucket, so forged X-Forwarded-For cannot evade limits.
    const header = process.env.AI_OVERVIEW_CLIENT_IP_HEADER;
    const identity = header ? request.headers.get(header)?.trim().slice(0, 200) || "anonymous" : "anonymous";
    const client = createHash("sha256").update(identity).digest("hex");
    const { status, retryAfter, ...result } = await generateOverview(context, client);
    return json(result, status, retryAfter);
  } catch { return json({ error: "Invalid search context." }, 400); }
}
