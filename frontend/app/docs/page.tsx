import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
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
    "Unified ranked search; the only backend route called by the frontend.",
  ],
  ["GET", "/search/suggestions", "Proposed", "Query completions."],
  ["GET", "/sources", "Proposed", "Source registry and availability."],
  ["GET", "/documents/{id}", "Proposed", "Normalized document details."],
  ["GET", "/related", "Proposed", "Related documents."],
  ["GET", "/health", "Proposed", "Service readiness."],
  ["POST", "/crawl", "Proposed · admin", "Queue a crawl."],
  ["POST", "/sources", "Proposed · admin", "Register a source."],
  ["GET", "/crawl/jobs", "Proposed · admin", "Inspect background jobs."],
  ["POST", "/reindex", "Proposed · admin", "Queue index rebuild."],
  ["GET", "/metrics", "Proposed · internal", "Operational metrics."],
];
export default function Docs() {
  return (
    <main className="docs-page shell">
      <Link className="text-button" href="/">
        <ArrowLeft size={15} /> Back to the search
      </Link>
      <div className="eyebrow" style={{ marginTop: 42 }}>
        DEVELOPER’S EYE / ENGINEERING REFERENCE
      </div>
      <h1>
        Under the hood<span style={{ color: "var(--lime)" }}>.</span>
      </h1>
      <p>
        A small frontend. A clear boundary. Room for a powerful search engine.
      </p>
      <p className="docs-note">
        The backend currently contains a Python package scaffold, with no
        implemented HTTP routes or third-party connectors. The frontend search
        bridge is implemented. All backend endpoints below are proposed
        contracts, not available services.
      </p>
      <h2>Connect the backend</h2>
      <p>
        Leave <code>BACKEND_URL</code> unset to explore labeled demo data. Once
        FastAPI implements <code>GET /search</code>, add its origin to{" "}
        <code>frontend/.env.local</code> and restart Next.js. This variable
        stays on the server.
      </p>
      <pre>
        <code>{`BACKEND_URL=http://127.0.0.1:8000\n\nBrowser → GET /api/search?q=fastapi+async\nNext.js → GET /search?q=fastapi+async → FastAPI`}</code>
      </pre>
      <h2>The search contract</h2>
      <p>
        Use a trimmed query of 1–300 characters. The optional{" "}
        <code>source</code> filter accepts{" "}
        <code>
          docs | github | stackoverflow | reddit | articles | events | practice
        </code>
        . UI source tabs filter the returned collection locally.
      </p>
      <pre>
        <code>
          {JSON.stringify(
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
          )}
        </code>
      </pre>
      <p>
        The bridge adds <code>mode</code> and measures <code>took_ms</code>.
        Result URLs must use HTTP or HTTPS; unknown source names and malformed
        results are rejected. A configured backend never silently falls back to
        demo data.
      </p>
      <h2>Endpoint inventory</h2>
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
                  <code>{method}</code>
                </td>
                <td>
                  <code>{path}</code>
                </td>
                <td>{status}</td>
                <td>{purpose}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2>Errors and limits</h2>
      <p>
        <code>400</code> means the query or source is invalid. <code>502</code>{" "}
        means the backend is unreachable, returned an error, or sent an invalid
        payload. <code>504</code> means the 10-second upstream timeout elapsed.
        Errors use <code>{'{ "error": "Human-readable message" }'}</code>.
        Responses are not cached. Search requests cancel when superseded.
      </p>
      <h2>Connector boundary</h2>
      <p>
        Documentation crawlers, GitHub, Reddit, Stack Exchange, DEV/blogs,
        events, and practice sources belong behind FastAPI. Normalize their
        results to the search schema before returning them. Provider credentials
        must never appear in browser code or public environment variables.
      </p>
      <p>
        The complete reference specifies all proposed endpoint inputs and
        outputs, connector responsibilities, normalization, failure handling,
        and integration checks.
      </p>
      <a className="text-button" href="/api-reference.md" download>
        Download the complete API & connector reference{" "}
        <ArrowUpRight size={15} />
      </a>
    </main>
  );
}
