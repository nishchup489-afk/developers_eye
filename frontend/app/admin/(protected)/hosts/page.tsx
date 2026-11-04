import { requireViewer } from "@/lib/admin-auth";
import HostsControlCenter from "@/components/admin/hosts-control-center";

export default async function HostsPage() {
  await requireViewer();
  return <HostsControlCenter />;
}
