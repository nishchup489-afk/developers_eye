import "server-only";
import axios, { isAxiosError } from "axios";

// Server-only client for Next.js -> FastAPI and other upstream calls. The fetch adapter
// keeps Next's `no-store` semantics, and `redirect: "error"` refuses to follow redirects
// so a bearer key is never replayed to another host. Every status resolves so routes map
// upstream failures to their own messages.
export const backend = axios.create({
  adapter: "fetch",
  // axios hands fetch a Request whose signal carries the timeout; Next's patched fetch only
  // honours `init.signal`, so pass it through. Resolving `fetch` per call also picks up
  // Next's patch (and test doubles) installed after this module loads.
  env: { fetch: (input: URL | Request | string, init?: RequestInit) => fetch(input, { ...init, signal: input instanceof Request ? input.signal : init?.signal }) },
  timeout: 15000,
  fetchOptions: { cache: "no-store", redirect: "error" },
  headers: { Accept: "application/json" },
  validateStatus: () => true,
});

export const isOk = (status: number) => status >= 200 && status < 300;

export function isTimeout(error: unknown) {
  if (isAxiosError(error)) {
    if (error.code === "ETIMEDOUT" || error.code === "ECONNABORTED") return true;
    error = error.cause;
  }
  return error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name);
}

// GET a FastAPI admin endpoint with the shared service key.
export const adminGet = (url: URL, key: string) => backend.get<unknown>(url.toString(), { headers: { Authorization: `Bearer ${key}` } });
