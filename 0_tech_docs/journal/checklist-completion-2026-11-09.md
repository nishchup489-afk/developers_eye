# Engineering checklist completion — 2026-11-09

Branch: `fix/checklist`. All engineering items above the final three sections of
[the checklist](fix_checklist.md) are checked with evidence or an explicit
decision to defer a conditional optimization. Tech docs, technical writing and
release-gate sections retain their original contents and checkbox states.

## Changes and evidence

| Area | Result | Record |
| --- | --- | --- |
| Acquisition integrity | Original owner retained; atomic per-target provenance; selected producer recorded; thin competing pages cannot replace richer stored content | [ADR-0052](../crawler/document-writer/ADR-0052-acquisition-provenance-and-content-quality.md), [INC-0037](../crawler/document-writer/INC-0037-thin-pages-and-competing-sources-replaced-content.md) |
| Search presentation | Explicit language preference, bounded/shareable paging, conservative language/version/last-observed metadata, related variant counts and relevant code excerpts | [ADR-0053](../frontend/search-experience/ADR-0053-language-preferences-and-result-provenance.md) |
| Category repair | Exact FastAPI-host classification; bounded dry-run/apply maintenance; 116 derived index categories repaired in the current corpus | [INC-0038](../crawler/content-processing/INC-0038-fastapi-documents-mapped-to-articles.md) |
| Search performance | SQL-stage timings, cold/warm samples and plans; full code metadata loaded only for final-page results | [EXP-0013](../infra/performance-and-scaling/EXP-0013-read-only-search-stage-profiling.md) |
| Relevance | 25 real-corpus queries, 328 editorial agent grades, frozen BM25/native rankings and reports at five/ten results; weights unchanged | [EXP-0014](../backend/ranking/EXP-0014-agent-reviewed-25-query-baseline.md), [dataset](../../backend/evaluation/checklist-25/README.md) |
| Structure | Extracted search components, one typed client factory, resource/outcome dispatch and finalize helpers; backend remains the shared schema package | [ADR-0054](../backend/package-boundary/ADR-0054-retain-backend-as-the-shared-schema-package.md) |
| Crawl write costs | Batched CPU checkpoints and terminal summary update; one-worker transactions/request 8.88 → 7.91, tuple updates/request 10.03 → 5.00 | [ADR-0055](../crawler/monitoring-and-telemetry/ADR-0055-batched-cpu-checkpoints-and-terminal-attempt-summaries.md), [EXP-0015](../infra/performance-and-scaling/EXP-0015-linux-crawl-write-cost-and-staged-workers.md) |
| Cancellation | Search/suggestions use centralized Node HTTP options; closing the browser request closes the upstream socket and cancels PostgreSQL work | [ADR-0056](../frontend/search-experience/ADR-0056-close-search-sockets-on-cancellation.md), [INC-0040](../frontend/search-experience/INC-0040-aborted-search-left-postgres-waiting.md) |
| Test setup | Redirected Windows output fixed, builds isolated from active dev cache, missing test clients declared, old scheduler contracts collected safely | [INC-0036](../infra/local-dev-and-testing/INC-0036-redirected-windows-test-runner-encoding.md), [INC-0039](../infra/local-dev-and-testing/INC-0039-fresh-clone-test-dependencies.md) |

## Verification

[Tracked verification summary](../../backend/reports/checklist/verification.json)
records final code revision `140c855`, exact suite counts and scope. Later
commits update documentation/evidence only.

| Check | Windows | Fresh Linux clone |
| --- | --- | --- |
| Backend pytest | 547 passed | 547 passed |
| Crawler pytest | 543 passed | 543 passed |
| Indexer pytest | 192 passed | 192 passed |
| Frontend lint/types/build/unit/integration/admin/overview | 46 checks passed | 46 checks passed |
| Total across 12 suites | 1,328; zero failures/skips | 1,328; zero failures/skips |
| Real Next.js → FastAPI → PostgreSQL stack | Passed | Passed |

Both fresh-stack runs create/migrate/seed their own database and remove it on
exit. They verify paging, source/code filters, suggestions, query bounds, 429,
504, overload, twelve alternating search/suggestion cancellations while actual
tables are locked, and concurrency-slot recovery. These are real HTTP stack
tests, not real browser UI automation.

Linux installation used a new Git clone, independent backend/crawler Poetry
environments, Python 3.14, checksum-verified official Node 24.15.0, `npm ci`,
and PostgreSQL 18.6 migrated from empty. The existing Windows application
database was not used for destructive tests. Windows tests use a new migrated
`developers_eye_checklist_test`; the older unversioned test database was retained.

From the repository root, with disposable test database configuration:

```sh
poetry -C backend install
poetry -C crawler install
npm --prefix frontend ci
# Apply backend migrations to the disposable test database first.
python scripts/run_all_tests.py --with-build --save
```

Then run the fresh-stack script with `NEXT_BUILD_DIR=.next-test-runner` in the
backend environment. For example, on Linux:

```sh
NEXT_BUILD_DIR=.next-test-runner backend/.venv/bin/python backend/scripts/e2e_search_stack.py
```

Full npm audit including dev dependencies reports zero vulnerabilities. Separate
Poetry environments pass `pip-audit` after updating the affected Python
telemetry/CA-bundle locks. Gitleaks 8.16 scans the implementation branch range
`dd8ad88..140c855` with no leaks; this does not claim a clean scan of all earlier
repository history or a verified GitHub Actions run. See
[dependency notes](../infra/ci-and-containers/overview.md).

## Decisions that do not introduce new features

Keep exact source-budget counts, request-scoped crawler IP pinning, fresh DNS
validation and full GETs. Maintained counters, shared HTTP/DNS caches,
conditional-fetch validators, fillfactor changes and `de_core` extraction lack
their required correctness/measurement justification. Their evaluation is
complete; their implementation remains deferred in ADR-0054 and EXP-0015.

Linux fake-web runs at one/two/four/eight processes show zero gap/overlap
violations and zero nonzero child exits, with 54.79/58.77/59.64/67.41 requests/s
after batching. They are short controlled runs, not sustained production load.
The existing registry has 380 enabled sources/316 hosts and configured budgets
totaling 598,245 pages. No public crawl was initiated, and these facts do not
prove two-million-page capacity or site-specific permissions.

The relevance assessor was an agent, with explicit prior-exposure limitations;
the benchmark is not an independent human holdout. Cold common-term search
costs and production/browser/sustained-load validation remain open release
concerns. No public deployment, push or merge was performed.
