import { backend, isTimeout } from "@/lib/axios";

// Transport only. FastAPI owns evidence validation, Groq and all quota/cache state.
export async function POST(request: Request) {
  const json = (body: unknown, status = 200, retryAfter?: string) => Response.json(body, {
    status, headers: { "Cache-Control": "no-store", ...(retryAfter ? { "Retry-After": retryAfter } : {}) },
  });
  const base = process.env.BACKEND_URL;
  if (!base) return json({ overview: null });
  let body: unknown;
  try { body = await request.json(); }
  catch { return json({ error: "Invalid search context." }, 400); }
  try {
    const response = await backend.post(`${base.replace(/\/$/, "")}/search/overview`, body, {
      timeout: 18000,
      // Caddy overwrites this header. FastAPI ignores it unless explicitly trusted.
      headers: {
        ...(request.headers.has("x-eye-client-ip") ? { "X-Eye-Client-IP": request.headers.get("x-eye-client-ip")! } : {}),
        ...(request.headers.has("sec-fetch-site") ? { "Sec-Fetch-Site": request.headers.get("sec-fetch-site")! } : {}),
      },
    });
    return json(response.data, response.status, response.headers["retry-after"]?.toString());
  } catch (error) {
    return json({ error: "AI overview is unavailable right now. Explore the sources below." }, isTimeout(error) ? 504 : 502);
  }
}
