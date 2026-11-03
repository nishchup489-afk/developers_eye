# Completing XML sitemap parsing

**Files involved:** `parser/sitemap.py`, `tests/test_sitemap.py`, `parser/docs/sitemap.md`, `pyproject.toml` and `poetry.lock`.

## The problem

Sitemap parsing existed only as uncommitted local work. Its entry limit counted unique valid URLs, allowing duplicate or invalid entries to bypass it. Compressed sitemaps and namespace-extension locations also needed explicit handling.

## What changed

Complete the existing parser with raw-entry counting, bounded gzip decoding, DTD rejection and namespace-aware locations. Preserve separate page and child-sitemap results. Add explanatory documentation in the parser docs directory and lock the existing defusedxml dependency.

## Verification

All 12 sitemap tests pass without network or PostgreSQL. `poetry -C crawler check --lock` passes.
