"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, HardDrive, Library, Network, Radar, ScanSearch } from "lucide-react";

const links = [["/admin/crawler", "Crawler", Radar], ["/admin/indexer", "Indexer", ScanSearch], ["/admin/corpus", "Corpus", Library], ["/admin/availability", "Availability", Activity], ["/admin/hosts", "Hosts", Network], ["/admin/system", "System", HardDrive]] as const;

export default function AdminNav() {
  const pathname = usePathname();
  return <nav className="admin-nav" aria-label="Administration">{links.map(([href, label, Icon]) => {
    const active = pathname.startsWith(href);
    return <Link key={href} href={href} className={active ? "active" : undefined} aria-current={active ? "page" : undefined}><Icon size={17} /> {label} {active && <span className="admin-nav-dot" />}</Link>;
  })}</nav>;
}
