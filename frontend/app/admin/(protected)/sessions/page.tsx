import { requireViewer } from "@/lib/admin-auth";
import CrawlSessions from "@/components/admin/crawl-sessions";

export default async function SessionsPage() {
  await requireViewer();
  return <CrawlSessions />;
}
