# Query-aware snippets

Area: backend · Status: active

## Purpose

The pure excerpt component returns bounded text/spans with code-aware boundaries. PR #6 repaired an output-budget bug. Public search still uses ts_headline, so the component and serving behavior must remain distinct.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/snippets`](../../../backend/src/backend/search/snippets)

## How-it-works docs

- [`backend/src/backend/search/snippets/docs/snippets_docs.md`](../../../backend/src/backend/search/snippets/docs/snippets_docs.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0029](ADR-0029-plain-text-query-aware-snippets.md) | decision | Generate bounded plain-text passages with separate highlight offsets | accepted |
| [INC-0009](INC-0009-snippet-window-budget-regression.md) | incident | Code snippet boundary adjustment could exceed max_chars | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Select code excerpts from at most 64 bounded blocks after page selection;
  prefer distinct query-term coverage and preserve source order on ties.

- Render snippet content as text, not trusted HTML.
- Generate snippets after final top-result selection.
- Preserve the hard character cap when improving word/line boundaries.
- Apply the character-budget assertion after all boundary adjustments.
- Do not call a regression resolved in deployment merely because a test was authored.
