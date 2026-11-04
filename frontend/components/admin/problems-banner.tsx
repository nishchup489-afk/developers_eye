"use client";

import { useState } from "react";
import { ChevronDown, CircleAlert, Info, OctagonAlert } from "lucide-react";
import { isProblemsReport, type Severity } from "@/lib/system-report";
import { usePolling } from "./crawler-control-center";

const icons: Record<Severity, React.ReactNode> = { critical: <OctagonAlert size={16} />, warning: <CircleAlert size={16} />, info: <Info size={16} /> };

// One shared rule check for every admin page. It stays silent while everything is healthy.
export default function ProblemsBanner() {
  const [open, setOpen] = useState(false);
  const { data } = usePolling("/api/admin/system/problems", isProblemsReport, 60000, true, 0);
  if (!data || !data.problems.length) return null;
  const top: Severity = data.counts.critical ? "critical" : data.counts.warning ? "warning" : "info";
  const summary = (["critical", "warning", "info"] as Severity[]).filter(s => data.counts[s]).map(s => `${data.counts[s]} ${s}`).join(" · ");
  return <section className={`sys-problems ${top}`} aria-label="System problems">
    <button className="sys-problems-toggle" aria-expanded={open} onClick={() => setOpen(v => !v)}>
      {icons[top]}<strong>{data.problems[0].title}</strong>{data.problems.length > 1 && <span>+{data.problems.length - 1} more</span>}<small>{summary}</small><ChevronDown size={15} className={open ? "expanded" : ""} />
    </button>
    {open && <ul>{data.problems.map(p => <li key={p.id} className={p.severity}>{icons[p.severity]}<div><strong>{p.title}</strong><p>{p.detail}</p></div></li>)}</ul>}
  </section>;
}
