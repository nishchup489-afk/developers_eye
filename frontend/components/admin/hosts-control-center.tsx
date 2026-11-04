"use client";

import { useState } from "react";
import { ChevronRight, CircleAlert, Gauge, Globe2, Loader2, Network, Pause, Play, Radio, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { isHostReport, type HostFlag, type HostReport } from "@/lib/system-report";
import { Empty, Panel, usePolling } from "./crawler-control-center";
import { Tone } from "./system-control-center";

const n = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined, suffix = "") => value == null ? "N/A" : `${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const time = (value: string | null) => value ? new Date(value).toLocaleTimeString() : "Never";
const flagText: Record<HostFlag, string> = { over_rate: "over polite rate", throttled: "throttled", hot: "hot host" };

export default function HostsControlCenter() {
  const [auto, setAuto] = useState(true), [refresh, setRefresh] = useState(0), [minutes, setMinutes] = useState(60);
  const report = usePolling(`/api/admin/system/hosts?minutes=${minutes}`, isHostReport, 15000, auto, refresh);
  const r = report.data;
  return <>
    <header className="admin-topbar"><div><span>Workspace</span><ChevronRight size={13} /><strong>Hosts</strong></div><span className="admin-readonly"><ShieldCheck size={13} /> Read-only monitoring</span></header>
    <main className="admin-main cc-main" id="main-content">
      <div className="admin-page-heading"><div><div className="admin-kicker"><Network size={12} /> POLITENESS ACROSS ALL WORKERS</div><h1>Every host.<br /><span>Treated kindly</span><span className="admin-heading-dot">.</span></h1><p>Requests per host summed across every crawler process, with the throttling signals that come before a ban.</p></div></div>
      <div className="cc-control-bar"><label><span>Window</span><select value={minutes} aria-label="Host window" onChange={e => setMinutes(Number(e.target.value))}><option value={15}>Last 15 minutes</option><option value={60}>Last hour</option><option value={360}>Last 6 hours</option><option value={1440}>Last 24 hours</option></select></label><div className="cc-refresh-controls"><button className="admin-button secondary" onClick={() => setAuto(v => !v)} aria-pressed={auto}>{auto ? <Pause size={13} /> : <Play size={13} />}{auto ? "Auto-refresh · 15s" : "Refresh paused"}</button><button className="admin-icon-button" disabled={report.loading} aria-label="Refresh dashboard" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={15} className={report.loading ? "admin-spin" : ""} /></button></div></div>
      {report.error && <div className="admin-alert" role="alert"><CircleAlert size={19} /><div><strong>{r ? "Some data may be out of date" : "Host data is unavailable"}</strong><p>{report.error}</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Retry</button></div>}
      {r ? <><Cards report={r} /><HostTable report={r} /></> : !report.error && <div className="cc-empty" role="status"><Loader2 size={22} className="admin-spin" /> Loading host snapshot.</div>}
    </main>
  </>;
}

function Cards({ report: r }: { report: HostReport }) {
  const throttled = r.hosts.filter(h => h.flags.includes("throttled")).length;
  const over = r.hosts.filter(h => h.flags.includes("over_rate")).length;
  const cards = [
    { label: "Hosts crawled", value: n(r.hosts.length), note: `${n(r.total_attempts)} attempts in window`, icon: <Globe2 size={16} /> },
    { label: "Polite rate", value: metric(r.polite_requests_per_minute, "/min"), note: `Per host, per process (${r.min_interval_seconds}s gap)`, icon: <Gauge size={16} /> },
    { label: "Worst case now", value: metric(r.worst_case_requests_per_minute, "/min"), note: `${r.online_workers} worker${r.online_workers === 1 ? "" : "s"} online × polite rate`, icon: <Radio size={16} /> },
    { label: "Throttled hosts", value: n(throttled), note: "HTTP 429 or 503 in window", icon: <ShieldAlert size={16} /> },
    { label: "Over polite rate", value: n(over), note: "Last 5 minutes, all workers", icon: <ShieldAlert size={16} /> },
  ];
  return <div className="cc-metrics">{cards.map(card => <article className="admin-metric cc-metric" key={card.label}><div className="admin-metric-label">{card.label}{card.icon}</div><strong className="admin-metric-value">{card.value}</strong><span className="admin-metric-detail">{card.note}</span></article>)}</div>;
}

function HostTable({ report: r }: { report: HostReport }) {
  return <Panel title="Host pressure" eyebrow="TOP 50 HOSTS BY ATTEMPTS">
    <div className="cc-table-wrap" role="region" aria-label="Host records" tabIndex={0}><table className="cc-table" role="table"><caption>Request rate, share and error signals for each host.</caption><thead><tr><th scope="col">Host</th><th scope="col">Rate (5m)</th><th scope="col">Attempts</th><th scope="col">Share</th><th scope="col">429 / 503</th><th scope="col">4xx / 5xx</th><th scope="col">Blocked / timeouts</th><th scope="col">Mean fetch</th><th scope="col">Last</th></tr></thead>
      <tbody>{r.hosts.map(h => <tr key={h.host}><td>{h.host}<small>{h.sources} source{h.sources === 1 ? "" : "s"}</small>{h.flags.length > 0 && <span className="sys-flags">{h.flags.map(f => <Tone key={f} value={flagText[f]} status={f === "throttled" ? "critical" : "warning"} />)}</span>}</td><td data-label="Rate (5m)">{metric(h.requests_per_minute, "/min")}</td><td data-label="Attempts">{n(h.attempts)}</td><td data-label="Share">{metric(h.share_percent, "%")}</td><td data-label="429 / 503">{n(h.http_429)} / {n(h.http_503)}</td><td data-label="4xx / 5xx">{n(h.http_4xx)} / {n(h.http_5xx)}</td><td data-label="Blocked / timeouts">{n(h.blocked)} / {n(h.timeouts)}</td><td data-label="Mean fetch">{metric(h.avg_fetch_ms, " ms")}</td><td data-label="Last">{time(h.last_attempt_at)}</td></tr>)}</tbody></table></div>
    {!r.hosts.length && <Empty>No crawl attempts in this window.</Empty>}
    <p className="cc-note">Politeness is enforced inside each crawler process, so the real per-host rate can reach the polite rate times the number of workers. &quot;Over polite rate&quot; means more than one process is hitting that host. &quot;Hot host&quot; means one host takes over half of all attempts.</p>
  </Panel>;
}
