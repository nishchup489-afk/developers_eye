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
