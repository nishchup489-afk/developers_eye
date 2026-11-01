# Document snapshot and field weighting

Area: indexer · Status: active

## Purpose
Turns a stored `document` into an immutable snapshot (`builder.py`, which also computes `indexed_hash`) and then into weighted prose and code fields (`analyzer.py`). It does not touch the database beyond reading the document.

## Code
- `crawler/src/indexer/builder.py`
- `crawler/src/indexer/analyzer.py`

## How-it-works docs
- `crawler/src/indexer/docs/builder.md`
- `crawler/src/indexer/docs/ANALYZER.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0010](../search-vectors/ADR-0010-two-weighted-tsvectors-in-postgres.md) | decision | Field weights per vector (owned by search-vectors) | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] Field weights for title, description, body, code (ADR-0010)

## Rules for future changes
- Field and weight changes bump `INDEXER_INDEX_VERSION` (ADR-0010, ADR-0009).
- Add every new indexed field to the `calculate_index_hash` payload (ADR-0009).
