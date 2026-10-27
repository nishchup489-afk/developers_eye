# Indexer test cases

Tests for the search indexer: `selector -> builder -> analyzer -> vector -> repository`. Run from `crawler/` with `poetry run pytest src/indexer/tests -v`. Tests that need PostgreSQL are skipped unless `TEST_DATABASE_URL` is set.

## conftest.py

Shared fixtures, not tests:

- `config`: an `IndexerConfig` with batch size 10, index version 1, a 100,000 character limit, `english` text search, and `simple` code search.
- `make_document`: builds a crawler `Document` (an available Python async tutorial with headings, a code block, and tags in `metadata_`).
- `make_index_document`: builds the matching `IndexDocument`.
- `candidate`: an `IndexCandidate` for document 10 at the fixed source timestamp.

It also adds `src/` to `sys.path` so the tests run against the source checkout.

## test_builder.py

Turning a crawler `Document` into an `IndexDocument`, and the index hash.

| Test | What it checks |
| --- | --- |
| `test_prepare_normalizes_text_and_metadata` | `prepare_index_document` applies Unicode NFC, converts `\r\n` and `\r` to `\n`, trims text, drops blank headings and code blocks, keeps code indentation, dedupes tags case-insensitively (first spelling wins), copies `updated_at`, and returns a frozen object. |
| `test_prepare_does_not_mutate_crawler_metadata` | The original `metadata_` dict is unchanged. |
| `test_prepare_rejects_invalid_document_id` | IDs `0`, `-1`, `"10"`, and `True` raise `IndexDocumentError`. |
| `test_prepare_rejects_unavailable_document` | An unavailable document raises `StaleIndexSourceError`. |
| `test_prepare_rejects_invalid_metadata` | Non-object metadata, non-list tags, and non-string headings or code blocks raise `IndexDocumentError` with a field-specific message. |
| `test_prepare_enforces_total_character_limit` | A document over `max_document_chars` raises `IndexDocumentTooLargeError`. |
| `test_build_reloads_document_and_prepares` | `build_index_document` reloads the document with one query and returns the prepared result for the candidate. |
| `test_build_rejects_stale_candidate` (missing, unavailable, updated) | A deleted, unavailable, or newer-than-candidate document raises `StaleIndexSourceError`. |
| `test_build_propagates_database_failure` | Database errors are not swallowed. |
| `test_hash_is_stable_and_version_prefixed` | `calculate_index_hash` is deterministic and is the version prefix plus 64 hex characters. |
| `test_hash_changes_for_index_relevant_fields` | Changing title, description, body, headings, code blocks, tags, canonical URL, or content hash changes the hash. |
| `test_hash_changes_when_index_version_changes` | Bumping `index_version` changes the hash. |
| `test_hash_excludes_source_timestamp` | A recrawl that only changes `source_updated_at` keeps the same hash. |

## test_analyzer.py

Splitting an `IndexDocument` into weighted text and code fields. No database and no TSVECTOR building.

| Test | What it checks |
| --- | --- |
| `test_analyzer_separates_text_and_code` | Text fields are title (A), tags (A), headings (B), description (B), body (C) with the `english` config. Code fields are tags (A), title (A), code_blocks (B), headings (B), canonical_url (D) with the `simple` config. IDs and timestamp are copied. |
| `test_analyzer_preserves_boundaries_and_code_whitespace` | List items are joined with blank lines, and code indentation is kept. |
| `test_analyzer_skips_optional_blank_fields` | Blank description, headings, tags, and code blocks are left out. |
| `test_analyzer_output_is_frozen` | Results and fields are frozen tuples and dataclasses. |
| `test_analyzer_is_deterministic` | The same input gives an equal result. |
| `test_field_rejects_non_strings` / `test_field_rejects_nul` / `test_field_returns_none_for_whitespace_only` | `_field` rejects non-strings and NUL bytes with `IndexDocumentError`, and returns `None` for whitespace-only text. |
| `test_join_items_does_not_change_indentation` / `test_join_items_rejects_invalid_container_or_elements` | `_join_items` keeps indentation and skips empty items, and rejects lists, `None` items, and non-tuples. |
| `test_analyzer_rejects_wrong_argument_types` | Wrong document or config types raise `TypeError`. |

## test_vector.py

Building bound, typed PostgreSQL `TSVECTOR` expressions. Most tests only compile SQL; one optional test runs against PostgreSQL.

