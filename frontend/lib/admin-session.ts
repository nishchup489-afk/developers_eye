import { createHmac, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "de_admin_session";
export const FLOW_COOKIE = "de_github_flow";
export const SESSION_SECONDS = 60 * 60 * 8;

export type AdminUser = { id: number; login: string; name: string | null };
export type ViewerRole = "admin" | "viewer" | "guest";
// A guest is an anonymous visitor, allowed only when ADMIN_VIEWER_ACCESS=public.
export type Viewer = (AdminUser & { role: "admin" | "viewer" }) | { id: null; login: null; name: null; role: "guest" };
export type ViewerAccess = "off" | "github" | "public";

export function adminConfig() {
  const secret = process.env.ADMIN_SESSION_SECRET ?? "";
  const clientId = process.env.GITHUB_CLIENT_ID ?? "";
  const clientSecret = process.env.GITHUB_CLIENT_SECRET ?? "";
  const ids = parseIds(process.env.ADMIN_GITHUB_IDS);
  // Read-only access: listed GitHub ids, any GitHub account ("github"), or anyone ("public").
  const viewerIds = parseIds(process.env.ADMIN_VIEWER_GITHUB_IDS);
  const access = (process.env.ADMIN_VIEWER_ACCESS ?? "off").trim().toLowerCase();
  const viewerAccess: ViewerAccess = access === "github" || access === "public" ? access : "off";
  let origin = "";
  try {
    const url = new URL(process.env.ADMIN_APP_URL ?? "");
    if (!url.username && !url.password && url.pathname === "/" && !url.search && !url.hash &&
      (url.protocol === "https:" || (url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))) origin = url.origin;
  } catch {}
  return { secret, clientId, clientSecret, ids, viewerIds, viewerAccess, origin, ready: Boolean(secret.length >= 32 && clientId && clientSecret && ids.length && origin) };
}

function parseIds(value: string | undefined) {
  return (value ?? "").split(",").map((id) => id.trim()).filter((id) => /^[1-9]\d*$/.test(id));
}

export function seal(value: object, purpose: "session" | "oauth", lifetime: number): string {
  const { secret } = adminConfig();
  if (secret.length < 32) throw new Error("Admin session secret is not configured");
  const payload = Buffer.from(JSON.stringify({ ...value, purpose, exp: Math.floor(Date.now() / 1000) + lifetime })).toString("base64url");
  const signature = createHmac("sha256", secret).update(payload).digest("base64url");
  return `${payload}.${signature}`;
}

export function unseal(token: string | undefined, purpose: "session" | "oauth"): Record<string, unknown> | null {
  const { secret } = adminConfig();
  if (!token || token.length > 4096 || secret.length < 32) return null;
  const parts = token.split(".");
  if (parts.length !== 2 || !/^[A-Za-z0-9_-]+$/.test(parts[1])) return null;
  const expected = createHmac("sha256", secret).update(parts[0]).digest();
  const actual = Buffer.from(parts[1], "base64url");
  if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) return null;
  try {
    const data = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf8"));
    return data && data.purpose === purpose && Number.isSafeInteger(data.exp) && data.exp > Math.floor(Date.now() / 1000) ? data : null;
  } catch { return null; }
}

function identityFromSession(token: string | undefined): AdminUser | null {
  const data = unseal(token, "session");
  if (!data || !Number.isSafeInteger(data.id) ||
    typeof data.login !== "string" || !/^[a-zA-Z0-9-]{1,39}$/.test(data.login) ||
    !(data.name === null || typeof data.name === "string")) return null;
  return { id: data.id as number, login: data.login, name: data.name as string | null };
}

// Role is decided from the current allowlists on every request, so removing an id revokes access at once.
export function roleFor(id: number): "admin" | "viewer" | null {
  const config = adminConfig();
  if (config.ids.includes(String(id))) return "admin";
  if (config.viewerIds.includes(String(id)) || config.viewerAccess === "github") return "viewer";
  return null;
}

export function userFromSession(token: string | undefined): AdminUser | null {
  if (!adminConfig().ready) return null;
  const identity = identityFromSession(token);
  return identity && roleFor(identity.id) === "admin" ? identity : null;
}

export function viewerFromSession(token: string | undefined): Viewer | null {
  const config = adminConfig();
  if (config.ready) {
    const identity = identityFromSession(token);
    const role = identity && roleFor(identity.id);
    if (identity && role) return { ...identity, role };
  }
  return config.viewerAccess === "public" ? { id: null, login: null, name: null, role: "guest" } : null;
}

export function cookieOptions(maxAge: number) {
  return { httpOnly: true, secure: adminConfig().origin.startsWith("https:"), sameSite: "lax" as const, path: "/", maxAge };
}
