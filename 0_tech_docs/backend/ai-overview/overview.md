# Backend-owned AI search overview

Area: backend · Status: active

## Purpose

Generate a short, cited overview of the search results already retrieved by Developer's Eye. FastAPI owns evidence signing/verification, the system prompt, the Groq key and transport, output validation, shared request/token limits, cooldowns, cache and generation leases. The frontend owns presentation and same-origin transport only. The model never fetches pages or performs another search.

## Code

- [`backend/src/backend/api/ai_overview.py`](../../../backend/src/backend/api/ai_overview.py) — public `POST /search/overview` and request boundaries.
- [`backend/src/backend/api/search.py`](../../../backend/src/backend/api/search.py) — signs existing results without waiting for generation.
- [`backend/src/backend/ai_overview/`](../../../backend/src/backend/ai_overview/) — evidence, prompt, transport, pure quota policy and orchestration.
- [`backend/src/backend/schema/ai_overview.py`](../../../backend/src/backend/schema/ai_overview.py) — evidence and cited answer schemas.
- [`backend/src/backend/models/ai_overview.py`](../../../backend/src/backend/models/ai_overview.py) — persistent shared state.
- [`backend/alembic/versions/f6b2d8a4c901_ai_overview_state.py`](../../../backend/alembic/versions/f6b2d8a4c901_ai_overview_state.py) — additive state-table migration.
- [`frontend/components/ai-overview.tsx`](../../../frontend/components/ai-overview.tsx) — display, cancellation and manual retry UI.
- [`frontend/app/api/search/overview/route.ts`](../../../frontend/app/api/search/overview/route.ts) — transport-only FastAPI proxy.

## How-it-works docs

Admin sidebar: `/admin/ai-usage` displays shared minute/day reserved tokens, generation request limits, the configured model and provider cooldown. The authenticated backend report is `GET /admin/system/ai-usage`. These values are conservative reservations including failed calls, not actual provider token consumption or billing.

- [Setup, HTTP contract, budgets, leases and verification](../../../backend/docs/ai_overview.md).
- [Backend environment example](../../../backend/.env.example).
- [Deployment configuration](../../../deploy/docker-compose.yml).

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0049](ADR-0049-backend-owned-overviews-with-shared-postgres-budgets.md) | decision | Own AI overviews in FastAPI with shared PostgreSQL budgets | accepted |
| [ADR-0048](../../frontend/search-experience/ADR-0048-ground-ai-overviews-in-signed-results.md) | decision | Ground AI overviews in signed search results with bounded Groq usage | superseded |

## Decisions to record

The ownership and persistent quota/cache choices are recorded in ADR-0049. Future changes to model/token accounting, public access policy or shared-state scope require an explicit successor decision and verification evidence. No production performance or answer-quality claim is established by local tests.

## Rules for future changes

- Keep the Groq key, prompt, signing, validation and all generation policy in the backend; frontend changes are limited to presentation and transport.
- Issue evidence from existing results; never accept unsigned client snippets, follow model-generated URLs or rerun retrieval for an overview.
- Reserve shared usage before provider I/O and retain reservations for failed/interrupted calls. Never replace PostgreSQL coordination with process-local limits.
- Do not hold database transactions open during provider I/O. Preserve lease ownership checks and bounded waiters.
- Missing state storage fails closed for AI generation without breaking ordinary search.
- Render model text as plain text and resolve citation URLs only from validated evidence.
- Trust client identity headers only when the ingress overwrites them and direct untrusted access is blocked.
- Keep backend overview unit/API/PostgreSQL tests and frontend proxy/search integration tests passing.
