import { redirect } from "next/navigation";
import { getViewer } from "@/lib/admin-auth";

export default async function AdminPage() {
  redirect(await getViewer() ? "/admin/crawler" : "/admin/login");
}
