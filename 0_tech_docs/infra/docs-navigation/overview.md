# Documentation layers and navigation

Area: infra · Status: active

## Purpose

Keeps decision rationale separate from mechanics and generates shared README maps. Living feature overviews and the record index are the entry points for historical decisions and future proposals.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`scripts/update_docs_nav.py`](../../../scripts/update_docs_nav.py)
- [`0_tech_docs/_templates`](../../../0_tech_docs/_templates)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0034](ADR-0034-two-documentation-layers-and-navigation.md) | decision | Keep mechanics separate from decision history and generate shared navigation | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Do not rewrite accepted rationale to invent history.
- Update public API documentation and validators with contract changes.
- Use the generator for generated navigation blocks.