| Test | What it checks |
| --- | --- |
| `test_empty_vector_is_typed_and_parameterized` | The empty vector is a `CAST('' AS TSVECTOR)` with a bound empty string. |
| `test_field_vector_compiles_as_weighted_tsvector` | A field becomes `setweight(to_tsvector(REGCONFIG, text), 'A')` with the text and config as bound parameters. |
| `test_all_supported_weights_are_compiled_as_literals` | Weights A to D are SQL literals, not parameters. |
| `test_field_values_are_bound_and_not_interpolated_into_sql` | A SQL injection payload and a schema-qualified config never appear in the SQL text. |
| `test_blank_field_yields_empty_vector` | Blank text gives the empty vector with no `to_tsvector`. |
| `test_field_vector_rejects_*` | Non-field input (`TypeError`), non-string text, NUL bytes, invalid weights, and invalid config names (spaces, leading digit, injection, double dots, three parts, too long, quoted) raise `ValueError`. Valid names such as `pg_catalog.english` and `_custom_1` are accepted. |
| `test_combining_*` | Zero fields give the empty vector, one field has no `||`, three fields are joined with `||` in order with their weights, a blank field stays as a valid empty expression, and non-tuple or invalid entries raise `TypeError`. |
| `test_search_vectors_from_real_analyzer_output` | `build_search_vectors` produces text and code vectors with one `to_tsvector` per field and the right configs. |
| `test_search_vectors_does_not_mutate_analyzer_output` / `..._result_is_frozen` / `..._are_deterministic` / `..._allow_empty_field_groups` | No mutation, frozen output, identical SQL across runs, and empty groups give empty vectors. |
| `test_search_vectors_reject_*` | Wrong document or config type, invalid IDs (`0`, `-1`, `True`, `"5"`), invalid timestamps, a field whose `search_config` does not match its group, and non-tuple field groups are rejected. |
| `test_postgresql_executes_weighted_text_and_code_vectors` | Optional, needs `TEST_DATABASE_URL` with asyncpg. Real PostgreSQL stems `Running` to `'run':1A` in the text vector and keeps `'running':1B` in the code vector. |

## test_selector.py

Picking documents that need indexing or removal, against real PostgreSQL. Needs `TEST_DATABASE_URL` (asyncpg or psycopg). Each test creates a temporary schema with `document` and `search_index` tables (no foreign keys) inside one transaction and rolls it back.

| Test | What it checks |
| --- | --- |
| `test_new_document_needs_indexing` | A document with no index row is not current and is selected with its `updated_at`. |
| `test_current_document_is_skipped` | An index row newer than the document with the current hash prefix is current and not selected. |
| `test_changed_document_is_reselected` | An index row older than the document's `updated_at` is selected again. |
| `test_old_index_version_is_reselected` | An index row with an old version prefix (`v0:`) is selected again. |
| `test_unavailable_document_is_not_indexed_and_is_removed` | An unavailable document is not a candidate for indexing but is a removal candidate. |
| `test_missing_source_document_triggers_cleanup` | An index row with no matching document is a removal candidate. |
| `test_cursor_and_batch_size` | `after_document_id=10` returns only later candidates (20, 30). |

## test_repository.py

Contract tests for the persistence adapter with a mocked `AsyncSession` (no live database). SQL is compiled for PostgreSQL and inspected.

| Test | What it checks |
| --- | --- |
| `test_get_search_index_loads_only_freshness_metadata` | `get_search_index` returns `StoredIndexState` and selects only `indexed_hash` and `indexed_at`, not the vectors. |
| `test_get_search_index_returns_none_if_missing` | A missing row returns `None`. |
| `test_get_document_for_update_locks_document` | `get_document_for_update` returns `LockedDocumentState`, uses `FOR UPDATE OF document`, and does not commit. |
| `test_get_document_for_update_returns_none_if_missing` | A missing document returns `None`. |
| `test_upsert_uses_bound_parameters_and_updates_both_vectors` | `upsert_search_index` uses `ON CONFLICT (document_id) DO UPDATE` to set both vectors, the hash, and `indexed_at = now()`, binds the hash and text as parameters, returns the ID, and does not commit. |
| `test_upsert_rejects_invalid_hash` | An empty hash, a `v0:` version, non-hex, or uppercase hex raises `ValueError` before any SQL runs. |
| `test_repository_rejects_invalid_document_ids` | `0`, `-1`, `True`, and `"10"` raise `ValueError` in get, lock, and delete, with no SQL run. |
| `test_delete_is_idempotent_and_does_not_commit` | `delete_search_index` uses `DELETE ... RETURNING`, returns `True` when a row was removed and `False` when none existed, and does not commit. |

## test_pipeline.py

| Test | What it checks |
| --- | --- |
| `test_document_flows_from_builder_to_analyzer` | Smoke test of the builder and analyzer contract: a document prepared by the builder keeps its ID and timestamp through the analyzer, gets a version-prefixed hash, and its body and first code block appear unchanged in the analyzed text and code fields. |
