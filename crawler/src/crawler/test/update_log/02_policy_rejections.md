# Fixing fetcher policy rejections

**Files involved:** `policy_and_politeness/policy_coordinator.py` and its tests.

## The problem

The coordinator imported `FetcherSecurityError`, then defined another class with the same name. Exceptions raised by the real fetcher were not caught. A rejected response could be treated as an ordinary retryable job failure.

## What changed

Use the shared exception from `fetcher/errors.py`. Both page requests and robots retrieval now catch the real fetcher's rejection.

Before: an unsupported response encoding escaped the policy handler.

After: the page is denied, or robots retrieval is deferred safely.

## Verification

Coordinator tests now raise the fetcher's actual exception. They verify denied requests and released politeness slots, plus exception-class identity.
