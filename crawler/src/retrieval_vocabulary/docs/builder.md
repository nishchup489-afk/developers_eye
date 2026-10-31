# Vocabulary builder (`builder.py`)

**Purpose:** Convert one selected, successfully indexed document into a validated `VocabularyDocument` for the tokenizer.

## Flow

```text
selector.py → VocabularyCandidate(document_id, indexed_hash)
           → builder.build_vocabulary_document(candidate, session)
           → repository.fetch_indexed_document(...)
           → VocabularyDocument | None
           → tokenizer.py
```

- **Repository** performs the single PostgreSQL `SELECT`: joins `document` to `search_index`, checks that the source is available, `indexed_at >= document.updated_at`, and `indexed_hash` matches a completed `vN:<sha256>` revision.
- **Builder** converts nullable text to `""`, nullable lists to `()`, and list content to tuples. It validates data using the existing Pydantic `VocabularyDocument` schema.
- **Returns `None`** when the repository finds no current matching revision. This is not an error: the indexer may have updated the document since selection.
- **Raises `VocabularyValidationError`** for a REMOVE candidate. The removal path does not need the builder.
- **Raises `VocabularyBuildError`** for malformed database content (e.g., a non-string body or a list containing an integer).
- **Never writes to PostgreSQL**, commits, normalizes, or tokenizes.

## Example

Input: `VocabularyCandidate(document_id=101, action=SYNC, indexed_hash="v1:...")`

Output: `VocabularyDocument(document_id=101, indexed_hash="v1:...", title="Python Async", body="...", headings=("Intro",), ...)`

## Safety / concurrency

The selector's result is only a hint. The repository checks freshness at read time, but another indexer update may occur **after** the builder returns. `writer.py` must lock/revalidate the indexed revision in its write transaction.

## Tests

```powershell
# From developers-eye/crawler
poetry run pytest src/retrieval_vocabulary/tests/test_builder.py -v
poetry run pytest src/retrieval_vocabulary/tests/test_repository_builder.py -v -rs
```

The second test file uses temporary PostgreSQL tables when `VOCABULARY_TEST_DATABASE_URL` points to a test database. It can load the variable from `src/retrieval_vocabulary/.env.local` through your existing `tests/conftest.py`.

**Schema caveat:** The repository query assumes your `Document` ORM provides `title`, `description`, `body`, `headings`, `code_blocks`, and `tags` attributes. Confirm the actual ORM and database column types before relying on the integration tests.
