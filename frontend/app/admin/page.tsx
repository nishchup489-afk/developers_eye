import { redirect } from "next/navigation";
import { getAdmin } from "@/lib/admin-auth";

export default async function AdminPage() {
  redirect(await getAdmin() ? "/admin/crawler" : "/admin/login");
}
