import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { backend, isOk } from "@/lib/backend-client";
import { adminConfig, cookieOptions, FLOW_COOKIE, seal, SESSION_COOKIE, SESSION_SECONDS, unseal } from "@/lib/admin-session";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const config = adminConfig();
  function finish(path: string) {
    const response = NextResponse.redirect(new URL(path, config.origin || request.url));
    response.headers.set("Cache-Control", "no-store");
    response.headers.set("Referrer-Policy", "no-referrer");
    response.cookies.set(FLOW_COOKIE, "", cookieOptions(0));
    return response;
  }
  if (!config.ready) return finish("/admin/login?error=configuration");
  const params = request.nextUrl.searchParams;
  const flow = unseal(request.cookies.get(FLOW_COOKIE)?.value, "oauth");
  const state = params.get("state") ?? "";
  if (!flow || typeof flow.state !== "string" || typeof flow.verifier !== "string" ||
    Buffer.byteLength(state) !== Buffer.byteLength(flow.state) || !timingSafeEqual(Buffer.from(state), Buffer.from(flow.state))) {
    return finish("/admin/login?error=state");
  }
  const code = params.get("code");
  if (params.has("error") || !code || code.length > 512) return finish("/admin/login?error=cancelled");
  try {
    const tokenResponse = await backend.post("https://github.com/login/oauth/access_token",
      new URLSearchParams({ client_id: config.clientId, client_secret: config.clientSecret, code,
        redirect_uri: `${config.origin}/api/auth/github/callback`, code_verifier: flow.verifier }),
      { timeout: 10000 });
    if (!isOk(tokenResponse.status)) return finish("/admin/login?error=provider");
    const token = tokenResponse.data;
    if (typeof token?.access_token !== "string") return finish("/admin/login?error=provider");
    const profileResponse = await backend.get("https://api.github.com/user", {
      headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token.access_token}`, "User-Agent": "DevelopersEye-Admin" },
      timeout: 10000,
    });
    if (!isOk(profileResponse.status)) return finish("/admin/login?error=provider");
    const profile = profileResponse.data;
    if (!Number.isSafeInteger(profile?.id) || !config.ids.includes(String(profile.id)) ||
      typeof profile.login !== "string" || !/^[a-zA-Z0-9-]{1,39}$/.test(profile.login)) return finish("/admin/login?error=denied");
    const response = finish("/admin/crawler");
    // Store only verified public identity. GitHub tokens never enter the session.
    response.cookies.set(SESSION_COOKIE, seal({ id: profile.id, login: profile.login, name: typeof profile.name === "string" ? profile.name.slice(0, 100) : null }, "session", SESSION_SECONDS), cookieOptions(SESSION_SECONDS));
    return response;
  } catch { return finish("/admin/login?error=provider"); }
}
