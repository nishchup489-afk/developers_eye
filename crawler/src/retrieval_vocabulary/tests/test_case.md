# Selector and repository test cases

| Case | Expected |
| --- | --- |
| New valid indexed document | SYNC |
| Exact indexed revision already processed | Skip |
| Changed index revision | SYNC |
| Crawled but not indexed | Skip |
| Source unavailable | Skip SYNC, schedule REMOVE if processed |
| Source newer than index | Skip until indexed |
| Index hash is `reindex:pending` | Skip SYNC |
| Malformed index hash | Skip |
| Missing search index but previously processed | REMOVE |
| Missing source document but previously processed | REMOVE |
| Pagination limit 2 | Return two ordered rows at most |
| Cursor set to 3 | Return document IDs greater than 3 |
| Invalid limit/cursor including booleans | Raise VocabularyValidationError |
| Empty eligible set | Return empty list |

The database tests use temporary tables. They require an explicitly configured PostgreSQL test database, not the production database.



## Builder + document-fetch repository tests

| Case | Expected |
| --- | --- |
| SYNC candidate with current document | Return validated `VocabularyDocument` |
| Repository returns no row (deleted, stale, unavailable) | Builder returns `None` |
| Text fields are `NULL` | Builder converts each to empty string |
| Headings, code blocks, tags are `NULL` | Builder converts each to empty tuple |
| Headings, code blocks, tags are arrays | Builder returns string tuples |
| Title, description, or body is not a string | Raise `VocabularyBuildError` |
| Heading/code/tag list has invalid type or element | Raise `VocabularyBuildError` |
| Invalid document ID or revision returned by repository | Raise `VocabularyBuildError` after schema validation |
| Input is not a `VocabularyCandidate` | Raise `TypeError` before querying |
| Candidate action is REMOVE | Raise `VocabularyValidationError` before querying |
| Repository query itself fails | Propagate database exception |
| Repository receives invalid document ID or hash | Reject before running SQL |
| PostgreSQL fetch of complete indexed content | Return all selected fields correctly |
| PostgreSQL fetch with nullable content | Preserve nullable source fields; builder handles conversion |
| PostgreSQL index revision differs from selected hash | Return `None` |
| PostgreSQL index is marked `reindex:pending` | Return `None` |
| PostgreSQL source document has become unavailable | Return `None` |
| PostgreSQL document `updated_at` is newer than index | Return `None` |
| PostgreSQL index is missing or has malformed revision | Return `None` |
| PostgreSQL source document is missing | Return `None` |

**Isolation:** Builder unit tests use mocked repository calls. PostgreSQL tests use `CREATE TEMP TABLE` in a dedicated test database and do not change permanent application tables.

**Run:**

```powershell
poetry run pytest src/retrieval_vocabulary/tests/test_builder.py src/retrieval_vocabulary/tests/test_repository_builder.py -v -rs
```
