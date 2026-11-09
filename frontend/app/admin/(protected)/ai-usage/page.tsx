import AIUsage from "@/components/admin/ai-usage";
import { requireViewer } from "@/lib/admin-auth";
export default async function Page() { await requireViewer(); return <AIUsage />; }
