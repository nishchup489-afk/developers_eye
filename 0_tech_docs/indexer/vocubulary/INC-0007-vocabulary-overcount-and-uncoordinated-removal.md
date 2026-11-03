---
id: INC-0007
title: Vocabulary bulk additions repeat and one removal path skips the mutex
status: open
date: '2026-11-02'
severity: high
area: indexer
feature: vocubulary
code:
- crawler/src/indexer/vocabulary.py
- crawler/src/indexer/writer.py
- crawler/tests/indexer/test_vocabulary.py
fix_commits: []
related:
- ADR-0002
- ADR-0036
- EXP-0006
---

# INC-0007: Vocabulary bulk additions repeat and one removal path skips the mutex

## Signature

`synchronize_vocabulary()` rebuilds and inserts the entire added-term batch inside the loop over each added term; `remove_search_index()` takes the document lock without `lock_vocabulary()`.

## Summary

These current defects are already noted in ADR-0002 and are confirmed by source inspection at the baseline. They can corrupt derived frequency counts or undermine rebuild coordination. The size of any live database drift has not been measured.

## Expected vs actual

- Expected: A document adding K unique terms increments each term once; every vocabulary-changing transaction follows the same mutex-before-document order.
- Actual: For K newly added terms, the full K-term batch executes K times, incrementing each term K times. The indexer removal entry point bypasses the advisory mutex.

## Root cause

The attempted batching was nested at the wrong level. The shared removal helper does not acquire the mutex itself, so every caller must satisfy the locking precondition; the indexer removal caller does not.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

**Not repaired in this documentation PR.** Move one sorted added-term batch outside the per-term loop and preserve deterministic locking for decrements. Acquire the vocabulary mutex before document locks on the missing removal path. Verify concurrent writers/deletions/rebuild and a multi-term lifecycle, then recount with writers stopped. A recount alone will drift again if the buggy increment loop resumes.

## Prevention

- Regression test: add two new terms to one document; each DF becomes exactly 1, remains 1 on unchanged reindex, and reaches 0 after removal.
- Concurrency: overlap deletion, upsert and rebuild using independent real PostgreSQL sessions.
- Monitoring: compare a sample/full vector-derived recount with stored counts; a nonnegative constraint cannot detect overcount.

## Rules for future changes

- Test multi-term additions, not just a one-term delta.
- Acquire the shared mutex before document locks on every index deletion path.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. This is a code-proven defect report, not a claim that a production incident was observed.

- [`crawler/src/indexer/vocabulary.py`](../../../crawler/src/indexer/vocabulary.py)
- [`crawler/src/indexer/writer.py`](../../../crawler/src/indexer/writer.py)
- [`crawler/tests/indexer/test_vocabulary.py`](../../../crawler/tests/indexer/test_vocabulary.py)
