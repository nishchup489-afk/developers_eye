# Developer’s Eye — API and backend connector reference

## Implementation status

This document describes the repository as inspected on October 5, 2026.

- `backend/` is a FastAPI app. `GET /search` is implemented (October 30, 2026) over the PostgreSQL full-text index, and `GET /search/suggest` (spelling suggestions, wired to the UI on November 7, 2026) and `GET /health` exist too; the other public routes below are still proposals.
- **Implemented:** Next.js `GET /api/search` and `GET /api/search/suggest`, frontend runtime validation, curated demo search, browser-local saved results, and `/docs`.
- **Not implemented:** every FastAPI route and external connector below. Their contracts are proposals based on README.md and system_design.md. They are a backend implementation handoff, not claims that those services exist.
- No backend files were changed to implement the frontend.

## 1. Connection and configuration

```text
Browser → same-origin Next.js /api/search → FastAPI /search
                                         → index / provider connectors
```

From `frontend/`, run `npm install` and `npm run dev`. The site opens at http://localhost:3000. Without configuration, searches run against a small curated dataset in `lib/demo.ts`; every response and the UI identify demo mode. There is no third-party network retrieval in demo mode. Demo ranking uses query-term matches followed by fixed fixture scores, not BM25.

To connect a future backend, create `frontend/.env.local`:

```dotenv
BACKEND_URL=http://127.0.0.1:8000
```

Restart Next.js after changing configuration. Use a backend URL reachable from the Next.js server; in containers, localhost refers to that container. A base path is allowed, e.g. `http://api:8000/v1` results in `/v1/search`. Do not include a query string or fragment in BACKEND_URL.

BACKEND_URL is server-only. No `NEXT_PUBLIC_` credential variables are needed. Because the browser calls its own origin, CORS is not required for this server-to-server connection. There is no authentication header forwarded in the current bridge. Add an explicit server credential contract before connecting an authenticated backend.

The homepage reads the configuration per request. A live-mode label means an origin is configured, not that a health check succeeded.

## 2. Implemented frontend API

### GET /api/search

| Query parameter | Type   | Required | Validation                                                                       |
| --------------- | ------ | -------- | -------------------------------------------------------------------------------- |
| q               | string | yes      | Trimmed; 1–300 characters                                                        |
| source          | enum   | no       | docs, github, stackoverflow, reddit, articles, events, practice; empty means all |

Unknown query parameters are ignored. Unsupported methods return 405 (Next.js also provides HEAD/OPTIONS behavior). No pagination, sort, autocomplete, or user-auth parameters are implemented.

```sh
curl --get 'http://localhost:3000/api/search' --data-urlencode 'q=fastapi async'
curl --get 'http://localhost:3000/api/search' --data-urlencode 'q=python' --data-urlencode 'source=docs'
```

Response, HTTP 200:

```json
{
  "query": "fastapi async",
  "results": [
    {
      "title": "Concurrency and async / await",
      "source": "docs",
      "url": "https://fastapi.tiangolo.com/async/",
      "snippet": "Learn when to use async def in FastAPI.",
      "score": 14.82,
      "tags": ["python", "fastapi", "async"]
    }
  ],
  "took_ms": 84,
  "mode": "demo"
}
```

`took_ms` measures elapsed processing at the Next.js bridge, including upstream time in live mode. `mode` is `demo` or `live` and is always controlled by the bridge. An empty result set is a successful 200. All bridge responses use `Cache-Control: no-store`.

Errors:

| HTTP | Condition                                   | Body                                                                  |
| ---- | ------------------------------------------- | --------------------------------------------------------------------- |
| 400  | Missing, whitespace-only, or oversized q    | `{ "error": "Enter a query between 1 and 300 characters." }`          |
| 400  | Unknown source                              | `{ "error": "Unknown source filter." }`                               |
| 502  | Upstream non-2xx status                     | `{ "error": "The search service is unavailable. Please try again." }` |
| 502  | Schema-invalid payload                      | `{ "error": "The search service returned an invalid response." }`     |
| 502  | Network/configuration error or invalid JSON | `{ "error": "Cannot reach the search service. Please try again." }`   |
| 504  | Upstream timeout                            | `{ "error": "Search timed out. Please try again." }`                  |

