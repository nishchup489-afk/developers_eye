import type { Metadata } from "next";
import "./admin.css";
import "./control-center.css";

export const metadata: Metadata = { title: "Admin | Developer's Eye", robots: { index: false, follow: false } };
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <div className="admin-root">{children}</div>;
}
