import axios from "axios";

// Browser client for this app's own /api routes. Every status resolves so callers read
// `response.status` and the route's `{ error }` body instead of catching AxiosError.
export const api = axios.create({
  baseURL: "/api",
  adapter: "fetch",
  fetchOptions: { cache: "no-store" },
  headers: { Accept: "application/json" },
  validateStatus: () => true,
});

export const isCancelled = (error: unknown) => axios.isCancel(error);
