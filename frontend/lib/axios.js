import axios, { isAxiosError } from "axios";

// Every axios instance in the frontend lives here. Both resolve every status, so callers
// read `response.status` and map failures to their own messages instead of catching AxiosError.

// Browser client for this app's own /api routes.
export const api = axios.create({
  baseURL: "/api",
  adapter: "fetch",
  fetchOptions: { cache: "no-store" },
  headers: { Accept: "application/json" },
  validateStatus: () => true,
});

// Server client for Next.js -> FastAPI and GitHub. The fetch adapter keeps Next's `no-store`
// semantics, and `redirect: "error"` refuses to follow redirects so a bearer key is never
// replayed to another host. Holds no secrets: keys are passed per request by server routes.
export const backend = axios.create({
  adapter: "fetch",
  timeout: 15000,
  // axios hands fetch a Request whose signal carries the timeout; Next's patched fetch only
  // honours `init.signal`, so pass it through. Resolving `fetch` per call also picks up
  // Next's patch (and test doubles) installed after this module loads.
  env: {
    /** @type {(input: URL | Request | string, init?: RequestInit) => Promise<Response>} */
    fetch: (input, init) => fetch(input, { ...init, signal: input instanceof Request ? input.signal : init?.signal }),
  },
  fetchOptions: { cache: "no-store", redirect: "error" },
  headers: { Accept: "application/json" },
  validateStatus: () => true,
});

/** @param {number} status */
export const isOk = (status) => status >= 200 && status < 300;

/** @param {unknown} error */
export const isCancelled = (error) => axios.isCancel(error);

/** @param {unknown} error */
export function isTimeout(error) {
  if (isAxiosError(error)) {
    if (error.code === "ETIMEDOUT" || error.code === "ECONNABORTED") return true;
    error = error.cause;
  }
  return error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name);
}

// GET a FastAPI admin endpoint with the shared service key (server routes only).
/** @param {URL} url @param {string} key */
export const adminGet = (url, key) => backend.get(url.toString(), { headers: { Authorization: `Bearer ${key}` } });
