# Adding configurable JSON API ingestion

**Files involved:** `parser/api`, source discovery, worker dispatch, JSON/ingestion tests and `parser/docs/json_api.md`.

## The problem

API sources had no seed-to-worker ingestion path, and arbitrary JSON records could not be mapped to the shared document schema.

## What changed

Add a bounded JSON parser with configurable collection, field and pagination paths; plain text or HTML bodies; validated record URLs and dates; duplicate URL handling; and strict JSON/config checks. Seed api targets and run imported records through source scope filtering, robots headers, processing and the existing finalizer. Document source registration, configuration, pagination, supported shapes and public-GET limitations outside the update log.

## Verification

All 52 tests in `crawler/tests` pass, including new mapping, malformed input, pagination, source seeding and real parser/processor worker-dispatch cases. Full-suite database and standalone DNS checks are being run separately with their required setup.
