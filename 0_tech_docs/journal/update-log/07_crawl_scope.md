# Enforcing crawl depth and source budgets

**Files involved:** frontier scope/repository, worker jobs, seed discovery, frontier model/schema, migration `c72f318bd923` and regression tests.

## The problem

Source configuration included `max_depth: 3`, but it was never read. Every page could discover another thousand URLs with no overall limit.

## What changed

- Persist target depth. Seeds start at 0; children use parent depth plus 1.
- Check depth before fetching and before creating children.
- Enforce `config.max_pages` across concurrent enqueue transactions using a per-source PostgreSQL advisory lock.
- Support `config.allowed_path_prefixes` for an explicit path boundary.

Defaults: depth 3, 10,000 frontier URLs per source, all paths on approved hosts. The page budget includes existing, disabled and scheduled targets; changing the budget does not delete historical records.

Example:

```json
{"max_depth": 3, "max_pages": 1000, "allowed_path_prefixes": ["/3/"]}
```

At depth 3, the page can be fetched but its children are not enqueued. Duplicate URLs do not consume remaining capacity.

## Existing data

The migration backfills depth from stored discovery parents. Broken or cyclic historical chains are left outside the permitted depth rather than treated as new seeds.

## Verification

Offline tests cover depth boundaries, child depth, path traversal, invalid configuration, duplicate URLs and full budgets. SQL compilation verifies the PostgreSQL advisory-lock path. Live multi-worker database validation requires a dedicated test database.
