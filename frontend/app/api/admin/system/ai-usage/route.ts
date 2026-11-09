import { adminProxy } from "@/lib/crawler-proxy";
export async function GET() {
  return adminProxy("system/ai-usage", new URLSearchParams(), (value: unknown) => {
    if (!value || typeof value !== "object") return false;
    const data = value as Record<string, unknown>;
    return typeof data.model === "string" && Array.isArray(data.windows) && typeof data.accounting === "string";
  });
}
