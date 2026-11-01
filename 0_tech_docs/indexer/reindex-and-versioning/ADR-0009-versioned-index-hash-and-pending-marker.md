---
id: ADR-0009
title: Reindexing is driven by a version prefix in indexed_hash and a reindex:pending marker, never by deleting rows
status: accepted
date: 2026-10-31
area: indexer
feature: reindex-and-versioning
code:
  - crawler/src/indexer/config.py:IndexerConfig.index_hash_prefix
  - crawler/src/indexer/builder.py:calculate_index_hash
  - crawler/src/indexer/selector.py:_outdated_index_condition
  - crawler/src/indexer/reindex.py:mark_for_reindex
  - crawler/src/indexer/reindex.py:mark_all_for_reindex
  - backend/src/backend/core/config.py:indexer_index_version
  - backend/src/backend/services/indexer_reporting.py
supersedes:
superseded_by:
related: [ADR-0008]
---

# ADR-0009: Version prefix in indexed_hash and a reindex:pending marker

## TL;DR
`search_index.indexed_hash` is `v<INDEXER_INDEX_VERSION>:<sha256 of every input that affects the index>`. The selector treats any row whose hash does not start with the current `v<N>:` as outdated. To rebuild everything after changing analyzer or vector rules, bump `INDEXER_INDEX_VERSION`; to rebuild some documents, set their hash to `reindex:pending`. Old vectors stay searchable until the new build replaces them, so search never has a hole.

## Context
The index depends on code as well as data: field weights in `analyzer.py`, `to_tsvector` expressions in `vector.py`, the text search configs, and size limits. Changing any of them makes every existing row wrong, but `document.updated_at` does not change, so the freshness rule from ADR-0008 would not notice.

Constraints: no new column or table if avoidable; rebuilding must not make documents disappear from search; an operator must be able to force a rebuild of one document while debugging.

## Decision
- **Hash** (`calculate_index_hash`): SHA-256 over a JSON payload with `format: 1`, `index_version`, both text search configs, and every document field the index reads (`document_id`, `source_id`, `canonical_url`, `document_type`, `title`, `description`, `body`, `headings`, `code_blocks`, `tags`, ...). Timestamps and crawl observations are left out. The stored value is `v<index_version>:<hex>`.
- **Version** (`INDEXER_INDEX_VERSION`, default 1, range 1 to 999,999): the selector's outdated predicate includes `NOT indexed_hash LIKE 'v<version>:%'`, so a bump makes every row a candidate. Rows are rebuilt by the normal worker at its normal pace.
- **Skip rule**: the writer returns `UNCHANGED` only when the stored hash equals the new hash **and** `indexed_at >= document.updated_at`.
- **Targeted rebuild** (`python -m indexer.reindex --document-id N` or `--all`, both with `--dry-run`): lock the available documents `FOR UPDATE` in id order and set `indexed_hash = 'reindex:pending'` on their existing index rows. Vectors are not touched. `--all` pages by `document.id` in committed batches (default 100). Documents with no index row are skipped because the selector already picks them up.
- **Backend must agree.** `backend` reads `INDEXER_INDEX_VERSION` (`settings.indexer_index_version`) for the coverage report's "current" count. A mismatch only makes the report wrong; it does not affect search.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Version prefix inside `indexed_hash`, `reindex:pending` marker | No schema change; old vectors keep serving; one env var to rebuild everything | The hash column carries two meanings; backend and worker must share the version; rebuild speed is the worker's normal pace | chosen |
| B. Separate `index_version` integer column | Clean to query and index | A migration; two columns that must agree with each other | rejected (not needed yet) |
| C. `DELETE FROM search_index` (or truncate) and let the worker rebuild | Simplest | Every document vanishes from search until it is rebuilt; vocabulary counts must be decremented for every row | rejected |
| D. Build a new index table (blue/green) and swap | Zero degradation; instant switch | Two tables, a swap step, double storage | rejected for current size |
| E. Set `indexed_at = NULL` or an old date to force rebuild | No marker string | Breaks the meaning of `indexed_at` ("a completed build happened then") | rejected |

> **Question for nish:** did you consider a separate version column (option B) and decide the prefix was enough, or was the prefix the first idea? One line either way.

## Why
- **Availability.** Neither a version bump nor the marker removes vectors, so search keeps returning (slightly outdated) results for every document during a rebuild.
- **Correctness.** Because the version and the configs are inside the hashed payload, a build under new rules can never be mistaken for `UNCHANGED`. The hash also covers every indexed field, so a crawler update that changes content but keeps `updated_at` would still rebuild if the row is reselected.
- **Cost to build.** No migration; one property on the config and one CLI.

## Consequences
- Gained: analyzer and vector changes ship by bumping one number; single documents can be rebuilt on demand.
- Accepted limitations:
  - During a rebuild the index mixes old-version and new-version rows. Ranking can be inconsistent until it finishes.
  - A full rebuild runs at worker speed (`batch_size` × `concurrency` per poll), with no progress beyond the coverage report.
  - `reindex:pending` and other prefixes are free-form strings in one column; the coverage report splits on `:` to show the version.
  - Rebuilds change lexemes, so the vocabulary is updated through normal deltas (ADR-0002); no separate vocabulary step is needed.
- What depends on this: the selector predicate (ADR-0008), the coverage report, and the operations runbook (`crawler/src/indexer/operations.md`).

## Invariants
- Every stored hash written by the writer starts with `v<index_version>:`.
- The hash payload includes `index_version` and both text search configs.
- `reindex.py` only changes `indexed_hash`; it never deletes rows or touches vectors.
- `INDEXER_INDEX_VERSION` is the same for the indexer worker and the backend.

## Evidence
- Tests: `crawler/src/indexer/tests/test_builder.py` (hash), `test_selector.py` (old-version rows selected), `test_service_writer.py` (version refresh), `test_indexer.py` (Postgres lifecycle).
- Measured: none.
- Commits: `b58e156` (builder), `0aedb4c` (reindex CLI and runner).

## Revisit when
- A full rebuild at worker speed takes longer than you are willing to serve mixed-version results. Consider blue/green (option D) or a dedicated backfill mode with higher concurrency.
- Queries need to filter or count by version often enough that string prefix matching becomes slow; add a column (option B).

## Rules for future changes
- Bump `INDEXER_INDEX_VERSION` (worker and backend together) in the same change as any edit to `analyzer.py`, `vector.py`, field weights, configs or size limits that changes vector output.
- Add every new indexed field to the `calculate_index_hash` payload.
- Never force a rebuild by deleting `search_index` rows; use `indexer.reindex` or a version bump.
- Keep passing: `indexer/tests/test_builder.py`, `test_selector.py`, `test_service_writer.py`.
