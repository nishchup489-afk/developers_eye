# Bounded fetcher

Area: crawler · Status: active

## Purpose

Executes policy-approved HTTP hops with streaming, size/media limits and typed failures. It does not independently choose redirects or bypass destination approval.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/fetcher`](../../../crawler/src/crawler/fetcher)
- [`crawler/src/crawler/policy_and_politeness/policy_coordinator.py`](../../../crawler/src/crawler/policy_and_politeness/policy_coordinator.py)

## How-it-works docs

- [`crawler/src/crawler/fetcher/docs/flow.md`](../../../crawler/src/crawler/fetcher/docs/flow.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0016](ADR-0016-bounded-hop-fetching.md) | decision | Stream bounded responses through a policy-approved single-hop transport | accepted |
| [INC-0010](INC-0010-transport-error-identity.md) | incident | Transport exceptions and shadowed policy errors broke classification | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Never enable automatic redirects in the hop fetcher.
- Preserve exception taxonomy and decoded-byte enforcement when changing HTTP clients.
- Do not collapse all transport failures into a generic retry.
- Test exception identity across the module boundary.
