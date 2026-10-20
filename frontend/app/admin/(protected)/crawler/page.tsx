import { requireAdmin } from "@/lib/admin-auth";
import CrawlerDashboard from "@/components/admin/crawler-dashboard";

export default async function CrawlerPage() {
  await requireAdmin();
  return <CrawlerDashboard />;
}
