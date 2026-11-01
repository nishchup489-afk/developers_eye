# Search vectors

Area: indexer · Status: active

## Purpose
Builds the two weighted `TSVECTOR` expressions stored per document in `search_index`: `search_vector` (`english`) for prose and `code_vector` (`simple`) for identifiers and code. It builds SQL expressions only; the writer executes them.

## Code
- `crawler/src/indexer/vector.py`
- `backend/src/backend/models/search_index.py`

## How-it-works docs
- `crawler/src/indexer/docs/vector.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0010](ADR-0010-two-weighted-tsvectors-in-postgres.md) | decision | Two weighted Postgres tsvectors, english for prose and simple for code | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] Two tsvectors: `english` for prose, `simple` for code tokens (ADR-0010)
- [x] Postgres full-text search instead of a separate search engine (ADR-0010)

## Rules for future changes
- Bump `INDEXER_INDEX_VERSION` with any change to fields, weights, configs or vector construction (ADR-0010, ADR-0009).
- Keep `/search` configs equal to the indexer configs (ADR-0010, ADR-0003).
- Bind document text and config names; never interpolate them into SQL (ADR-0010).
