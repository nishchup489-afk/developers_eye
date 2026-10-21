# Closing structured-ingestion edge cases and verifying persistence

**Files involved:** structured parsers/helpers, worker dispatch, source discovery, ingestion tests, PostgreSQL pipeline tests, explanatory docs and the test-artifact ignore rule.

## The problem

Sitemap gzip bytes could be accepted by the parser but omitted by the fetcher's textual MIME allowlist. Corrupt deflate errors and extreme date conversions needed normalized failure handling. Namespaced Atom XHTML could leak script text into searchable bodies. Automatic sitemap discovery also needed to remain opt-in for feed/API sources, and a small frontier budget could admit a sitemap before the primary page seed.

## What changed

Allow bounded gzip file MIME types only for sitemap fetches. Normalize corrupt gzip/date failures, remove namespaced non-content markup, validate discovery flags, default feed/API sitemap expansion to false, prioritize robots declarations within candidate limits and reserve the primary seed before auxiliary maps. Normalize touched Python line endings and expose the existing rss_atom module entry point. Add real PostgreSQL cases for all structured kinds, document the test layers and ignore generated local database files.

## Verification

- 456 offline regression tests and 33 subtests pass. Six database cases skip in the offline invocation.
- All 13 PostgreSQL writer/pipeline integration tests pass against a separately initialized PostgreSQL 18 cluster migrated through Alembic head, including three new sitemap/RSS/API persistence cases.
- All 73 standalone DNS checks pass.
- Python compilation, Poetry lock validation and the diff whitespace check pass.
- The disposable PostgreSQL server was stopped after testing. The application's normal database and running crawler were not used.
