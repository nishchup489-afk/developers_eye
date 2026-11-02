---
id: ADR-0016
title: Stream bounded responses through a policy-approved single-hop transport
status: accepted
date: '2026-11-02'
area: crawler
feature: fetcher
code:
- crawler/src/crawler/fetcher/fetch.py
- crawler/src/crawler/fetcher/config.py
- crawler/src/crawler/fetcher/errors.py
- crawler/src/crawler/policy_and_politeness/policy_coordinator.py
supersedes: null
superseded_by: null
related:
- ADR-0007
- INC-0005
- INC-0010
---

# ADR-0016: Stream bounded responses through a policy-approved single-hop transport

## TL;DR

The policy coordinator approves each hop and the HTTPX transport consumes a bounded response. Typed failures let the worker distinguish unsafe requests, retryable failures and oversized content.

## Context

A fast HTTP client is insufficient when redirects or decompression can escape destination policy or consume unbounded memory.

## Decision

Automatic redirects stay disabled. The coordinator supplies approved IPs, body budget and timeout per request; defaults are 2,000,000 decoded bytes and 15 seconds. The fetcher streams 16 KiB chunks, checks supported media types and closes the response/client. Policy, timeout, network, size and media failures retain their types. The host politeness slot covers body consumption, not only headers.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Policy-controlled streaming hops | Destination and memory bounds | More explicit orchestration | chosen |
| Follow redirects and read full response | Less code | Bypasses hop approval and risks large allocation | rejected |
| Headless browser for every page | Executes dynamic pages | Much higher resource cost and wider attack surface | deferred |

## Why

The crawler primarily ingests extractable docs and structured text. Bounded HTTP acquisition fits this scope and makes failure decisions inspectable.

## Consequences

- Gained: Limits apply before downstream parsing and persistence.
- Accepted limitations / tech debt: JavaScript-only pages and unsupported media remain outside acquisition coverage; bytes are still buffered up to the cap.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Every redirect receives fresh destination checks.
- No successful payload exceeds the effective body budget.
- Transport errors do not become success-shaped responses.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/fetcher/fetch.py`](../../../crawler/src/crawler/fetcher/fetch.py)
- [`crawler/src/crawler/fetcher/config.py`](../../../crawler/src/crawler/fetcher/config.py)
- [`crawler/src/crawler/fetcher/errors.py`](../../../crawler/src/crawler/fetcher/errors.py)
- [`crawler/src/crawler/policy_and_politeness/policy_coordinator.py`](../../../crawler/src/crawler/policy_and_politeness/policy_coordinator.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/src/crawler/fetcher/tests`](../../../crawler/src/crawler/fetcher/tests)
- [`crawler/src/crawler/worker/tests`](../../../crawler/src/crawler/worker/tests)

## Revisit when

- A measured source requirement cannot be served by static/structured acquisition.
- Connection setup dominates profiles and pooling can preserve per-request pinning.

## Rules for future changes

- Never enable automatic redirects in the hop fetcher.
- Preserve exception taxonomy and decoded-byte enforcement when changing HTTP clients.