Upstream requests have a 10-second deadline, `Accept: application/json`, no cache, and no automatic retries. Provider errors or credentials are not forwarded to clients. A configured but broken backend never falls back to fixtures.

### GET /api/search/suggest

"Did you mean" for the results page. Forwards `q` to FastAPI `GET /search/suggest` and returns the corrected query, or `suggestion: null` when there is nothing to suggest. It never changes what `/api/search` returns.

| Query parameter | Type   | Required | Validation                |
| --------------- | ------ | -------- | ------------------------- |
| q               | string | yes      | Trimmed; 1–300 characters |

```sh
curl --get 'http://localhost:3000/api/search/suggest' --data-urlencode 'q=fastapi configuraton'
```

Response, HTTP 200:

```json
{
  "query": "fastapi configuraton",
  "suggestion": "fastapi configuration",
  "corrections": [{ "original": "configuraton", "replacement": "configuration" }],
  "mode": "live"
}
```

- Demo mode (no `BACKEND_URL`), pasted code (multi-line), queries over 256 characters and queries the backend rejects (422) return 200 with `suggestion: null`.
- A suggestion equal to the query (ignoring case and spacing), or one with no corrections, becomes `suggestion: null`.
- 400 for a missing, blank or over 300 character `q`; 502 for an upstream non-2xx status, a malformed payload or an unreachable backend; 504 after the 5-second deadline. All responses use `Cache-Control: no-store`.

### Result schema

| Field   | Type              | Required | Contract                                                     |
| ------- | ----------------- | -------- | ------------------------------------------------------------ |
| title   | string            | yes      | Plain text                                                   |
| source  | source enum above | yes      | Normalized category, not provider-specific identifier        |
| url     | string            | yes      | Absolute, parseable HTTP(S) URL with hostname                |
| snippet | string            | yes      | Plain text, rendered as text rather than HTML                |
| score   | finite number     | yes      | Backend relevance score; frontend preserves backend ordering |
| tags    | string[]          | no       | Display labels                                               |

Additional result fields are accepted but not used. The bridge rejects the entire response if any result fails validation. Backend `source: "fastapi_docs"` from early design examples must become `source: "docs"`; keep the original source identifier in a separate optional field if useful. Document types such as issue, repository, and discussion should likewise be separate fields.

### Browser integration

- `components/search-experience.tsx` fetches `/api/search` only when a form, suggested query, or source card is activated.
- UI tabs filter the returned collection locally; they do not trigger provider requests. Direct API callers may use the server `source` parameter.
- The Discussions tab groups `stackoverflow` and `reddit`. It is a frontend vertical, not an additional API enum value; direct API callers still use the individual provider categories. Cards reuse the entered query, or a sample query when the input is blank.
- Queries are shareable as `/?q=fastapi%20async#results`. Loading that URL runs the search; browser back/forward restores query state. Filters and saved view are local UI state, not encoded in the URL.
- New searches abort obsolete browser fetches. Server upstream requests remain bounded by their own deadline.
- Saved results live in localStorage under `developers-eye-saved`. They are validated on load and can be removed with the same bookmark button. They are local to the browser, not synced to an account. Storage failure falls back to the session with a visible notice.
- The "Try" chips on the home page are static examples. On the results page, when a plain single-line query returns fewer than 3 results, the page calls `/api/search/suggest` in the background and, if there is a suggestion, shows "Did you mean …" with the corrected words in bold. Clicking it runs that search; the original search is never rewritten.
- Keyboard shortcuts: `/`, Ctrl+K, and Cmd+K focus search. GSAP motion respects `prefers-reduced-motion`.

## 3. Proposed public FastAPI contracts — not implemented

