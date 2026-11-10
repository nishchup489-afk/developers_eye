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

// This client also calls GitHub/Wikipedia, so never set the edge secret as a
// default header. Attach it at request time only to configured backend origins.
backend.interceptors.request.use((config) => {
  config.headers.delete("X-Edge-Secret");
  const secret = typeof window === "undefined" ? process.env.EDGE_SHARED_SECRET : undefined;
  if (!secret) return config;
  const target = new URL(backend.getUri(config));
  const origins = [process.env.BACKEND_URL, process.env.CRAWLER_REPORT_API_URL]
    .filter(Boolean).map((value) => new URL(value).origin);
  if (origins.includes(target.origin)) {
    if (target.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(target.hostname))
      throw new Error("The authenticated backend origin must use HTTPS");
    config.headers.set("X-Edge-Secret", secret);
  }
  return config;
});

// Search cancellation must close the socket, not merely reject a fetch promise.
// Node's HTTP adapter bypasses Next's patched fetch and its abort/socket leak.
// Node HTTP has no Next data cache; redirects and environment proxies are disabled.
/** @type {import("axios").AxiosRequestConfig} */
export const searchRequestOptions = Object.freeze({
  adapter: "http",
  maxRedirects: 0,
  proxy: false,
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

// Send a write (PUT, POST or DELETE) to a FastAPI admin endpoint with the shared service key (server routes only).
/** @param {"PUT" | "POST" | "DELETE"} method @param {URL} url @param {string} key @param {unknown} [data] */
export const adminWrite = (method, url, key, data) => backend.request({ method, url: url.toString(), data, headers: { Authorization: `Bearer ${key}` } });
