# Cleaning the frontier model whitespace

**File involved:** `backend/src/backend/models/crawler_frontier.py`.

## The problem

A trailing whitespace-only line remained in the frontier model and failed the final diff check.

## What changed

Remove trailing spaces and normalize the file's line endings. No model fields or behavior changed.

## Verification

The repository diff check passes. No additional behavioral tests were needed for whitespace removal.