These contracts give the backend team concrete starting points. Only `/search` is required by this frontend. Paths below are relative to BACKEND_URL. The proposals are not exposed as generic Next.js proxies.

### GET /search — implemented

Implemented in `backend/src/backend/api/search.py`. Accepts `q` (1–300 characters, 422 otherwise), optional `source` and optional `limit` (1–50, default 20). Each result also carries `type`, the raw document type. A database failure returns 503. The category comes from known hosts (GitHub/GitLab, Stack Overflow/Stack Exchange, Reddit, practice sites) and otherwise from the document type.

Original proposal: accept `q` and optional `source` using the same validation as the bridge. Return `{ "query": string, "results": SearchResult[] }`; optional `took_ms`, totals, metadata, and warnings may be added. The current bridge ignores backend top-level extras and supplies its own timing/mode. Respect the source filter when provided. Return results in relevance order and use the normalized schema above. Deduplicate canonical URLs before returning.

```json
{
  "query": "python",
  "results": [],
  "warnings": [{ "source": "reddit", "code": "timeout" }]
}
```

Proposed backend status codes: 200 for success (including partial results), 400/422 for invalid input, 429 for rate limits, 503 if no retrieval path is available. The current bridge maps all upstream non-2xx statuses to 502, so exposing a distinct 429 or partial-source UI requires a coordinated frontend change.

### GET /search/suggest — implemented

Implemented in `backend/src/backend/api/search.py` (`suggest_query_correction` in `backend/search/retrieval/fuzzy/correction.py`). Input: `q` (normalized by the query analyzer; 422 if invalid). Response, the `QueryCorrection` schema:

```json
{
  "original_query": "fastapi configuraton",
  "suggested_query": "fastapi configuration",
  "corrections": [
    { "original": "configuraton", "replacement": "configuration", "similarity": 0.53, "edit_distance": 1 }
  ]
}
```

- Candidates come from the indexer-maintained `search_terms` vocabulary with `pg_trgm` (similarity threshold 0.2), then must be within edit distance 1 (words up to 6 letters) or 2 (longer).
- Only plain 4–32 letter words are corrected. Quoted words, identifiers such as `AsyncSession` or `fastapi.utils`, `and`/`or`/`not`, and words already in the vocabulary (or whose English stem is) are kept.
- The vocabulary holds English stems (`configur`, `librari`). Each candidate is expanded into readable forms (stem plus common suffixes, `i` back to `y`), and a form is kept only if PostgreSQL's `english_stem` reduces it to that candidate. The closest form wins, so `configuraton` suggests `configuration`, not `configur`. A bare stem ending in `i` is never suggested.
- 503 if the vocabulary query fails. `/search` never applies the suggestion by itself.

Autocomplete (query completions while typing) is a separate idea and is not implemented.

### GET /sources

Input: optional `category` source enum. Return registry information without credentials.

```json
{
  "sources": [
    {
      "id": "fastapi_docs",
      "category": "docs",
      "name": "FastAPI documentation",
      "acquisition": "crawler",
      "status": "available",
      "last_indexed_at": "2026-10-05T16:00:00Z"
    }
  ]
}
```

Status enum proposal: `available`, `degraded`, `disabled`. `last_indexed_at` is an ISO-8601 UTC timestamp or null. 200 / 422.

### GET /documents/{id}

Input: stable document ID in the path. Return normalized detail:

```json
{
  "id": "doc_123",
  "title": "Concurrency and async / await",
  "source": "docs",
  "source_id": "fastapi_docs",
  "type": "documentation",
  "url": "https://fastapi.tiangolo.com/async/",
  "content": "Plain-text document content.",
  "author": null,
  "tags": ["python"],
  "created_at": null,
  "indexed_at": "2026-10-05T16:00:00Z"
}
```

200, 404 when missing, 422 for malformed IDs. Do not expose unsanitized provider HTML. Current result cards navigate directly to original URLs.

### GET /related

Input: required `document_id`, optional `limit` integer (default 5, 1–20).

