# Developer’s Eye frontend

Responsive Next.js search frontend with a custom GSAP eye illustration, staggered entrances, source filters, shareable queries, browser-local saved results, keyboard shortcuts, and reduced-motion support.

## Run

```sh
npm install
npm run dev
```

Open http://localhost:3000. No environment variables are required for the labeled demo playground. It uses a small curated collection, not live third-party search.

To connect a future FastAPI backend, copy `.env.example` to `.env.local`, set `BACKEND_URL=http://127.0.0.1:8000`, and restart. The backend must implement the documented GET /search contract. The existing backend directory is a scaffold and was not modified.

## Checks

```sh
npm run lint
npm run build
npm run test:integration
```

Integration checks require the production build and start isolated local Next.js servers plus a mock upstream. No actual backend or provider credentials are used.

## Documentation

Visit `/docs` for the API overview or read [the full API and connector reference](public/api-reference.md). It distinguishes implemented frontend endpoints from all proposed public/admin backend routes and provider connector contracts.

## Architecture

`app/page.tsx` passes server configuration mode to the interactive search component. The browser calls same-origin `/api/search`; the route reads BACKEND_URL and forwards validated searches server-side. No provider credentials are exposed. Failed live requests return errors rather than demo results.

The UI has intentionally no account system, dashboard, crawl controls, or fake analytics. Saved items live in this browser’s localStorage. Query suggestions are static shortcuts. Source tabs filter the received result collection.

The landing page centers the animated eye illustration, wordmark, and rounded search field in a full-height first screen. The source cards begin below the viewport on desktop and mobile, accessible by scrolling or the sources navigation link. Searches and suggestions open `/search?q=...`; source cards also pass a `source` filter. Results have a compact search field, source filters, and bookmarks, without the landing hero or source cards. Saved items open `/search?saved=1`. Query URLs support refresh and browser history; legacy `/?q=...` links redirect to the results page. The eye illustration lives in `components/brand-eye.tsx` as a reusable brand asset. The four source cards are Docs, GitHub, Discussions, and Articles; Discussions groups Stack Overflow and Reddit locally while preserving their separate API source values. Bookmarks remain local to this browser.
