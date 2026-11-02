# Evidence, scope and validation

## Scope

This documentation capture uses main at [`facd333`](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492), reviewed on 2026-11-02. It covers backend/database, crawler, indexer/vocabulary, search components, frontend/admin and infrastructure plans. It does not change application behavior, fix the recorded incidents, merge a PR, rotate credentials or certify a deployment.

## Evidence hierarchy

| Evidence | Permitted conclusion | Limit |
| --- | --- | --- |
| Current code and caller inspection | Implemented behavior and integration gaps at the pinned revision | Not proof of a successful production run |
| Existing tests | What assertions were authored | Not a passing run without execution evidence |
| Linked commits/PRs and fix logs | Historical changes and documented causes | Commit messages alone do not prove performance or deployment |
| EXP-0001 | Historical synthetic scheduler benchmark with recorded setup/results | Not rerun here and not production QPS |
| EXP-0002 | Qualitative prototype abandonment supported by commits | No measured resource improvement |
| EXP-0003 | Static SQL-call counts and illustrative arithmetic | Not elapsed time or complete request cost |
| EXP-0004–0006 | Reproducible prerequisites/protocols for future evaluation | Not run; no results invented |
| Prior project discussions | Intent: backend-first scope, abandoned worker, future BM25/Nginx/scaling | Code takes precedence for implementation status |

The template and baseline accepted records were read before adding new records. Current saved ranking drafts agree with the inspected statistics module; the code is the authoritative implementation. No personal/career information or credentials are included.

See the [historical evidence catalog](infra/system-architecture/evidence-catalog.md) for retained writer/scheduler reports and the complete crawler fix-log cross-reference.

## Historical records preserved

ADR-0001–0012, INC-0001–0006 and EXP-0001 retain their original bodies. New living overviews correct stale service paths and distinguish current implementation from original intent. The old technical handoff remains historical, with a pointer to the current architecture. New record dates are capture dates unless their narrative gives the event date.

## Verification boundary

This is documentation work. Validation covers record/template structure, unique IDs, source/relative links, feature/index coverage, metadata references, generated navigation and source-level assertions about important incomplete components. Application and PostgreSQL test suites were not run for this PR. Existing test references are reproduction pointers, not new pass claims.

No production database was read or modified. No network crawl/load benchmark, deployment, migration, vocabulary rebuild or secret rotation was performed. The known incremental vocabulary defects and fuzzy import defect remain open and are explicitly documented.

The root environment did not have the backend pytest/SQLAlchemy runtime installed. Static inspection and documentation validation do not substitute for the PostgreSQL checks listed in the records. Runtime verification belongs with the follow-up implementation/repair.

## Remaining unknowns

Deployment/provider state, current corpus size, actual database drift, production credential rotation, live QPS/latency and result quality cannot be established from this repository snapshot. Do not infer them from dependency declarations, old screenshots, local milestone counts, roadmap boxes or empty implementation files.
