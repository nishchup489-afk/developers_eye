# Running the frontend tests

What each test checks is in [test_case.md](test_case.md).

These are plain Node scripts using `node:assert`. Each prints `PASS ...` lines and stops on the first failure. Run them from `frontend/`.

## Unit tests (no build needed)

```powershell
npm run test:admin:unit
```

Runs `admin-unit.mjs` and `crawler-monitor-unit.mjs` with `--experimental-strip-types`, so Node imports the `lib/*.ts` files directly.

## Tests that need a production build

`integration.mjs`, `admin-integration.mjs`, and `admin-routes.mjs` use the compiled app, so build first:

```powershell
npm run build
npm run test:integration
npm run test:admin
npm run test:admin:routes
```

- `test:integration` starts `next start` on ports 3181 and 3182 with a local mock search backend. Make sure those ports are free.
- `test:admin` starts `next start` on a free port with a mock crawler report API and test-only secrets.
- `test:admin:routes` loads the route handlers from `.next` without opening sockets. Set `NEXT_BUILD_DIR` if you built into another folder.

All secrets and GitHub settings are generated or faked by the scripts. No real GitHub or backend is contacted.

## Admin dashboard preview

`preview-crawler.mjs` is not a test. It serves the crawler dashboard with fixture data so you can look at it in a browser. It expects a build in `.next-crawler-monitor`:

```powershell
$env:NEXT_BUILD_DIR = ".next-crawler-monitor"
npm run build
node tests/preview-crawler.mjs
```

Then open `http://127.0.0.1:3457/__test_session`. It uses ports 3457, 3458, and 3459. Stop it with Ctrl+C.

## Fixtures

`fixtures/crawler-report.mjs` and `fixtures/crawler-monitor.mjs` hold synthetic data for these tests only. The app never imports them.
