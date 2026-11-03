---
id: INC-0004
title: Python's urllib.robotparser ignored wildcard Disallow rules and longest-match Allow
status: resolved
date: 2026-10-20
severity: high
area: crawler
feature: robots-and-politeness
code:
  - crawler/src/crawler/policy_and_politeness/robots_rules.py:parse_rules
  - crawler/src/crawler/policy_and_politeness/robots_rules.py:RobotsRules.can_fetch
  - crawler/src/crawler/policy_and_politeness/robots_policy.py
fix_commits: [d154dcc]
related: [ADR-0007]
---

# INC-0004: The standard robots parser ignored wildcards and longest-match rules

## Signature
No error. A page under a wildcard exclusion is fetched and stored:
```
User-agent: *
Disallow: /private/*
```
`/private/file` → allowed (should be denied).
```
User-agent: *
Disallow: /
Allow: /public/
```
`/public/page` → denied (should be allowed).

## Summary
`robots_policy.py` used `urllib.robotparser.RobotFileParser` to evaluate cached robots.txt files. That parser follows the original 1994 draft: it matches rule paths as plain prefixes, does not understand `*` or `$`, and applies the first matching rule in file order instead of the longest one. As a result the crawler fetched pages that site owners had excluded with wildcard rules, and skipped pages that a more specific `Allow` permitted. Fetching excluded pages is the worse half: it is exactly what robots.txt asks crawlers not to do, under our bot's name (`DevelopersEyeBot`).

> **Question for nish:** was this found by a test you wrote against RFC 9309, or by noticing a real site's page in the documents table that should have been excluded? If a real site, which one?

## Expected vs actual
- Expected (RFC 9309, sections 2.2.1 to 2.2.3): `*` matches any sequence, `$` anchors the end, the longest matching rule wins, and `Allow` wins a tie.
- Actual: plain prefix matching and first-match-wins.

## Root cause
The stdlib parser does not implement RFC 9309. The code assumed "standard library" meant "standard behaviour".

## Fixes that did not work
| Attempt | Why it failed |
| --- | --- |
| `urllib.robotparser.RobotFileParser` (original implementation) | No wildcard or `$` support; first match wins. |

## Resolution
Commit `d154dcc` replaced it with `robots_rules.py`, a small network-free matcher (92 lines):
- groups for the same user agent are merged; a group naming our bot wins over `*` (the longest agent token found in our product name `developerseyebot` is used); `/robots.txt` itself is always allowed;
- `*` and `$` are supported;
- the longest matching pattern wins, and `Allow` wins a tie;
- paths and patterns are compared as normalized percent-encoded UTF-8 octets, so `%7E` and `~`, or Unicode paths, compare correctly;
- query strings are part of the match.

The robots cache (`robots_cache`, expiry per origin) and the allow / deny / defer outcomes did not change.

## Prevention
- Regression tests: `crawler/tests/crawler/policy_and_politeness/test_robots_rules.py` (wildcards, `$`, rule order, duplicate groups, user-agent matching, comments, query strings, Unicode and reserved escapes), plus `test_robots_policy.py` and `test_policy_coordinator.py` for integration.
- Monitoring: none.
- Remaining risk: agent matching is a substring test (`agent in product`), so a group for `bot` or `eye` would also apply to us. RFC 9309 asks for a case-insensitive match of the product token. We also maintain our own robots parser. Edge cases not in the tests (very long files, odd line endings, `crawl-delay`) behave however the code happens to handle them.

## Rules for future changes
- Do not go back to `urllib.robotparser` or any parser that does not implement RFC 9309 longest-match and wildcards.
- Any change to `robots_rules.py` needs a test case with the exact robots.txt text and URL that motivated it.
- Keep passing: `policy_and_politeness/tests/test_robots_rules.py`, `test_robots_policy.py`.

## References
- `0_tech_docs/journal/update-log/04_robots_rules.md`
- RFC 9309: https://www.rfc-editor.org/rfc/rfc9309.html
- Related, same day: robots meta tags were only read from the first generic tag, so a later `noindex` was missed (`update_log/05_robots_metadata.md`, commit `feccf25`).
