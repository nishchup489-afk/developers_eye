import Link from "next/link";
import { ArrowLeft, ArrowUpRight, Eye } from "lucide-react";
import CodeBlock from "@/components/code-block";
import DocsToc from "@/components/docs-toc";
export const metadata = { title: "API & connectors — Developer’s Eye" };
const routes = [
  [
    "GET",
    "/api/search",
    "Implemented in Next.js",
    "Validates queries; searches demo fixtures or forwards to FastAPI.",
  ],
  [
    "GET",
    "/search",
    "Backend contract",
    "Unified ranked search, called through /api/search.",
  ],
  [
    "GET",
    "/api/search/suggest",
    "Implemented in Next.js",
    "“Did you mean” spelling suggestion; forwards to FastAPI /search/suggest.",
  ],
  [
    "GET",
    "/search/suggest",
    "Backend contract",
    "Spelling suggestion from the indexed vocabulary; never rewrites /search.",
  ],
  ["POST", "/api/search/overview", "Implemented in Next.js", "Forwards signed evidence to backend-owned optional AI overview."],
  ["POST", "/search/overview", "Backend contract", "Validates evidence and applies shared PostgreSQL quotas/cache."],
  ["GET", "/api/admin/system/report", "Implemented · authenticated", "Protected system observability; admin access is off unless configured."],
  ["GET", "/sources", "Proposed", "Source registry and availability."],
  ["GET", "/documents/{id}", "Proposed", "Normalized document details."],
  ["GET", "/related", "Proposed", "Related documents."],
  ["GET", "/health", "Backend contract", "Liveness; /health/db checks the database."],
  ["POST", "/crawl", "Proposed · admin", "Queue a crawl."],
  ["POST", "/sources", "Proposed · admin", "Register a source."],
  ["GET", "/crawl/jobs", "Proposed · admin", "Inspect background jobs."],
  ["POST", "/reindex", "Proposed · admin", "Queue index rebuild."],
  ["GET", "/metrics", "Proposed · internal", "Operational metrics."],
];
const sections = [
  { id: "connect", title: "Connect the backend" },
  { id: "contract", title: "The search contract" },
  { id: "endpoints", title: "Endpoint inventory" },
  { id: "errors", title: "Errors and limits" },
  { id: "connectors", title: "Connector boundary" },
] as const;
const sampleResponse = JSON.stringify(
  {
    query: "fastapi async",
    results: [
      {
        title: "Concurrency and async / await",
        source: "docs",
        url: "https://fastapi.tiangolo.com/async/",
        snippet: "Learn when to use async def in FastAPI.",
        score: 14.82,
        tags: ["python", "async"],
      },
    ],
    took_ms: 84,
    mode: "demo",
  },
  null,
  2,
);
function statusTone(status: string) {
  if (status.startsWith("Implemented")) return "live";
  if (status.startsWith("Backend")) return "contract";
  return "proposed";
}

export default function Docs() {
  return (
    <div className="docs-shell">
      <header className="header shell docs-header">
        <Link className="brand" href="/" aria-label="Developer’s Eye home">
          <span className="brand-mark">
            <Eye size={24} />
          </span>
          <span>
            developer’s<span className="brand-light">eye</span>
            <span className="brand-dot">.</span>
          </span>
        </Link>
        <Link className="text-button docs-back" href="/" data-magnetic>
          <ArrowLeft size={15} /> Back to the search
        </Link>
      </header>
      <main className="docs-page shell">
        <div className="docs-hero">
          <div className="eyebrow">DEVELOPER’S EYE / ENGINEERING REFERENCE</div>
          <h1>
            Under the hood<span className="accent">.</span>
          </h1>
          <p className="docs-lede">
            A small frontend. A clear boundary. Room for a powerful search
            engine.
          </p>
        </div>
        <div className="docs-layout">
          <DocsToc sections={sections} />
          <article className="docs-article">
            <p className="docs-note">
              FastAPI serves indexed search, spelling suggestions, optional AI
              overview and authenticated admin reports. The frontend calls it
              through server-side route handlers. Rows labeled proposed are
              future interfaces and are not available services.
            </p>
            <h2 id="connect">Connect the backend</h2>
            <p>
              Leave <code>BACKEND_URL</code> unset to explore labeled demo data.
              To search the PostgreSQL index, add the FastAPI origin
              to <code>frontend/.env.local</code> and restart Next.js. This
              variable stays on the server. The Vercel deployment also needs a
              server-only <code>EDGE_SHARED_SECRET</code> matching the API ingress.
            </p>
            <CodeBlock
              title="frontend/.env.local"
              code={`BACKEND_URL=http://127.0.0.1:8000\n\nBrowser → GET /api/search?q=fastapi+async\nNext.js → GET /search?q=fastapi+async → FastAPI`}
            />
            <h2 id="contract">The search contract</h2>
            <p>
              Use a query of 1–256 normalized characters (at most 1,024 raw). The optional{" "}
              <code>source</code> filter accepts{" "}
              <code>
                docs | github | stackoverflow | reddit | articles | events |
                practice
              </code>
              . Source tabs query the server. Mode (all/text/code), page, page
              size (1–50), and language preference are passed through to FastAPI.
            </p>
            <CodeBlock
              title="GET /search · 200 response"
              code={sampleResponse}
            />
            <p>
              The bridge adds <code>mode</code> and measures{" "}
              <code>took_ms</code>. Result URLs must use HTTP or HTTPS; unknown
              source names and malformed results are rejected. A configured
              backend never silently falls back to demo data.
            </p>
            <h2 id="endpoints">Endpoint inventory</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Path</th>
                    <th>Status</th>
                    <th>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {routes.map(([method, path, status, purpose]) => (
                    <tr key={method + path}>
                      <td>
                        <span
                          className={`method method-${method.toLowerCase()}`}
                        >
                          {method}
                        </span>
                      </td>
                      <td>
                        <code>{path}</code>
                      </td>
                      <td>
                        <span className={`status status-${statusTone(status)}`}>
                          {status}
                        </span>
                      </td>
                      <td>{purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h2 id="errors">Errors and limits</h2>
            <p>
              <code>400</code> means the query or source is invalid.{" "}
              <code>502</code> means the backend is unreachable, returned an
              error, or sent an invalid payload. <code>504</code> means the
              backend deadline or six-second search-proxy timeout elapsed.
              Rate limits return <code>429</code>; overload returns <code>503</code>,
              both with Retry-After. Errors use{" "}
              <code>{'{ "error": "Human-readable message" }'}</code>. Responses
              are not cached. Search requests cancel when superseded.
            </p>
            <h2 id="connectors">Connector boundary</h2>
            <p>
              Documentation crawlers, GitHub, Reddit, Stack Exchange, DEV/blogs,
              events, and practice sources belong behind FastAPI. Normalize
              their results to the search schema before returning them. Provider
              credentials must never appear in browser code or public
              environment variables.
            </p>
            <p>
              The complete reference specifies all proposed endpoint inputs and
              outputs, connector responsibilities, normalization, failure
              handling, and integration checks.
            </p>
            <a
              className="docs-download"
              href="/api-reference.md"
              download
              data-spotlight
            >
              <span>
                <small>FULL REFERENCE · MARKDOWN</small>
                Download the complete API & connector reference
              </span>
              <ArrowUpRight size={20} />
            </a>
          </article>
        </div>
      </main>
    </div>
  );
}
