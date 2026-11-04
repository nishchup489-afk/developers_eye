import { requireViewer } from "@/lib/admin-auth";
import SystemControlCenter from "@/components/admin/system-control-center";

export default async function SystemPage() {
  await requireViewer();
  return <SystemControlCenter />;
}
