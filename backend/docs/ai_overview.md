# AI overview: setup, API and verification

FastAPI owns this feature. Next.js renders the card and forwards requests; it never holds the Groq key or generates answers. The feature overview and design rationale are in [tech docs](../../0_tech_docs/backend/ai-overview/overview.md).

## Enable locally

1. Apply backend migrations: from `backend/`, run `poetry run alembic upgrade head`. Revision `f6b2d8a4c901` adds `ai_overview_budget` and `ai_overview_cache`; existing search/crawler tables are unchanged.
2. Put `GROQ_API_KEY=...` in **`backend/.env`**, which `core/config.py` loads. The API uses `GROQ_MODEL=qwen/qwen3.8-27b` by default. Set `AI_OVERVIEW=false` to disable it. Never put this key in frontend environment files. Reasoning is disabled for the default short-answer model. The former Llama default was [retired for free/developer accounts](https://console.groq.com/docs/deprecations); verify availability before changing models.
3. Restart FastAPI. Keep `BACKEND_URL=http://127.0.0.1:8000` in the frontend configuration and search normally. No extra frontend feature flag is required.

Without a backend key, search omits `overview_token` and no provider call occurs. If the overview tables or database are unavailable, overview returns 503 and does not call Groq. Ordinary search does not access the overview tables.

For the Oracle/Vercel topology, put provider settings in `deploy/.env`, run the
migration service and rebuild/recreate the API. Vercel receives only its backend
origin and edge credential, never the Groq key. The supplied profile has one API
process; quota/cache state remains PostgreSQL-backed if it is later scaled.
See [deployment setup](../../deploy/README.md).

## Request flow

```text
Browser -> Next search proxy -> FastAPI GET /search -> existing index results
                                      |
                                      +-> signed overview_token (no Groq call)

Browser -> Next overview proxy -> FastAPI POST /search/overview
                                      |
                                      +-> verify evidence -> shared PostgreSQL claim
                                      +-> Groq -> validate citations -> shared cache
Browser <- cited plain-text overview <-+
```

`GET /search` signs up to four unique result excerpts, a query and a ten-minute expiration. The signature uses a domain-separated HMAC derived from the backend Groq key; rotation invalidates old tokens. Tokens are signed, not encrypted, and contain only the result excerpts already returned to the browser. The Next search proxy renames `overview_token` to its existing UI field `overviewToken`. No second search, external page fetch, or model browsing is performed.

`POST /search/overview` accepts only JSON `{ "token": "..." }`. FastAPI enforces a 25,000-byte body limit, a 24,000-character token limit, signature/expiry checks and the evidence schema. Arbitrary query/results payloads and unknown fields are rejected. Model inputs contain source IDs, categories, titles and snippets; citation URLs come from the verified snapshot, never model output.

Successful response:

```json
{
  "overview": {
    "paragraphs": [{ "text": "Answer supported by the excerpt.", "sources": [1] }],
    "sources": [{ "id": 1, "title": "Documentation", "url": "https://example.com/docs", "snippet": "Evidence.", "kind": "docs" }]
  }
}
```

Disabled/insufficient-evidence responses are `{ "overview": null }`. Errors contain `error`, with `overview: null` for service/provider failures. All responses are `Cache-Control: no-store`.

| Status | Meaning |
| --- | --- |
| 400 | Invalid, tampered, expired or schema-invalid evidence |
| 403 | Browser fetch metadata identifies a cross-site request |
| 413 / 415 | Oversized body / unsupported content type |
| 429 | Application reservation denied or Groq throttled; `Retry-After` is seconds |
| 502 | Provider failure, malformed/truncated output or invalid citation |
| 503 | PostgreSQL state/lock unavailable; fail closed before a new provider call |
| 504 | Provider or service deadline exceeded |

## Prompt and output policy

The complete system prompt lives in `backend/ai_overview/prompt.py`. It requires evidence-only answers, treats queries/excerpts as untrusted data, forbids following embedded instructions, preserves uncertainty/version qualifiers, requires citations for factual claims and declines an overview when excerpts cannot support one. The model is asked for at most three paragraphs and 150 words. Backend validation enforces three paragraphs, 700 characters per paragraph, strict numeric citation IDs and at least one valid citation per paragraph. Prompting and valid IDs cannot establish that a claim is true; the UI keeps its source-checking notice.

Groq transport uses a fixed HTTPS endpoint, disables redirects/retries, limits response reads to 64 KiB and reserves the full 600-token output cap. The provider deadline is 12 seconds, the service deadline is 16 seconds, and the Next proxy deadline is 18 seconds. Provider diagnostics and credentials are never returned to the browser. Python's standard-library HTTP call runs off the event loop under the deadline.

## Shared rate limits and cache

| Scope | Sliding limit |
| --- | --- |
| All API workers using this database | 20 generations/minute and 800/day |
| All API workers using this database | 5,000 reserved tokens/minute and 160,000/day |
| Client identity | 3 generations/minute and 30/day |

The backend locks one `ai_overview_budget` row in a short transaction, reads the database clock, checks the cache/lease and atomically reserves usage before a new Groq call. Conservative token accounting uses UTF-8 bytes for text input, message overhead and the full output cap. Large snippets are shortened; if the prompt still cannot fit, the backend abstains. Failed and interrupted generations keep their reservations. No database transaction spans a provider call.

`ai_overview_cache` stores the outcome and a 30-second generation lease with an ownership token. Concurrent workers wait for the owner's result instead of reserving another call. A crashed owner's lease expires; an old owner cannot overwrite its replacement's result. Waiters remain bounded by the service deadline. Success caches for 30 minutes, insufficient evidence for five minutes, and errors for five seconds. Keys include the query, source URLs/excerpts, model and complete prompt; expiration of the signed token is excluded from the cache key. New reservations prune expired entries and retain at most 500 completed entries plus active leases. Cache hits/waiters do not reserve generation usage.

Groq `Retry-After` is parsed as seconds or an HTTP date; a missing/invalid value defaults to 60 seconds. The backend persists a shared cooldown when Groq returns 429. Application quotas, cooldowns and cache survive API restarts because PostgreSQL owns them. These limits protect calls through this app; another application sharing the Groq organization can still consume its quota. Check the [actual organization limits](https://console.groq.com/docs/rate-limits), especially when changing models.

With `EDGE_SHARED_SECRET`, authenticated middleware validates the single
`X-Eye-Client-IP` derived by Next from Vercel platform headers and supplies the
request client identity. Raw caller headers cannot override it; Compose leaves
`AI_OVERVIEW_CLIENT_IP_HEADER` empty and disables Uvicorn proxy-header trust.
Without an edge credential, local deployments use the connection IP or an
explicitly configured trusted legacy header. PostgreSQL stores a SHA-256 client
hash, not the raw address. Only Caddy publishes ports in the Oracle profile.

## Verification

From the repository root, with the backend environment installed:

```powershell
$env:PYTHONPATH = (Resolve-Path backend/src).Path
crawler/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_ai_overview.py backend/tests/api/test_ai_overview.py -q
```

The existing crawler environment may be replaced with your backend Poetry interpreter. These tests mock the provider/state boundary and do not need a database or real key.

For actual PostgreSQL locking/migration tests, set `TEST_DATABASE_URL`, or explicitly opt into the configured local database:

```powershell
$env:OVERVIEW_TEST_USE_LOCAL_DB = '1'
crawler/.venv/Scripts/python.exe -m pytest backend/tests/integration/test_ai_overview.py -q
```

Integration tests create only the two overview tables inside a randomly named `ai_overview_test_<uuid>` schema, run concurrent independent stores and remove that schema afterward. They do not migrate the application's public schema or call Groq. Frontend proxy tests remain `npm run test:overview:routes` after a production build. Live provider quality/availability must be checked separately with a configured backend key.

Implementation smoke check (2026-11-08): the running backend and Next proxy returned HTTP 200 for a live overview of an existing `python` search, with one validated paragraph and three cited sources. The backend migration was applied locally and the configured key moved out of the frontend environment. This confirms one local flow; it does not establish general answer quality or production throughput.
