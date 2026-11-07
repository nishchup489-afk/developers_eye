import { requireViewer } from "@/lib/admin-auth";
import CorpusControlCenter from "@/components/admin/corpus-control-center";

export default async function CorpusPage() {
  await requireViewer();
  return <CorpusControlCenter />;
}
