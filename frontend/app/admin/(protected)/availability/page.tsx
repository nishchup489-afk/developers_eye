import { requireViewer } from "@/lib/admin-auth";
import AvailabilityControlCenter from "@/components/admin/availability-control-center";

export default async function AvailabilityPage() {
  await requireViewer();
  return <AvailabilityControlCenter />;
}
