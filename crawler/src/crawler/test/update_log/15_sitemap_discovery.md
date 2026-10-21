# Wiring sitemap discovery into the worker

**Files involved:** source discovery, robots policy/coordinator, parser schemas, sitemap adapter, worker jobs/helpers, runner startup and sitemap discovery tests/docs.

## The problem

The worker disabled sitemap targets and source discovery queued only HTML seeds. A working XML parser alone could not discover or crawl sitemap URLs.

## What changed

Queue configured and conventional sitemap seeds. Carry bounded robots sitemap declarations through policy results. Dispatch leased sitemap targets to the XML parser, validate page/child-map candidates, preserve source budgets and existing atomic lease-safe finalization. Retain the existing local runner startup source sync. Document configuration, depth, limits and worker execution in explanatory docs.

## Verification

The existing 82 targeted sitemap, scope, policy and monitoring tests pass. Four additional discovery/worker tests pass without network or PostgreSQL.
