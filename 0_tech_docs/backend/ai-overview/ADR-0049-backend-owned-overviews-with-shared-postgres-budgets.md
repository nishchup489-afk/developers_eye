---
id: ADR-0049
title: Own AI overviews in FastAPI with shared PostgreSQL budgets
status: accepted
date: '2026-11-08'
area: backend
feature: ai-overview
code:
- backend/src/backend/ai_overview/
- backend/src/backend/api/ai_overview.py
- backend/src/backend/api/search.py
- backend/src/backend/schema/ai_overview.py
- backend/src/backend/schema/search.py
- backend/src/backend/models/ai_overview.py
- backend/src/backend/core/config.py
- backend/alembic/versions/f6b2d8a4c901_ai_overview_state.py
- frontend/app/api/search/overview/route.ts
- frontend/components/ai-overview.tsx
supersedes: ADR-0048
superseded_by: null
related:
- ADR-0031
- ADR-0013
---

# ADR-0049: Own AI overviews in FastAPI with shared PostgreSQL budgets

## TL;DR

FastAPI owns the entire AI overview feature; Next.js displays it and proxies requests. PostgreSQL coordinates reservations, cooldowns, cached outcomes and generation leases across the existing two API workers and process restarts.

## Context

The user requires a backend-owned overview and a frontend limited to UI. The first implementation placed generation, signing and rate limits in Next.js (ADR-0048), whose process-local accounting did not fit multiple API workers. Search already runs in FastAPI over PostgreSQL, and its exact returned evidence should support an independently generated overview without another retrieval.

## Decision

`GET /search` optionally emits a ten-minute HMAC-signed `overview_token` for up to four existing result excerpts. FastAPI `POST /search/overview` validates body size, token integrity/expiry and evidence types. It prepares a bounded evidence-only prompt, calls Groq's fixed HTTPS chat-completions endpoint, validates strict JSON paragraphs and citation IDs, and returns only cited plain text with URLs resolved from the verified evidence. Invalid/truncated output fails closed; insufficient evidence returns no overview. The full policy and schema limits are documented in backend/docs/ai_overview.md.

The backend uses PostgreSQL `ai_overview_budget` and `ai_overview_cache`. A short transaction serializes the shared budget row, uses database time, checks cache/lease state, and atomically reserves usage before granting a 30-second generation lease. Transactions never span provider calls. Lease owners alone can publish the result; expired leases are recoverable. Other API workers wait for that outcome within the 16-second service deadline.

Use conservative limits for the current Qwen model: 20 requests/5,000 reserved tokens per minute and 800 requests/160,000 tokens per day globally, plus three generations/minute and 30/day per client. Reserve UTF-8 input bytes, message overhead and the full 600-token output cap; failed/interrupted calls remain counted. Cache success for 30 minutes, insufficient evidence for five minutes and errors for five seconds. Groq 429 responses persist a shared Retry-After cooldown. Never automatically retry provider calls. The provider deadline is 12 seconds and response reads are capped at 64 KiB. Prompt/evidence/model changes invalidate cache keys.

Default to `qwen/qwen3.8-27b` with `reasoning_effort=none`; the former Llama default is retired for free/developer usage. Identify HTTP requests as `developers-eye/0.1` because the default Python client identifier is rejected by the provider gateway. Store Groq configuration only in the backend. Compose exposes an explicit UI environment allowlist to Next.js, preserving the ingress-overwritten client-IP header through its transport proxy. Without a trusted header, FastAPI uses the connecting peer's IP. No Redis or new external service is introduced. Revision `f6b2d8a4c901` adds only the two overview tables.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| FastAPI ownership with PostgreSQL state | Clear ownership; shared durable quotas; existing infrastructure | Additional short transactions and a schema migration | chosen |
| Keep generation and process-local state in Next.js | Already implemented | Violates requested ownership; quotas multiply across processes/restarts | rejected; supersedes ADR-0048 |
| Move generation to FastAPI with process-local counters | Small port | Existing two API workers can each spend the budget | rejected |
| Add Redis coordination | Suitable atomic shared state | Adds a service for a deliberately low-volume free-tier feature | deferred until measured PostgreSQL contention warrants it |
| Generate inside the search response | One client request | Provider latency/failure delays otherwise successful search | rejected |

