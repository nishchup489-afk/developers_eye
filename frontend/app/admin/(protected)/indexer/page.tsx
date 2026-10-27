import { requireAdmin } from "@/lib/admin-auth";
import IndexerControlCenter from "@/components/admin/indexer-control-center";

export default async function IndexerPage() {
  await requireAdmin();
  return <IndexerControlCenter />;
}
