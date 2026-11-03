# Fixing stored content after 404 and 410 responses

**Files involved:** document model/writer, worker finalization/reporting/monitoring, migration `e94b530df145`, dashboard inspector/contracts and regression tests.

## The problem

A stored page could later return 404 or 410. Its target was permanently disabled while its old document remained indistinguishable from current content.

## What changed

Mark documents owned by that target unavailable, record the HTTP status and first unavailable time, and remove their search-index entries in the same transaction. Preserve the body for admin inspection. Check again after the normal source interval so restored pages can recover.

A later successful observation clears the unavailable fields. Pending-index counts exclude unavailable documents. The inspector displays the reason and timestamp.

The migration also marks historical documents whose latest finished attempt returned 404/410. It preserves existing manually disabled frontier states.

Before: a removed page looked like current content and would never be checked again.

After: its old content is retained with an unavailable marker and can become available again after a successful recrawl.

## Verification

Tests cover 404 and 410 finalization, search invalidation, preserved document rows and availability restoration. Frontend contracts, TypeScript and lint checks cover the inspector update. Migration SQL generation checks the additive schema change.
