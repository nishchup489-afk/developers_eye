# Running the indexer tests

What each test checks is in [test_case.md](test_case.md).

## Fast tests (no database)

From `crawler/`:

```powershell
poetry run pytest src/indexer/tests -v -rs
```

Everything runs except the PostgreSQL tests, which show as skipped. `-rs` prints the skip reasons so a skip is not mistaken for a pass.

To run one layer, name its file, for example:

```powershell
poetry run pytest src/indexer/tests/test_service_writer.py -v
```

## PostgreSQL tests

Three tests need a real PostgreSQL server:

- `test_selector.py` (all tests), which creates a temporary schema inside one transaction and rolls it back.
- `test_vector.py::test_postgresql_executes_weighted_text_and_code_vectors`, which only runs a `SELECT`.
- `test_indexer.py::test_final_indexer_lifecycle_against_postgresql`, which uses TEMP tables on its own connection.

None of them write to your real `document` or `search_index` tables, but still point them at a separate test database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/developers_eye_test"
poetry run pytest src/indexer/tests -v -rs
```

`TEST_DATABASE_URL` must use the `postgresql+asyncpg://` driver (`test_selector.py` also accepts `postgresql+psycopg://`).

## Notes

- `conftest.py` holds the shared fixtures (`config`, `make_document`, `make_index_document`, `candidate`) and adds `src/` to `sys.path`, so the tests also run against the source checkout.
- Async tests use `pytest-asyncio` (`@pytest.mark.asyncio`), which is a crawler dependency.
