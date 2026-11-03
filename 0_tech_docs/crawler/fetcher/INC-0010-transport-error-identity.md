---
id: INC-0010
title: Transport exceptions and shadowed policy errors broke classification
status: resolved
date: '2026-11-02'
severity: medium
area: crawler
feature: fetcher
code:
- crawler/src/crawler/fetcher/transport.py
- crawler/src/crawler/fetcher/errors.py
- crawler/src/crawler/policy_and_politeness/policy_coordinator.py
fix_commits:
- fd7dc8799cafae833afeb6b96a842048335d8d63
- 6b2b4a67e21ceb8fdd16dea010f11242c227e68f
related:
- ADR-0016
---

# INC-0010: Transport exceptions and shadowed policy errors broke classification

## Signature

`ReadTimeout` could become `AttributeError`; a real `FetcherSecurityError` escaped the coordinator handler.

## Summary

Historical crawler fixes restored transport error identity and shared policy exceptions so timeouts and rejected responses follow the intended defer/deny paths.

## Expected vs actual

- Expected: Transport errors retain their HTTPX equivalents and policy errors are caught by type identity.
- Actual: Catching nonexistent httpcore.HTTPError masked the original failure, and redefining FetcherSecurityError shadowed the imported class.

## Root cause

Exception conversion depended on a nonexistent base class in the declared httpcore version. Separately, same-name local exception classes are not the same Python type.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

Catch the concrete httpcore classes from the conversion table, preserve causes, and import the shared security error without redefining it. Coordinator tests raise the fetcher actual exception, not a local lookalike.

## Prevention

- Regression test: opening, streaming and closing failures preserve error types and causes.
- Regression test: actual fetcher policy rejection releases host slots and yields the intended decision.
- Remaining risk: HTTP library upgrades can change exception behavior.

## Rules for future changes

- Do not collapse all transport failures into a generic retry.
- Test exception identity across the module boundary.

## Evidence

Historical fix logs: [transport](../../journal/update-log/01_transport_errors.md) and [policy rejection](../../journal/update-log/02_policy_rejections.md). No new live-network run is claimed.

- [`crawler/src/crawler/fetcher/transport.py`](../../../crawler/src/crawler/fetcher/transport.py)
- [`crawler/src/crawler/fetcher/errors.py`](../../../crawler/src/crawler/fetcher/errors.py)
- [`crawler/src/crawler/policy_and_politeness/policy_coordinator.py`](../../../crawler/src/crawler/policy_and_politeness/policy_coordinator.py)
