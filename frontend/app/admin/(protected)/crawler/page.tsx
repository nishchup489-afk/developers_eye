import { requireAdmin } from "@/lib/admin-auth";
import CrawlerDashboard from "@/components/admin/crawler-control-center";

export default async function CrawlerPage() {
  await requireAdmin();
  return <CrawlerDashboard />;
}