```json
{ "document_id": "doc_123", "results": [] }
```

`results` uses SearchResult[]. 200 / 404 / 422. Exclude the original document and duplicates.

### GET /health — implemented as liveness

Implemented in `backend/src/backend/main.py`: `GET /health` returns `{ "status": "ok", "service": ... }` and `GET /health/db` also runs a query against the database. The richer readiness response below is still a proposal.

No input. Proposed readiness response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": { "database": "ok", "index": "ok", "redis": "optional" }
}
```

Return 200 when essential retrieval dependencies are ready, 503 otherwise. No tokens, internal hostnames, or stack traces. Consider a separate liveness route later. The frontend does not health-poll.

## 4. Proposed internal/admin API — not implemented

These operations must be authorized inside the backend before exposure. The search frontend neither calls nor proxies them. Authentication and roles have not been implemented; a possible contract is an admin bearer token validated by FastAPI. Examples intentionally contain no credentials.

Common proposed errors: 401 unauthenticated, 403 unauthorized, 404 missing resource, 409 conflict, 422 validation failure, 429 rate limit, 503 unavailable. Suggested error envelope: `{ "error": { "code": "invalid_input", "message": "...", "request_id": "..." } }`. This differs from the implemented browser bridge’s simple error envelope.

### POST /crawl

```json
{
  "source_id": "fastapi_docs",
  "seed_urls": ["https://fastapi.tiangolo.com/"],
  "max_depth": 2,
  "max_pages": 100
}
```

Require a registered source, allowlisted origin, nonempty URL list, nonnegative depth, and bounded page count. Proposed response: 202 `{ "job_id": "crawl_123", "status": "queued" }`. Respect robots rules; block private-network destinations, redirect escapes, and unsupported schemes. Crawl idempotency/deduplication belongs in the scheduler.

### POST /sources

```json
{
  "id": "fastapi_docs",
  "name": "FastAPI documentation",
  "category": "docs",
  "acquisition": "crawler",
  "base_url": "https://fastapi.tiangolo.com/",
  "recrawl_interval_hours": 48,
  "enabled": true
}
```

`acquisition`: `crawler`, `api`, or `feed`. Validate IDs, category, URL policy, and positive recrawl interval. Proposed response 201 with the created source, 409 for duplicate ID. Store credentials separately by secret reference; do not accept raw tokens into the public registry response.

### GET /crawl/jobs

Optional `status` (queued/running/completed/failed), `source_id`, `cursor`, `limit` (default 20, 1–100).

```json
{
  "jobs": [
    {
      "id": "crawl_123",
      "source_id": "fastapi_docs",
      "status": "running",
      "pages_fetched": 12,
      "pages_indexed": 10,
      "created_at": "2026-10-05T16:00:00Z",
      "error": null
    }
  ],
  "next_cursor": null
}
```

200; cursor is opaque. Redact provider error details and secrets.

### POST /reindex

```json
{ "source_id": "fastapi_docs", "mode": "incremental" }
```

Optional source_id; mode is incremental or full. Proposed response 202 `{ "job_id": "index_123", "status": "queued" }`. Full reindex must keep the serving index usable until the replacement is ready. Duplicate/incompatible active jobs may return 409. No UI triggers this operation.

### GET /metrics

Internal authenticated/scrape-network-only endpoint. No query parameters. Proposed 200 response uses Prometheus text exposition (`text/plain; version=0.0.4`). Suggested counters/histograms:

```text
# TYPE developers_eye_search_requests_total counter
developers_eye_search_requests_total{status="success"} 42
# TYPE developers_eye_documents_indexed_total counter
developers_eye_documents_indexed_total{source="docs"} 1200
```

Additional metrics: search/crawl duration, queue depth, cache hits, connector failures, and quota remaining. Do not use raw user queries or full URLs as metric labels.

## 5. Proposed provider connectors — not implemented

Every connector executes in the backend. No provider token, scraping logic, or paid integration is included in this frontend. Provider-specific authentication, terms, quotas, and API availability must be checked against current official documentation when implementing.

| Connector           | Acquisition                             | Normalized source | Normalization and backend responsibilities                                                                                    |
| ------------------- | --------------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Official docs       | Allowlisted crawler                     | docs              | Extract title/body/canonical URL; remove navigation; preserve version; obey robots and recrawl policy                         |
| GitHub              | Backend API client / ingestion          | github            | Repositories, issues, discussions; preserve type, repo, author, dates; use server credentials; deduplicate repo/issue URLs    |
| Reddit              | Authorized backend API client           | reddit            | Normalize post title/body/permalink/subreddit; treat comments separately; keep authorization and quota management server-side |
| Stack Exchange      | Backend API client                      | stackoverflow     | Normalize question title/body/link/tags; preserve accepted-answer and score metadata; decode entities and remove HTML         |
| DEV Community       | Backend API ingestion                   | articles          | Normalize article title/description/canonical URL/tags; deduplicate mirrors by canonical URL/content hash                     |
| Engineering blogs   | Allowlisted crawler/feed                | articles          | Extract main text, author, date, canonical URL; sanitize and obey source policies                                             |
| Events / Luma       | Permitted API/feed or curated ingestion | events            | Normalize title/description/URL and separate start/end/timezone/location metadata; exclude expired events in event search     |
| LeetCode / practice | Curated/permitted ingestion             | practice          | Normalize title/problem URL/topic tags/difficulty; do not assume a public API is available or scrape protected content        |

### Internal adapter interface proposal

```python
class Connector:
    async def search(self, query: str, limit: int) -> list[NormalizedDocument]: ...
    async def health(self) -> ConnectorStatus: ...
