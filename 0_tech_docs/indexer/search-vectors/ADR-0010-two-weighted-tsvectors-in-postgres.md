---
id: ADR-0010
title: Index each document as two weighted Postgres tsvectors, english for prose and simple for code
status: accepted
date: 2026-10-31
area: indexer
feature: search-vectors
code:
  - crawler/src/indexer/analyzer.py
  - crawler/src/indexer/vector.py:build_search_vectors
  - crawler/src/indexer/vector.py:build_field_vector
  - crawler/src/indexer/config.py:IndexerConfig
  - backend/src/backend/models/search_index.py
  - backend/alembic/versions/28efc23fadfc_update_search_index.py
supersedes:
superseded_by:
related: [ADR-0003, ADR-0009, ADR-0002]
---

# ADR-0010: Two weighted Postgres tsvectors, english for prose and simple for code

## TL;DR
Search uses PostgreSQL full-text search, not a separate search engine. Each document gets two `TSVECTOR` columns in `search_index`, each with a GIN index: `search_vector` built with the `english` config (stemming, stop words) from title, tags, headings, description and body, and `code_vector` built with the `simple` config (lowercase only, no stemming) from tags, title, code blocks, headings and URL. Fields carry `setweight` A to D so a title match ranks above a body match. Developer queries mix English and identifiers, and one config cannot serve both.

## Context
Documents are developer content: prose that benefits from stemming (`running` → `run`) next to identifiers that stemming damages (`asyncio`, `useEffect`, `getattr`, `numpy.ndarray`). The English config also drops stop words, which removes things like the `in`, `is` or `as` keywords from code.

Everything else already lived in PostgreSQL: documents, frontier, attempts. The project is run by one developer on a laptop.

> **Question for nish:** what made you choose Postgres FTS over Elasticsearch/OpenSearch/Meilisearch/Typesense? Was it "one database to run", wanting to learn ranking from scratch, or something you measured? This is the biggest architectural choice in search and deserves your own reasoning here.

## Decision
- **Engine.** PostgreSQL `to_tsvector`, `@@`, `ts_rank_cd`, `ts_headline`. Vectors are computed inside Postgres (the writer sends SQL expressions, not Python-built vectors), so query-time and index-time tokenization are the same code.
- **Two columns** in `search_index`, both `NOT NULL`, both GIN indexed: `search_vector` and `code_vector` (the second added by migration `28efc23fadfc`).
- **Configs.** `INDEXER_TEXT_SEARCH_CONFIG` (default `english`) for prose and `INDEXER_CODE_SEARCH_CONFIG` (default `simple`) for code. Only `english` and `simple` are accepted; the name is validated against a pattern and bound as a `regconfig` value, never interpolated.
- **Field weights** (`analyzer.py`):

  | Field | `search_vector` (english) | `code_vector` (simple) |
  | --- | --- | --- |
  | title | A | A |
  | tags | A | A |
  | headings | B | B |
  | description | B | not included |
  | body | C | not included |
  | code blocks | not included | B |
  | canonical URL | not included | D |

- **Empty fields** become an empty tsvector, so a document with no code still has a valid `code_vector`.
- **Changing any of this** (fields, weights, configs, vector construction) requires bumping `INDEXER_INDEX_VERSION` (ADR-0009).

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Postgres FTS, two weighted tsvectors (`english` + `simple`) | No extra service; index updates are transactional with documents; prose stemmed and identifiers preserved | Ranking is basic (`ts_rank_cd`, no BM25, no IDF); no built-in fuzzy matching; scaling is one Postgres | chosen |
| B. Postgres FTS, one `english` vector | Half the storage and one query | Stemming and stop words mangle identifiers | rejected |
| C. Postgres FTS, one `simple` vector | Identifiers exact | No stemming: `install` misses `installing` | rejected |
| D. Elasticsearch / OpenSearch | BM25, analyzers per field, fuzzy, highlighting | Separate cluster; a sync pipeline from Postgres; heavy on a laptop | rejected for now |
| E. Meilisearch / Typesense | Typo tolerance and ranking out of the box, light to run | Another service to keep in sync; less control over ranking | rejected for now |
| F. Custom code tokenizer (split `camelCase`, `snake_case`, dotted names) | Matches `use effect` to `useEffect` | Needs a custom Postgres parser or Python-side tokens | not done |

## Why
- **Correctness.** The same Postgres config parses the document and the query, so stems line up. `simple` keeps `asyncio` and `numpy` intact for exact identifier queries.
- **Consistency.** The index is written in the same database transaction model as everything else: the writer can lock the document and upsert the vectors atomically (ADR-0008), and the vocabulary is derived from the same stored lexemes (ADR-0002).
- **Operability.** No second system to deploy, monitor or resync.
- **Security.** Config names and weights are hard-coded or validated; document text is always a bound parameter.

## Consequences
- Gained: weighted, stemmed prose search plus exact-ish identifier search with zero extra infrastructure.
- Accepted limitations:
  - `ts_rank_cd` has no inverse document frequency; common words in a title score like rare ones. Real BM25 is planned in `search/ranking/`.
  - `simple` splits on Postgres's default parser rules, so `numpy.ndarray` and `c++` are not matched as single symbols. Punctuation-sensitive lookup needs another index (noted in `search/retrieval/code.py`).
  - Title and tags appear in both vectors, so they contribute to both ranks when `/search` adds them (ADR-0003).
  - Storage is roughly two vectors per document plus two GIN indexes.
- What depends on this: `/search` (must use the same configs, ADR-0003), the vocabulary (ADR-0002), the coverage report.

## Invariants
- `search_vector` uses `INDEXER_TEXT_SEARCH_CONFIG` and `code_vector` uses `INDEXER_CODE_SEARCH_CONFIG`; `/search` uses the same pair.
- Both vectors are `NOT NULL` (empty tsvector when a document has no content for them).
- Vectors are computed in Postgres from bound text; no SQL is built by string interpolation of document text or config names.
- Any change to the table above bumps `INDEXER_INDEX_VERSION`.

## Evidence
- Tests: `crawler/src/indexer/tests/test_analyzer.py`, `test_vector.py` (72 tests at `6c3b24d`), `test_indexer.py` (Postgres).
- Measured: none (no relevance or latency numbers).
- Commits: `423f1da` (analyzer), `6c3b24d` (vector), `28efc23fadfc` migration (`code_vector`).
- Related known gap: the `code_vector` migration adds a `NOT NULL` column without a default, so it fails on a non-empty `search_index` (handoff gap 3).

## Revisit when
- The relevance evaluation set shows identifier queries failing because of tokenization (consider option F).
- `ts_rank_cd` cannot be tuned to pass the evaluation set and BM25 in SQL becomes too slow; reconsider options D or E.
- `search_index` size or GIN update cost becomes a bottleneck for the indexer.

## Rules for future changes
- Bump `INDEXER_INDEX_VERSION` with any change to fields, weights, configs or vector construction.
- Keep query-time configs in `/search` equal to the indexer configs.
- Do not add a third config name without widening the allowlist in `IndexerConfig` deliberately.
- Keep passing: `indexer/tests/test_analyzer.py`, `test_vector.py`, `test_indexer.py`.
