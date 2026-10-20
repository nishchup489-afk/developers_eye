import { NextResponse } from "next/server";
import { adminConfig, cookieOptions, FLOW_COOKIE, SESSION_COOKIE } from "@/lib/admin-session";

export async function POST(request: Request) {
  const { origin } = adminConfig();
  if (!origin || request.headers.get("origin") !== origin) return Response.json({ error: "Invalid request origin." }, { status: 403 });
  const response = NextResponse.redirect(new URL("/admin/login", origin), 303);
  response.headers.set("Cache-Control", "no-store");
  response.cookies.set(SESSION_COOKIE, "", cookieOptions(0));
  response.cookies.set(FLOW_COOKIE, "", cookieOptions(0));
  return response;
}
