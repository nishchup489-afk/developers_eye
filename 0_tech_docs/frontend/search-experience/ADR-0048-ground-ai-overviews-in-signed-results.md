---
id: ADR-0048
title: Ground AI overviews in signed search results with bounded Groq usage
status: accepted
date: '2026-11-08'
area: frontend
feature: search-experience
code:
- frontend/app/api/search/route.ts
- frontend/app/api/search/overview/route.ts
- frontend/lib/ai-overview-context.ts
- frontend/lib/ai-overview-server.ts
- frontend/lib/ai-overview-limit.ts
- frontend/lib/ai-overview.ts
- frontend/components/ai-overview.tsx
supersedes: null
superseded_by: null
related:
- ADR-0031
---

# ADR-0048: Ground AI overviews in signed search results with bounded Groq usage

## TL;DR

Generate an optional Groq overview after live results arrive. Sign the existing evidence server-side, require valid paragraph citations, and reserve request/token budgets before generation to protect a free-tier account.

## Context

The results page already retrieves validated index snippets. An AI overview should use these excerpts, keep search usable during provider failures, match the existing visual design, and conserve a shared Groq quota.

## Decision

The live search bridge signs a ten-minute snapshot of up to four unique results with an HMAC derived from the server-only Groq key. A same-origin POST verifies that snapshot before calling Groq's chat-completions endpoint. The model receives the query, result IDs, titles, source categories and shortened snippets, with an evidence-only system prompt. It returns JSON paragraphs with required source IDs; invalid IDs, malformed or truncated output fail closed. An empty paragraph list means insufficient evidence. The browser renders plain text with links resolved from verified search results.

Use `llama-3.1-8b-instant` by default, a 600-token output cap and a 12-second provider timeout. Server-wide sliding budgets are 20 requests/5,000 reserved tokens per minute and 1,000 requests/400,000 tokens per day; each client gets three generations/minute and 30/day. Reserve a conservative UTF-8 byte bound plus framing/output overhead, including failed calls. Groq 429 responses pause new generations for Retry-After. Cache success for 30 minutes and insufficient evidence for five minutes; coalesce identical inflight requests. The cache key includes query, model, prompt and exact evidence. Never automatically retry.

State is process-local, matching the current Compose web service. Budgets reset when it restarts. Before adding replicas, serverless instances or persistent organization-wide accounting, move reservations, cooldowns and cache to an atomic shared store. Client identity defaults to one anonymous bucket; only trust an explicitly configured, proxy-overwritten header. Caddy overwrites X-Eye-Client-IP.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Signed existing results, direct server-side Groq call | No duplicate retrieval; small integration; bounded evidence | Short snippets can be insufficient | chosen |
| Browser submits arbitrary snippets and URLs | Simple UI payload | Client can replace evidence and consume the key for unrelated prompts | rejected |
| Refetch search and full pages for every overview | More context | Additional latency, quota/load and URL-fetch complexity | rejected |
| Add a distributed store immediately | Shared persistent accounting | Adds infrastructure beyond the existing single web process | deferred until scaling |

## Why

The signed snapshot binds the overview to exactly what this search returned while avoiding a second index query. Conservative token reservations and caching favor predictable usage over maximum free-tier throughput.

## Consequences

- Gained: cited overviews, server-held credentials, bounded calls and independent search availability.
- Accepted limitations: prompting cannot prove factual grounding; process-local budgets are not durable or distributed; other applications sharing the Groq organization can consume quota.
- Dependencies: the browser and overview route share the paragraph/citation contract. Runtime configuration is documented in frontend/README.md.

## Invariants

- Demo and saved-result views never generate AI output.
- Model-generated URLs never become citation links.
- Only server-verified result evidence reaches the provider.
- Provider errors never replace or delay ordinary search results.
- Failed calls consume reserved budgets; provider throttling is not automatically retried.

## Evidence

- Unit tests cover evidence integrity/expiry, output validation, client/global sliding windows and cooldowns.
- Compiled-route tests mock upstream fetch and cover coalescing/cache, changed evidence, signed context, proxy origins, provider failures and throttling.
- Production build, lint and existing search integration checks passed during implementation. A local browser preview uses fixture upstreams, not a live provider. No Groq key was available for live verification.
- Provider contract: [Groq API reference](https://console.groq.com/docs/api-reference), [model capabilities](https://console.groq.com/docs/model/llama-3.1-8b-instant), [organization limits](https://console.groq.com/docs/rate-limits).

## Revisit when

- More than one web process serves generation, the app moves to serverless, the model changes, or other applications share the account budget.

## Rules for future changes

- Preserve signed evidence, valid citations and plain-text rendering.
- Move reservations to an atomic shared store before scaling web instances.
- Never enable a client-IP header without a proxy that overwrites it.
- Keep overview unit/route tests and the existing search integration suite passing.
