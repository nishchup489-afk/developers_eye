# Reconciling the local and remote ingestion histories

**Files involved:** the Git merge history, `seed/seed.py`, tracked crawl logs and the existing ingestion files.

## The problem

Remote-only publishing left the local checkout behind. A subsequent local commit recorded the same ingestion implementation, so local main had one separate commit while remote main had five. The code matched after normalizing line endings, but a normal push was rejected because the histories had diverged.

## What changed

Create an actual merge commit with both the remote ingestion head and the local commit as parents. Keep the remote normalized ingestion files, preserve the local Windows selector-loop seeding change and tracked crawl logs, and retain the test-artifact ignore rule. No ingestion implementation is discarded or duplicated.

## Verification

Compare every changed code/document file against the common ancestor and both branch tips. The only distinct application change is the local Windows seed entry point. Scan tracked source/docs for conflict markers and run the ingestion test suite plus source-registry loading without database writes.
