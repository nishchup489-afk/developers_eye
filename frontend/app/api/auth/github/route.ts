import { createHash, randomBytes } from "node:crypto";
import { NextResponse } from "next/server";
import { adminConfig, cookieOptions, FLOW_COOKIE, seal } from "@/lib/admin-session";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const config = adminConfig();
  if (!config.ready) return NextResponse.redirect(new URL("/admin/login?error=configuration", request.url));
  const state = randomBytes(32).toString("base64url");
  const verifier = randomBytes(32).toString("base64url");
  const url = new URL("https://github.com/login/oauth/authorize");
  url.search = new URLSearchParams({ client_id: config.clientId, redirect_uri: `${config.origin}/api/auth/github/callback`, state,
    code_challenge: createHash("sha256").update(verifier).digest("base64url"), code_challenge_method: "S256", allow_signup: "false" }).toString();
  const response = NextResponse.redirect(url);
  response.headers.set("Cache-Control", "no-store");
  response.cookies.set(FLOW_COOKIE, seal({ state, verifier }, "oauth", 600), cookieOptions(600));
  return response;
}
