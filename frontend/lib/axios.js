import axios, { isAxiosError } from "axios";

// Every axios instance in the frontend lives here. Both resolve every status, so callers
// read `response.status` and map failures to their own messages instead of catching AxiosError.

/**
 * Shared typed transport interface for browser and server callers.
 * @param {import("axios").CreateAxiosDefaults} [options]
 * @returns {import("axios").AxiosInstance}
 */
function createHttpClient(options = {}) {
  return axios.create({
    adapter: "fetch",
    fetchOptions: { cache: "no-store" },
    headers: { Accept: "application/json" },
    validateStatus: () => true,
    ...options,
  });
}

// Browser client for this app's own /api routes.
export const api = createHttpClient({ baseURL: "/api" });

/**
 * fetch that always settles when its signal aborts. Next's patched fetch can ignore the
 * signal on a server process's first hanging request, so a stalled upstream would never
 * time out; racing the signal makes the axios timeout reject either way.
 * @type {(input: URL | Request | string, init?: RequestInit) => Promise<Response>}
 */
function abortableFetch(input, init) {
  const signal = input instanceof Request ? input.signal : init?.signal;
  const pending = fetch(input, { ...init, signal });
  if (!signal) return pending;
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    if (signal.aborted) return abort();
    signal.addEventListener("abort", abort, { once: true });
    pending.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

// Server client for Next.js -> FastAPI and GitHub. The fetch adapter keeps Next's `no-store`
// semantics, and `redirect: "error"` refuses to follow redirects so a bearer key is never
// replayed to another host. Holds no secrets: keys are passed per request by server routes.
export const backend = createHttpClient({
  timeout: 15000,
  // axios hands fetch a Request whose signal carries the timeout; Next's patched fetch only
  // honours `init.signal`, so pass it through. Resolving `fetch` per call also picks up
  // Next's patch (and test doubles) installed after this module loads.
  env: { fetch: abortableFetch },
  fetchOptions: { cache: "no-store", redirect: "error" },
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
