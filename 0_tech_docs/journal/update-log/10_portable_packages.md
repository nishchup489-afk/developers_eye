# Fixing machine-specific and circular package dependencies

**Files involved:** backend/crawler project files and locks, backend reporting services/API, crawler report compatibility modules, setup README and regression tests.

## The problem

Both projects depended on each other through an absolute `C:/Users/nishc/...` path. Another checkout could not resolve those paths. The backend also imported crawler implementation modules just to read reports.

## What changed

Move read-only reporting and inspection into backend services, which already own the models and database. Keep the existing crawler report commands as compatibility entry points. The crawler depends on the backend through `../backend`; the backend no longer depends on the crawler.

Before: backend → crawler → backend, tied to one Windows directory.

After: crawler → backend. Install the repository at any path using Poetry. The backend can serve reporting without importing the crawler package.

## Verification

Poetry validation, regenerated locks, wheel metadata and an API import with crawler imports blocked check the package boundary. Existing crawler and authenticated monitoring tests check compatibility.
