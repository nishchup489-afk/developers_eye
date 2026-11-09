"use client";
import { useState } from "react";
import { usePolling } from "./crawler-control-center";
type Usage = {model: string; accounting: string; cooldown_seconds: number; windows: {name: string; requests: number; request_limit: number; reserved_tokens: number; token_limit: number}[]};
function valid(value: unknown): value is Usage { return !!value && typeof value === "object" && Array.isArray((value as Usage).windows); }
export default function AIUsage() {
  const [refresh, setRefresh] = useState(0);
  const report = usePolling("/api/admin/system/ai-usage", valid, 15000, true, refresh);
  return <main className="admin-main cc-main" id="main-content"><div className="admin-page-heading"><div><div className="admin-kicker">AI OVERVIEW</div><h1>AI token usage</h1><p>Shared usage across all backend workers. Refreshes every 15 seconds.</p></div><button className="admin-button secondary" onClick={() => setRefresh(v => v + 1)}>Refresh</button></div>{report.error && <div role="alert" className="admin-alert">{report.error}</div>}{!report.data && !report.error && <p role="status">Loading AI usage…</p>}{report.data && <><p>Model: {report.data.model}</p><p className="cc-note">{report.data.accounting}</p><div className="cc-metrics">{report.data.windows.map(window => <article className="admin-metric cc-metric" key={window.name}><div className="admin-metric-label">{window.name}</div><strong className="admin-metric-value">{window.reserved_tokens.toLocaleString()}</strong><span className="admin-metric-detail">Reserved tokens / {window.token_limit.toLocaleString()}</span><p>{window.requests.toLocaleString()} / {window.request_limit.toLocaleString()} generation requests</p></article>)}</div><p>Provider cooldown: {report.data.cooldown_seconds} seconds</p></>}</main>;
}
