import Link from "next/link";
import { ArrowUpRight, BookOpen, Eye, LogOut, Radar, ShieldCheck } from "lucide-react";
import Github from "@/components/admin/github-icon";
import { requireAdmin } from "@/lib/admin-auth";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const user = await requireAdmin();
  return <div className="admin-workspace">
    <a className="admin-skip" href="#main-content">Skip to report</a>
    <aside className="admin-sidebar">
      <Link href="/admin" className="admin-wordmark"><span className="admin-eye"><Eye size={22} /></span><span>developer&apos;s eye<span className="admin-accent">.</span><small>ADMIN WORKSPACE</small></span></Link>
      <div className="admin-workspace-label"><span className="admin-workspace-icon">DE</span><span>Developer&apos;s Eye<small>Personal workspace</small></span><ShieldCheck size={15} /></div>
      <div className="admin-nav-label">OBSERVE</div>
      <nav className="admin-nav" aria-label="Administration"><Link href="/admin/crawler" className="active" aria-current="page"><Radar size={17} /> Crawler <span className="admin-nav-dot" /></Link></nav>
      <div className="admin-sidebar-bottom"><div className="admin-sidebar-note"><span className="admin-kicker">BUILT TO DISCOVER</span><p>The web moves.<br />Keep your eye on it.</p><div className="admin-note-lines" aria-hidden="true" /></div>
        <Link href="/" className="admin-sidebar-link"><ArrowUpRight size={15} /> Open search</Link><Link href="/docs" className="admin-sidebar-link"><BookOpen size={15} /> Documentation</Link>
        <div className="admin-profile"><span className="admin-avatar"><Github size={19} /></span><span><strong>{user.name || user.login}</strong><small>@{user.login}</small></span><form action="/api/auth/logout" method="post"><button aria-label="Sign out" title="Sign out"><LogOut size={17} /></button></form></div>
      </div>
    </aside>
    <div className="admin-content">{children}</div>
  </div>;
}
