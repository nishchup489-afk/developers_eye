import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, userFromSession, viewerFromSession } from "./admin-session";

// Administrators only. Use for anything that changes state.
export async function getAdmin() {
  return userFromSession((await cookies()).get(SESSION_COOKIE)?.value);
}

export async function requireAdmin() {
  const user = await getAdmin();
  if (!user) redirect("/admin/login");
  return user;
}

// Administrators, read-only viewers, and (with ADMIN_VIEWER_ACCESS=public) anonymous guests.
export async function getViewer() {
  return viewerFromSession((await cookies()).get(SESSION_COOKIE)?.value);
}

export async function requireViewer() {
  const viewer = await getViewer();
  if (!viewer) redirect("/admin/login");
  return viewer;
}
