import SearchQuality from "@/components/admin/search-quality";
import { requireViewer } from "@/lib/admin-auth";

export default async function SearchQualityPage() {
  const viewer = await requireViewer();
  return <SearchQuality canEdit={viewer.role === "admin"} />;
}