```

`NormalizedDocument` carries stable ID, canonical URL, source category, provider source ID, type, title, plain-text content, snippet, author, tags, timestamps, and optional quality signals. The orchestrator—not the browser—merges candidates, deduplicates, assigns comparable relevance scores, and projects them into SearchResult.

Suggested sequence: classify intent → choose sources → consult cache/local index → bounded parallel connector calls → normalize → deduplicate → BM25/quality ranking → source diversity → snippets → response.

Each connector needs its own timeout shorter than the bridge’s 10 seconds, bounded concurrency, quota accounting, cache strategy, and backoff. A provider failure should leave other results available where possible. Never label a source as healthy just because configuration exists. Provider warnings currently cannot be shown individually by this UI; extend SearchResponse and its validation together if needed.

## 6. Integration checklist

1. Implement FastAPI GET /search with the normalized result schema.
2. Add a test for each supported source, including docs source-ID normalization.
3. Test empty results, Unicode queries, malicious/invalid result URLs, malformed payloads, and duplicate URLs.
4. Set BACKEND_URL on the Next.js server and restart; confirm response mode is live.
5. Confirm failure and timeout states; verify there is no fallback to demo fixtures.
6. Verify partial provider failures do not crash unified search.
7. Keep all credentials in backend/server secret storage. Decide auth and rate limiting before public deployment; neither is implemented by the current bridge.
8. Run `npm run build`, `npm run lint`, and `npm run test:integration` in frontend.

The integration test uses an isolated mock upstream to exercise bridge contracts. It does not claim real FastAPI/provider integration is verified.

## 7. Relevant frontend files

- `app/api/search/route.ts`: demo/live bridge, validation, timeout and errors.
- `app/api/search/suggest/route.ts`: "Did you mean" bridge to FastAPI `/search/suggest`.
- `lib/search.ts`: public types, source enum, runtime result and suggestion validation.
- `lib/demo.ts`: curated fixtures and local demo matching.
- `components/search-experience.tsx`: search state, abort handling, bookmarks, GSAP.
- `app/globals.css`: responsive design and reduced-motion rules.
- `app/docs/page.tsx`: browser-readable API overview.
- `public/api-reference.md`: this complete handoff document.
- `.env.example`: connection setup.
