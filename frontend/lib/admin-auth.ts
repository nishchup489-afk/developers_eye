import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, userFromSession } from "./admin-session";

export async function getAdmin() {
  return userFromSession((await cookies()).get(SESSION_COOKIE)?.value);
}

export async function requireAdmin() {
  const user = await getAdmin();
  if (!user) redirect("/admin/login");
  return user;
}
