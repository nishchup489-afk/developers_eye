import { requireViewer } from "@/lib/admin-auth";
import CrawlerDashboard from "@/components/admin/crawler-control-center";

export default async function CrawlerPage() {
  await requireViewer();
  return <CrawlerDashboard />;
}
