# Fixing combined robots metadata

**Files involved:** `parser/html/metadata.py`, `config.py`, `policy_and_politeness/robots_policy.py` and parser tests.

## The problem

Only the first generic robots meta tag was read. A later `noindex` or a directive addressed to DevelopersEyeBot could be ignored.

## What changed

Merge every generic and own-bot meta tag. Preserve restrictive directives regardless of order. Ignore tags addressed only to other bots. Share the crawler's user-agent name between policy and parsing.

Before: `index` followed by `noindex` was accepted for storage.

After: the processor skips the page, and the worker's existing noindex cleanup can remove its stored copy.

## Verification

Parser tests cover both tag orders, bot-specific tags, other bots, nofollow and a restriction after a long directive list. Existing parser and processing tests remain applicable.
