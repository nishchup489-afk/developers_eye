# Fixing HTTP transport error handling

**Files involved:** `crawler/fetcher/transport.py`

## The problem

Reading, closing or opening a failed HTTP connection could raise `AttributeError` instead of the original network error. The code caught `httpcore.HTTPError`, which does not exist in httpcore 1.0.9.

## What changed

Catch the actual httpcore exception classes already listed in the HTTPX conversion table. Preserve the corresponding HTTPX timeout, connection or protocol error and its original cause.

Before: `ReadTimeout` became `AttributeError`.

After: `ReadTimeout` becomes `httpx.ReadTimeout`, so the coordinator can defer and retry the request.

## Verification

The fetcher regression suite checks streaming errors, response closure and HTTPX exception conversion. No live HTTP or database access is required.
