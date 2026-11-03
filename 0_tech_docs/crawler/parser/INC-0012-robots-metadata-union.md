---
id: INC-0012
title: Later or bot-specific robots metadata restrictions were ignored
status: resolved
date: '2026-11-02'
severity: high
area: crawler
feature: parser
code:
- crawler/src/crawler/parser/html/metadata.py
- crawler/src/crawler/config.py
- crawler/src/crawler/processing/processing.py
fix_commits:
- feccf251f827c48833694e76c0c9fffb42010793
related:
- ADR-0018
- ADR-0011
---

# INC-0012: Later or bot-specific robots metadata restrictions were ignored

## Signature

An `index` meta directive followed by `noindex`, or a DevelopersEyeBot-specific restriction, could be missed.

## Summary

Reading only the first generic robots meta tag ignored later restrictive directives and bot-specific policy. This could allow content to be retained/indexed contrary to the parsed page policy.

## Expected vs actual

- Expected: All applicable generic and own-bot restrictions are combined independently of tag order.
- Actual: Only the first generic tag was inspected.

## Root cause

Single-tag extraction represented a potentially repeated policy field as one optional value.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

Merge every generic and own-bot tag, preserve restrictive directives, ignore other-bot-only tags and share the user-agent name across policy/parsing. Processing and worker cleanup handle noindex/nofollow consequences.

## Prevention

- Regression test: both tag orders, bot-specific tags, other-bot tags, nofollow and a late restriction in a long list.
- Remaining risk: HTTP headers and future directives need explicit precedence rules if added.

## Rules for future changes

- Do not replace all-tag policy aggregation with first-tag lookup.
- Keep parser and crawler bot identity aligned.

## Evidence

[Historical metadata log](../../journal/update-log/05_robots_metadata.md).

- [`crawler/src/crawler/parser/html/metadata.py`](../../../crawler/src/crawler/parser/html/metadata.py)
- [`crawler/src/crawler/config.py`](../../../crawler/src/crawler/config.py)
- [`crawler/src/crawler/processing/processing.py`](../../../crawler/src/crawler/processing/processing.py)