## Why

Backend ownership keeps provider policy beside retrieval and preserves a simple display contract. PostgreSQL is already required, and free-tier generation volume is small enough for a single short-held budget row. Shared leases avoid duplicate quota spending when successive requests reach different workers. This is an implementation choice backed by local correctness tests, not a production throughput benchmark.

## Consequences

- Gained: backend-only generation policy and credentials; shared quotas/cache/cooldowns survive worker and API restarts; ordinary search does not touch the overview tables.
- Accepted limitations: snippets may be insufficient; valid citations do not prove factual support; conservative byte accounting underuses some available quota; other applications sharing the Groq organization remain outside this database's accounting.
- Dependencies: apply the additive migration before enabling; preserve the ingress trust boundary; frontend and backend must evolve their display schema together.

## Invariants

- Frontend contains no Groq key handling, system prompt, evidence signing, generation cache or quota policy.
- Only backend-signed existing results reach the model; no second search or page fetch occurs.
- Every published paragraph has valid citations; URLs always come from verified evidence.
- Shared usage is reserved before network I/O and never refunded after a failed or interrupted call.
- A stale lease owner cannot overwrite a newer generation.
- Database or provider failures affect the optional overview, not completed search results.

## Failure modes

- Missing key/disabled feature: omit the search token and perform no provider work.
- Missing migration, unavailable PostgreSQL or lock timeout: return 503 and never bypass shared reservations.
- Worker crash/cancellation: keep its usage reservation; allow lease recovery after 30 seconds.
- Groq quota exhaustion: persist the cooldown, return Retry-After, and keep sources visible.
- Malformed JSON, unknown citations, provider diagnostics or truncated output: return a generic failure without exposing credentials or diagnostics.

## Evidence

- Backend unit/API tests validate signatures, expiration, safe URLs, bounded evidence, strict citations, byte budgets, client/global sliding windows, transport failures and endpoint behavior using a mocked provider.
- PostgreSQL integration tests execute the actual additive migration in disposable schemas and confirm concurrent independent workers share one lease/reservation, restart-persistent cache/limits, durable cooldown, stale-owner protection, failed-call accounting and cache pruning.
- Frontend compiled-route tests confirm FastAPI-only transport and token/status/Retry-After passthrough. The production build, lint and existing search integration checks passed.
- Local verification on 2026-11-08: 67 backend overview/search/telemetry/lifespan tests passed, including real PostgreSQL coordination in disposable schemas. A live `python` search returned 20 existing results; the backend generated one validated paragraph with three cited sources. The running FastAPI endpoint and the running Next UI proxy both returned HTTP 200 with those citations. This is a single smoke check, not a production quality or performance benchmark.
- Provider protocol: [Groq API reference](https://console.groq.com/docs/api-reference). Quota scope: [Groq organization limits](https://console.groq.com/docs/rate-limits).

## Revisit when

- Measured contention on the budget row affects search latency, generation limits/model change, multiple independent applications need one accounting scope, or a streaming product requires a different display contract.

## Rules for future changes

- Keep provider policy and credentials in FastAPI; frontend code remains presentation/transport.
- Preserve signed existing evidence, valid citations and plain-text rendering.
- Keep atomic shared reservations, durable cooldowns and lease-owner checks; never hold transactions over provider I/O.
- Do not silently fall back to process-local quota state when PostgreSQL is unavailable.
- Only trust ingress-overwritten client identity headers.
- Run backend overview unit/API/PostgreSQL tests and frontend proxy/search integration checks when these boundaries change.
