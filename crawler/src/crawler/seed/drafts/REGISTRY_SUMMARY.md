# Source registry draft

Built from nish's 197-row draft (2026-11-07), with fixes and additions. Nothing here is enabled: every row has `is_enabled: false` so you can turn sources on in batches.

Files in this folder:

- `documentation.json`, `blogs.json`, `apis.json`: seedable rows in the exact `SourceCreate` shape (`kind` is website / rss / api). Copy into `../sources/` when you want them seeded. They sit in `drafts/` because `seed.py` loads every `*.json` in `sources/`.
- `offline_datasets.json`: the Stack Overflow dump. Not seedable; it needs an importer.
- `github_issue_repos.json`: 500 repo allowlist for the GitHub issues source (from GitHub search, top by stars, filtered).
- `source_registry_draft.tsv`: your column layout plus `version_pin`, `est_docs`, `max_docs`.
- `build_registry.py`: the generator. Edit the tables in it and run `python build_registry.py` (no arguments) instead of hand-editing JSON. It validates every row first and writes nothing if any check fails.
- `inputs/`: the generator's checked-in inputs (nish's original draft and the GitHub repo snapshot), so a clean checkout rebuilds the same files.

## Totals

| Tier | Sources | Est. docs | Sum of caps (max_docs) | MVP sources | MVP est. docs |
|---|---:|---:|---:|---:|---:|
| Tier 1: core language and platform docs | 39 | 94,200 | 142,970 | 30 | 88,000 |
| Tier 2: frameworks and libraries | 107 | 75,265 | 128,670 | 36 | 23,775 |
| Tier 3: infrastructure and tools | 75 | 99,481 | 157,005 | 5 | 4,520 |
| Tier 4: engineering blogs (RSS) | 166 | 4,830 | 159,600 | 11 | 330 |
| Special sources: discussions | 3 | 500,100 | 510,000 | 0 | 0 |
| **All** | **390** | **773,876** | **1,098,245** | **82** | **116,625** |

Reading the numbers: est. docs are my rough page counts, not measured. Blogs show ~30 docs each because an RSS feed only lists recent posts; turning on sitemap backfill per blog would add roughly 300 each (~50K total). Special sources count the Stack Overflow dump at the local-corpus size (500K) and GitHub issues at 100K.

- **Prototype (cloud seed):** the `suggested_mvp = yes` rows come to about **116,625 docs**, inside the 100-200K target.
- **Local corpus:** all tiers 1-3 are ~270K docs; add blogs with backfill (~50K), GitHub issues (~100K) and the filtered Stack Overflow dump (~500K) for roughly **900K**, inside the 500K-1M target.

## What I changed in your draft

- Hostnames: the markdown-link-mangled hosts (`[www.w3.org](...)`) are plain hostnames now.
- Real path scopes instead of `/` for react, angular, webpack, dart, docker, pkg.go.dev, fastapi, typer, polars, solid, redux-toolkit, react-router, elasticsearch (was all of `/docs/`), net-docs.
- Kept `/` where the host only serves docs (nestjs, zod, httpx, nats, flutter, homebrew, rails guides) and for SQLite. SQLite's docs are flat files like `/lang_select.html`, and `allowed_path_prefixes` matches whole path segments, so `/lang_` can't work. It uses depth 2 from docs.html plus a cap instead.
- Where I narrowed a scope I also moved `base_url` inside it (fastapi to /learn/, docker to /get-started/, typer, polars, solid). `discovery.py` silently drops a seed that falls outside its own prefixes, so the generator now checks this for every row.
- Overlaps removed: net-docs excludes `/dotnet/csharp/` (own source) and `/dotnet/api/`; cpp-reference is `/w/cpp` and c-reference is `/w/c` (no collision, prefix match is per segment); svelte-docs is `/docs/svelte/` so it doesn't swallow sveltekit; remix-docs disabled as a duplicate of React Router 7; rust-std is `/std/` only (not `/stable/std/`).
- Renamed `version-typescript` to `typescript-docs`.
- Version pins: Java 25 LTS, .NET 10 LTS, MySQL 8.4 LTS, OpenSSL 3.5 LTS (was `/master/`), Hibernate `/current/` (was every version), systemd `/latest/`, JUnit moved to docs.junit.org, PyTorch moved to docs.pytorch.org, bun.sh to bun.com (old hosts kept in `allowed_hosts` so redirects pass).
- http-rfcs now lists exact RFC files (9110-9114 plus WebSocket, OAuth 2, JWT, TLS 1.3, URI) instead of all of `/rfc/`.
- apple-swiftui-docs disabled: developer.apple.com/documentation is a JavaScript app and returns an empty page to an HTML fetch.
- Blog rows now point `base_url` at the real feed URL (the RSS parser needs the feed, not the homepage), with `follow_entry_links: true` and `max_depth: 1`.
- The `stack-overflow-dump` and `curated-engineering-rss` rows didn't fit the schema (`dataset` and `manifest` aren't valid kinds). The dump moved to `offline_datasets.json`; the manifest is replaced by the 168 real feed rows.
- Added 56 docs sources (web.dev, dev.java, more docs.rs crates, React Native, Expo, Electron, Ruff, mypy, Keras, JAX, Vault, Istio, Argo CD, Cloudflare, Supabase, Firebase, DuckDB, gRPC, OWASP cheat sheets, DigitalOcean tutorials and others) and 138 blog feeds.

## Review fixes (2026-11-08)

- **Seeds that redirected out of scope:** C and C++ now seed `/c` and `/cpp` (cppreference moved off `/w/`; the old prefixes stay allowed so redirects land in scope). Django seeds `/en/6.1/` because `/en/stable/` redirects there. Redux Toolkit moved to `redux.js.org/toolkit/` and Pydantic to `pydantic.dev/docs/validation/latest/`; their hosts, seeds and scopes changed together.
- **AWS:** each aws-* row lists its own guide sitemap in `sitemap_urls` and has `discover_sitemaps: false`. The host-wide index lists ~13,900 child sitemaps and would eat each source's budget. The same switch-off now applies to every shared or very large host (learn.microsoft.com, cloud.google.com, docs.rs, doc.rust-lang.org, developer.hashicorp.com, huggingface.co, pkg.go.dev and others; see `SHARED_HOSTS`).
- **AWS crawl delay:** `politeness_policy.py` now has `HOST_MIN_INTERVAL_SECONDS` with `docs.aws.amazon.com: 5.0`. Both the in-memory limiter and the shared PostgreSQL limiter use it. The robots parser still ignores `Crawl-delay`, so hosts that ask for one are listed there by hand.
- **Blocked (excluded from counts):** swift-docs (DocC page, empty body), dan-luu and vercel-blog (feeds over the 2 MB parser limit), planet-python and planet-postgresql (every entry is on another host). microsoft-devblogs is disabled because its `/` scope swallowed three product feeds.
- **Stack Overflow sample:** the mapping now keeps `content_license` (posts carry CC BY-SA 2.5, 3.0 or 4.0), score, tags and ids in document metadata, via a new `metadata_fields` option in the JSON API parser. `parse_record_date` now reads Unix seconds. The estimate is 100 docs, the one page reachable until pagination works.
- **One owner per URL:** go.dev/blog/, react.dev/blog and nextjs.org/blog now belong only to their feeds. inside-rust and the Baeldung feed were dropped because other rows already cover them. DuckDB's blog is scoped to its year paths, and the Flutter feed moved to blog.flutter.dev. The generator now fails when two live rows can admit the same host and path.

## robots.txt spot check (20 hosts)

- Allowed for a generic crawler: MDN, docs.python.org (blocks only EOL `/3.x/` trees), learn.microsoft.com, php.net, pkg.go.dev, docs.rs, sqlite.org, docs.github.com (no rules at all), docs.aws.amazon.com, cloud.google.com, huggingface.co, digitalocean.com, man7.org, kubernetes.io, medium.com.
- **docs.aws.amazon.com sets `Crawl-delay: 5`.** Six aws-* sources share that host. The 5-second gap is now enforced per host in the crawler (see Review fixes).
- **en.cppreference.com** allows crawling but says `Content-Signal: search=yes, ai-train=no` and blocks ~35 named AI bots. Search indexing is fine; don't let the corpus feed model training.
- **medium.com** allows generic crawlers but blocks named AI bots. Use your own user agent and a low rate.
- Couldn't verify: docs.oracle.com (59 KB file, only partly readable), www.gnu.org (refused the checker), stackoverflow.com (blocked the checker), wiki.archlinux.org (bot wall, so I left the Arch wiki out).
- The other ~370 hosts are unchecked. Every row has `robots_reviewed: false` and every feed has `feed_url_verified: false`. Feed URLs are from memory, so expect a few to 404 on first run.

## Crawler gaps this list runs into

- **No deny list.** Hugging Face, ClickHouse, Scala docs and TensorFlow mix versioned or translated trees under the same prefix. Their caps bound the damage, but an `excluded_path_prefixes` key (plus stripping `?hl=` and `?view=` in the URL normalizer) would fix it properly.
- **One base_url per source.** That is why AWS, GCP, Azure and docs.rs are split into many rows. A `seed_urls` list in config would let them collapse.
- **Shared hosts.** doc.rust-lang.org (~32K of caps), learn.microsoft.com (~23K), docs.rs (~13K) and docs.aws.amazon.com (~13K) each serve several sources. `max_pages` is per source, so a per-host cap still needs adding.
- **GitHub issues API:** no auth header support (60 requests/hour without a token), pagination is in the `Link` header which `next_path` can't read, and one source can only hold one repo URL. Details are in `apis.json`.
- **Stack Overflow:** the archive.org mirror stopped updating in 2024. Newer dumps come from Stack Exchange behind an account and their own terms, so read those before importing. The content license is still CC BY-SA, which means keeping author, link and license on every document.
- Existing seeded slugs (mdn, python-docs, fastapi, django, rust-book) keep their names. `seed.py` skips slugs that already exist, so new scopes for those five only take effect through `update_source`.

## Tier 1: core language and platform docs (39)

| Slug | Name | Host | Path scope | Version | Est. docs | Max docs | MVP | Notes |
|---|---|---|---|---|---:|---:|---|---|
| `mdn` | MDN Web Docs | developer.mozilla.org | `/en-US/docs/Web/ /en-US/docs/Learn_web_development/ /en-US/docs/Glossa …` | living | 14,000 | 20,000 | yes | English subtree only; exclude translated /<locale>/ paths |
| `html-standard` | WHATWG HTML Living Standard | html.spec.whatwg.org | `/multipage/` | living | 120 | 300 | yes | Multipage spec only; the single-page / file is ~15 MB, never fetch it |
| `web-css-spec` | W3C CSS specifications | www.w3.org | `/Style/CSS/` | latest REC/CR | 200 | 600 | yes | w3.org Style/CSS index links out to drafts.csswg.org and /TR/; add www.w3.org /TR/ prefixes for the specs you want |
| `http-rfcs` | HTTP Semantics and HTTP/1.1 RFCs | www.rfc-editor.org | `/rfc/rfc9110.html /rfc/rfc9111.html /rfc/rfc9112.html /rfc/rfc9113.htm …` | per-RFC | 10 | 20 | yes | Exact-file allowlist: HTTP 9110-9114, WebSocket, OAuth2, JWT, TLS 1.3, URI |
| `webassembly-core` | WebAssembly core specification | webassembly.github.io | `/spec/core/` | 2.0 | 60 | 200 | yes | Core spec only |
| `python-docs` | Python 3 documentation | docs.python.org | `/3/` | 3 (stable alias) | 2,000 | 5,000 | yes | robots.txt blocks EOL /3.x/ trees, /3/ allowed; sitemap at /sitemap.xml |
| `nodejs-docs` | Node.js API documentation | nodejs.org | `/api/ /en/learn/` | latest (current) | 250 | 1,000 | yes | /api/ is the current release; /docs/latest-vXX.x/ trees are duplicates, keep them out |
| `typescript-docs` | TypeScript Handbook | www.typescriptlang.org | `/docs/` | 5.x latest | 300 | 1,000 | yes | Renamed from version-typescript. /docs/ excludes localized /ja/docs/ etc. Add /tsconfig as a second source if needed (it is one big page) |
| `rust-book` | The Rust Programming Language Book | doc.rust-lang.org | `/book/` | stable | 110 | 300 | yes | English book only |
| `rust-std` | Rust standard library | doc.rust-lang.org | `/std/` | stable | 25,000 | 30,000 | yes | /std/ only; /stable/std/ and /nightly/ are duplicates, out of scope. Host doc.rust-lang.org shared by 5 sources, host cap 40K |
| `rust-reference` | Rust Reference | doc.rust-lang.org | `/reference/` | stable | 150 | 400 | yes | Language reference |
| `rust-by-example` | Rust By Example | doc.rust-lang.org | `/rust-by-example/` | stable | 200 | 400 | yes | Example-driven pages |
| `go-docs` | Go documentation | go.dev | `/doc/ /ref/` | latest | 400 | 1,200 | yes | Added /ref/ (spec, memory model). /blog/ belongs to the go-blog feed only, so the two sources never write the same URL |
| `go-stdlib` | Go standard library package docs | pkg.go.dev | `/std /archive /bufio /builtin /bytes /cmp /compress /container /contex …` | latest Go release | 300 | 600 | yes | Top-level std package names as exact path prefixes, so third-party module paths (/github.com/...) stay out |
| `java-docs` | Java SE Documentation | docs.oracle.com | `/en/java/javase/25/` | JDK 25 LTS | 6,000 | 10,000 | yes | Pinned to 25 LTS. robots.txt is 59 KB and was only partly readable; re-check /en/java/javase/25/ before enabling |
| `kotlin-docs` | Kotlin documentation | kotlinlang.org | `/docs/ /api/core/kotlin-stdlib/` | latest | 3,000 | 6,000 | yes | Added stdlib API reference |
| `swift-docs` | Swift documentation | docs.swift.org | `/swift-book/` | Swift 6.x | 0 | 200 | no | **blocked_empty_body**. Blocked: the Swift book is a DocC app and the HTML parser extracts an empty body. Workable input: the book's markdown in github.com/swiftlan |
| `cpp-reference` | C++ reference | en.cppreference.com | `/cpp /w/cpp` | living | 5,000 | 8,000 | yes | /w/cpp now redirects to /cpp, so the seed is /cpp and both prefixes are allowed (old links still redirect in). Doesn't overlap c-reference.  |
| `c-reference` | C reference | en.cppreference.com | `/c /w/c` | living | 1,200 | 2,000 | yes | /w/c now redirects to /c. Prefix /c matches /c/... only (segment match), so no collision with /cpp |
| `csharp-docs` | C# language docs | learn.microsoft.com | `/en-us/dotnet/csharp/` | C# 14 / .NET 10 | 1,500 | 3,000 | yes | C# only |
| `net-docs` | .NET APIs and fundamentals | learn.microsoft.com | `/en-us/dotnet/fundamentals/ /en-us/dotnet/core/ /en-us/dotnet/standard …` | .NET 10 LTS | 8,000 | 12,000 | yes | Excludes /en-us/dotnet/csharp/ (own source) and /en-us/dotnet/api/ (200K+ API pages; add later with its own cap). learn.microsoft.com host s |
| `php-docs` | PHP Manual | www.php.net | `/manual/en/` | 8.x | 12,000 | 15,000 | yes | English manual only |
| `ruby-docs` | Ruby official documentation | docs.ruby-lang.org | `/en/master/` | master (pin to latest x.y when verified) | 3,000 | 5,000 | yes | Pick one version tree only; /en/3.x/ trees are near-duplicates |
| `dart-docs` | Dart documentation | dart.dev | `/language /libraries /tools /effective-dart /guides /interop /null-saf …` | Dart 3.x | 400 | 1,000 | yes | Allowlist /language and /libraries; exclude unrelated site paths |
| `bash-manual` | GNU Bash Manual | www.gnu.org | `/software/bash/manual/` | 5.x | 200 | 400 | yes | gnu.org robots.txt could not be read by our checker (it refused automated fetch); verify before enabling |
| `gnu-coreutils` | GNU Coreutils Manual | www.gnu.org | `/software/coreutils/manual/` | 9.x | 300 | 500 | yes | Same gnu.org robots caveat as bash-manual |
| `postgres-docs` | PostgreSQL Documentation | www.postgresql.org | `/docs/current/` | current (18) | 1,200 | 3,000 | yes | Current version only; pin version in snapshots |
| `sqlite-docs` | SQLite Documentation | www.sqlite.org | `/` | 3.x | 500 | 1,200 | yes | Kept '/' on purpose: SQLite docs are flat files (/lang_*.html, /c3ref/*). The scope only matches whole path segments, so '/lang_' can't work |
| `git-docs` | Git Reference | git-scm.com | `/docs /book/en/v2` | latest | 800 | 1,500 | yes | Added English Pro Git book |
| `web-dev` | web.dev guides | web.dev | `/learn /articles /explore` | living | 1,500 | 2,500 | yes | Google's web guides (performance, a11y, PWA) |
| `rust-nomicon` | Rustonomicon | doc.rust-lang.org | `/nomicon/` | stable | 60 | 150 | no |  |
| `rust-async-book` | Async Rust book | rust-lang.github.io | `/async-book/` | latest | 40 | 100 | no |  |
| `java-tutorials` | dev.java Learn | dev.java | `/learn/` | latest | 300 | 600 | yes | Official Java tutorials |
| `gnu-make` | GNU Make Manual | www.gnu.org | `/software/make/manual/` | 4.x | 200 | 300 | no | gnu.org robots caveat |
| `gnu-gawk` | GNU Awk Manual | www.gnu.org | `/software/gawk/manual/` | 5.x | 300 | 400 | no | gnu.org robots caveat |
| `scala-docs` | Scala documentation | docs.scala-lang.org | `/` | 3.x | 1,500 | 2,500 | no | Has /ja/, /zh-cn/ trees; cap until a deny list exists |
| `elixir-docs` | Elixir documentation | hexdocs.pm | `/elixir/` | latest | 400 | 800 | no | hexdocs.pm/elixir/ is current; versioned trees at /elixir/1.x/ |
| `python-peps` | Python PEPs | peps.python.org | `/` | living | 700 | 1,000 | no |  |
| `linux-kernel-docs` | Linux kernel documentation | docs.kernel.org | `/` | latest | 3,000 | 5,000 | no | Translations under /translations/; cap |

## Tier 2: frameworks and libraries (107)

| Slug | Name | Host | Path scope | Version | Est. docs | Max docs | MVP | Notes |
|---|---|---|---|---|---:|---:|---|---|
| `react-docs` | React | react.dev | `/learn /reference` | 19.x | 250 | 700 | yes | /blog belongs to the react-blog feed |
| `nextjs-docs` | Next.js | nextjs.org | `/docs /learn` | latest (App Router) | 600 | 1,800 | yes | /docs/pages/ is the legacy router; keep or drop. /blog belongs to the nextjs-blog feed |
| `vue-docs` | Vue | vuejs.org | `/guide/ /api/ /tutorial/ /examples/` | 3.x | 200 | 500 | yes | Official guide |
| `angular-docs` | Angular | angular.dev | `/overview /guide /api /tutorials /reference /tools /best-practices /cl …` | latest | 1,500 | 3,000 | yes | Allowlist /guide and /api |
| `svelte-docs` | Svelte | svelte.dev | `/docs/svelte/` | 5.x | 150 | 400 | yes | Narrowed to /docs/svelte/ so it doesn't overlap sveltekit-docs |
| `sveltekit-docs` | SvelteKit | svelte.dev | `/docs/kit/` | 2.x | 100 | 300 | yes | SvelteKit docs only |
| `tailwind-docs` | Tailwind CSS | tailwindcss.com | `/docs` | 4.x | 250 | 500 | yes | Utilities and configuration |
| `vite-docs` | Vite | vite.dev | `/guide/ /config/ /plugins/ /blog/` | latest | 80 | 300 | yes | Official docs |
| `webpack-docs` | webpack | webpack.js.org | `/concepts /configuration /api /guides /loaders /plugins /migrate` | 5.x | 400 | 800 | yes | Allowlist /concepts /configuration /guides and /api |
| `astro-docs` | Astro | docs.astro.build | `/en/` | 5.x | 500 | 1,000 | yes | English content |
| `nuxt-docs` | Nuxt | nuxt.com | `/docs` | 4.x | 400 | 1,000 | yes | nuxt.com/docs is current; /docs/3.x/ duplicates if present |
| `react-router-docs` | React Router | reactrouter.com | `/home /start /api /tutorials /explanation /how-to /community /upgradin …` | 7.x | 300 | 800 | yes | RR7 is where Remix v2 went; this replaces remix-docs |
| `solid-docs` | SolidJS | docs.solidjs.com | `/quick-start /concepts /reference /guides /configuration /advanced-con …` | 1.x | 300 | 600 | yes | Docs only |
| `redux-toolkit-docs` | Redux Toolkit | redux.js.org | `/toolkit/` | 2.x | 150 | 400 | yes | redux-toolkit.js.org now 302s to redux.js.org/toolkit/ |
| `tanstack-query-docs` | TanStack Query | tanstack.com | `/query/latest/docs/` | v5 (latest) | 300 | 600 | yes | All frameworks under /latest/docs/; restrict to /framework/react/ if dupes hurt |
| `remix-docs` | Remix | remix.run | `/docs/en/main` | v2 (legacy) | 0 | 200 | no | **duplicate_disabled**. Disabled: Remix v2 merged into React Router 7, covered by react-router-docs |
| `playwright-docs` | Playwright | playwright.dev | `/docs/` | latest | 400 | 800 | later | English test docs |
| `vitest-docs` | Vitest | vitest.dev | `/guide/ /api/ /config/` | latest | 150 | 400 | later | Guides and API |
| `jest-docs` | Jest | jestjs.io | `/docs/` | current | 150 | 300 | later | /docs/next/ and /docs/29.x/ are versioned dupes; jestjs.io/docs/ is current |
| `cypress-docs` | Cypress | docs.cypress.io | `/app/ /api/` | latest | 500 | 1,000 | later | App testing docs |
| `testing-library-docs` | Testing Library | testing-library.com | `/docs/` | latest | 120 | 300 | later | Official docs |
| `storybook-docs` | Storybook | storybook.js.org | `/docs` | latest | 400 | 800 | later | Component-development docs |
| `eslint-docs` | ESLint | eslint.org | `/docs/latest/` | 9.x | 600 | 1,000 | later | Current rules and guides |
| `prettier-docs` | Prettier | prettier.io | `/docs/` | 3.x | 40 | 100 | later | Official docs |
| `django` | Django | docs.djangoproject.com | `/en/6.1/ /en/stable/` | 6.1 | 800 | 2,000 | yes | /en/stable/ redirects to /en/6.1/, so the seed is the pinned version; bump both when 6.2 ships. Already seeded with no path prefix; seed.py  |
| `flask-docs` | Flask | flask.palletsprojects.com | `/en/stable/` | stable | 150 | 300 | yes | Stable docs |
| `fastapi` | FastAPI | fastapi.tiangolo.com | `/learn/ /tutorial/ /advanced/ /reference/ /how-to/ /deployment/ /fasta …` | latest | 300 | 600 | yes | English prefixes only (translations live under /es/, /zh/, /ja/ ...). Already seeded; apply via update_source |
| `sqlalchemy-docs` | SQLAlchemy | docs.sqlalchemy.org | `/en/20/` | 2.0 | 600 | 1,500 | yes | SQLAlchemy 2.x docs |
| `pydantic-docs` | Pydantic | pydantic.dev | `/docs/validation/latest/` | 2.x latest | 300 | 600 | yes | docs.pydantic.dev/latest/ now 302s to pydantic.dev/docs/validation/latest/ |
| `pandas-docs` | pandas | pandas.pydata.org | `/docs/` | stable | 4,000 | 6,000 | yes | Guide and reference |
| `numpy-docs` | NumPy | numpy.org | `/doc/stable/` | stable | 3,500 | 5,000 | yes | Stable reference |
| `scipy-docs` | SciPy | docs.scipy.org | `/doc/scipy/` | stable | 3,000 | 4,500 | yes | Stable SciPy docs |
| `pytest-docs` | pytest | docs.pytest.org | `/en/stable/` | stable | 250 | 500 | yes | Stable pytest docs |
| `requests-docs` | Requests | requests.readthedocs.io | `/en/latest/` | latest | 30 | 100 | yes | Official Requests docs |
| `httpx-docs` | HTTPX | www.python-httpx.org | `/` | latest | 50 | 150 | yes | '/' is fine: docs-only host |
| `celery-docs` | Celery | docs.celeryq.dev | `/en/stable/` | stable | 300 | 800 | yes | Stable docs |
| `polars-docs` | Polars | docs.pola.rs | `/user-guide/ /api/python/stable/` | stable | 1,500 | 3,000 | yes | Allowlist Python user guide and API |
| `matplotlib-docs` | Matplotlib | matplotlib.org | `/stable/` | stable | 3,000 | 4,000 | yes | Current docs |
| `beautifulsoup-docs` | Beautiful Soup | www.crummy.com | `/software/BeautifulSoup/bs4/doc/` | 4.x | 5 | 20 | yes | Specific bs4 documentation |
| `jinja-docs` | Jinja | jinja.palletsprojects.com | `/en/stable/` | stable | 40 | 100 | yes | Current docs |
| `rich-docs` | Rich | rich.readthedocs.io | `/en/stable/` | stable | 50 | 150 | yes | Rich docs |
| `click-docs` | Click | click.palletsprojects.com | `/en/stable/` | stable | 50 | 150 | yes | Current docs |
| `typer-docs` | Typer | typer.tiangolo.com | `/tutorial/ /features/ /typer-cli/ /alternatives/ /virtual-environments …` | latest | 120 | 300 | yes | English prefixes only, same pattern as fastapi |
| `pillow-docs` | Pillow | pillow.readthedocs.io | `/en/stable/` | stable | 150 | 300 | yes | Image processing docs |
| `aiohttp-docs` | aiohttp | docs.aiohttp.org | `/en/stable/` | stable | 100 | 300 | yes | Stable docs |
| `express-docs` | Express | expressjs.com | `/en/` | 5.x | 150 | 400 | later | /en/ is English; /en/4x/ is a versioned dupe |
| `nestjs-docs` | NestJS | docs.nestjs.com | `/` | latest | 250 | 500 | later | '/' is fine: docs-only host |
| `prisma-docs` | Prisma | www.prisma.io | `/docs` | latest | 1,200 | 2,000 | later | ORM docs |
| `fastify-docs` | Fastify | fastify.dev | `/docs/latest/` | latest | 150 | 300 | later | Current docs |
| `zod-docs` | Zod | zod.dev | `/` | 4.x | 40 | 100 | later | '/' is fine: docs-only host |
| `typeorm-docs` | TypeORM | typeorm.io | `/docs/` | latest | 100 | 300 | later | Core docs |
| `drizzle-docs` | Drizzle ORM | orm.drizzle.team | `/docs/` | latest | 400 | 800 | later | ORM docs |
| `mongoose-docs` | Mongoose | mongoosejs.com | `/docs/` | 8.x | 200 | 500 | later | Current docs |
| `bun-docs` | Bun | bun.com | `/docs` | latest | 400 | 800 | later | bun.sh redirects to bun.com; both hosts allowed so redirects pass |
| `deno-docs` | Deno | docs.deno.com | `/runtime/ /examples/ /deploy/` | 2.x | 600 | 1,500 | later | Official runtime docs |
| `spring-docs` | Spring Framework | docs.spring.io | `/spring-framework/reference/` | 7.x (current) | 600 | 1,500 | later | Official framework docs |
| `springboot-docs` | Spring Boot | docs.spring.io | `/spring-boot/reference/` | 4.x (current) | 500 | 1,200 | later | Boot docs |
| `hibernate-docs` | Hibernate ORM | docs.jboss.org | `/hibernate/orm/current/` | current | 50 | 200 | later | Pinned to /current/; the bare /hibernate/orm/ tree has every version since 3.x |
| `quarkus-docs` | Quarkus | quarkus.io | `/guides/` | latest | 400 | 800 | later | Guides |
| `micronaut-docs` | Micronaut | docs.micronaut.io | `/latest/guide/` | latest | 20 | 100 | later | Guide |
| `junit-docs` | JUnit 5 | docs.junit.org | `/current/` | current (JUnit 6) | 30 | 100 | later | JUnit docs moved to docs.junit.org; old junit.org/junit5/docs URL redirects |
| `rails-docs` | Ruby on Rails | guides.rubyonrails.org | `/` | 8.x | 80 | 200 | later | '/' is fine: guides-only host. Consider api.rubyonrails.org as a tier-3 extra |
| `laravel-docs` | Laravel | laravel.com | `/docs` | current | 100 | 300 | later | laravel.com/docs redirects to the current major (/docs/12.x or 13.x); allow both via /docs |
| `symfony-docs` | Symfony | symfony.com | `/doc/current/` | current | 1,000 | 2,000 | later | Symfony current docs |
| `tokio-docs` | Tokio | docs.rs | `/tokio/latest/tokio/` | latest | 3,000 | 4,000 | later | docs.rs allowlist specific crate only |
| `serde-docs` | Serde | docs.rs | `/serde/latest/serde/` | latest | 300 | 600 | later | docs.rs allowlist specific crate only |
| `axum-docs` | Axum | docs.rs | `/axum/latest/axum/` | latest | 800 | 1,500 | later | docs.rs allowlist specific crate only |
| `clap-docs` | clap | docs.rs | `/clap/latest/clap/` | latest | 800 | 1,500 | later | docs.rs allowlist specific crate only |
| `flutter-docs` | Flutter | docs.flutter.dev | `/` | stable | 1,000 | 2,000 | later | '/' is fine: docs-only host |
| `android-docs` | Android Developers | developer.android.com | `/develop /guide /topic /training /kotlin` | latest | 6,000 | 10,000 | later | Curated Android SDK docs only |
| `apple-swiftui-docs` | SwiftUI | developer.apple.com | `/documentation/swiftui` | n/a | 0 | 1 | no | **blocked_js_rendered**. Disabled: developer.apple.com/documentation is a JS app, HTML fetch returns an empty shell. Alternative: its JSON at /tutorials/data/documen |
| `pytorch-docs` | PyTorch | docs.pytorch.org | `/docs/stable/ /tutorials/` | stable | 3,800 | 5,000 | later | pytorch.org/docs redirects to docs.pytorch.org; added /tutorials/ |
| `tensorflow-docs` | TensorFlow | www.tensorflow.org | `/api_docs/python/ /guide/ /tutorials/` | 2.x stable | 8,000 | 10,000 | later | Locales use ?hl= query, so the path scope can't drop them; normalizer should strip hl= |
| `sklearn-docs` | scikit-learn | scikit-learn.org | `/stable/` | stable | 2,500 | 4,000 | later | Current stable docs |
| `hf-transformers` | Hugging Face Transformers | huggingface.co | `/docs/transformers/` | unversioned (main release) | 1,500 | 2,500 | later | Prefix also admits /docs/transformers/v4.x/, /main/ and /ja/ trees; cap keeps it bounded until a deny list exists |
| `hf-datasets` | Hugging Face Datasets | huggingface.co | `/docs/datasets/` | latest | 150 | 400 | later | Same versioned-tree caveat as hf-transformers |
| `hf-tokenizers` | Hugging Face Tokenizers | huggingface.co | `/docs/tokenizers/` | latest | 60 | 200 | later | Tokenizers library only |
| `lightning-docs` | Lightning | lightning.ai | `/docs/pytorch/stable/` | stable | 600 | 1,000 | later | PyTorch Lightning docs |
| `langchain-docs` | LangChain | docs.langchain.com | `/oss/python/langchain/` | 1.x | 600 | 1,200 | later | Python LangChain only |
| `llamaindex-docs` | LlamaIndex | docs.llamaindex.ai | `/en/stable/` | stable | 1,500 | 2,500 | later | docs.llamaindex.ai may redirect to developers.llamaindex.ai; verify host |
| `onnx-docs` | ONNX | onnx.ai | `/onnx/` | latest | 300 | 600 | later | Core docs |
| `xgboost-docs` | XGBoost | xgboost.readthedocs.io | `/en/stable/` | stable | 150 | 300 | later | Current docs |
| `anyhow-docs` | anyhow (docs.rs) | docs.rs | `/anyhow/latest/anyhow/` | latest | 40 | 100 | no | docs.rs host cap 30K across crates |
| `thiserror-docs` | thiserror (docs.rs) | docs.rs | `/thiserror/latest/thiserror/` | latest | 10 | 50 | no |  |
| `reqwest-docs` | reqwest (docs.rs) | docs.rs | `/reqwest/latest/reqwest/` | latest | 300 | 600 | no |  |
| `serde-json-docs` | serde_json (docs.rs) | docs.rs | `/serde_json/latest/serde_json/` | latest | 150 | 300 | no |  |
| `sqlx-docs` | sqlx (docs.rs) | docs.rs | `/sqlx/latest/sqlx/` | latest | 800 | 1,500 | no |  |
| `tracing-docs` | tracing (docs.rs) | docs.rs | `/tracing/latest/tracing/` | latest | 300 | 600 | no |  |
| `hyper-docs` | hyper (docs.rs) | docs.rs | `/hyper/latest/hyper/` | latest | 300 | 600 | no |  |
| `rand-docs` | rand (docs.rs) | docs.rs | `/rand/latest/rand/` | latest | 200 | 400 | no |  |
| `regex-docs` | regex (docs.rs) | docs.rs | `/regex/latest/regex/` | latest | 100 | 200 | no |  |
| `chrono-docs` | chrono (docs.rs) | docs.rs | `/chrono/latest/chrono/` | latest | 300 | 600 | no |  |
| `react-native-docs` | React Native | reactnative.dev | `/docs/ /blog/` | latest | 600 | 1,200 | no | /docs/next/ and /docs/0.7x/ are versioned dupes |
| `expo-docs` | Expo | docs.expo.dev | `/` | latest | 1,500 | 2,500 | no |  |
| `electron-docs` | Electron | www.electronjs.org | `/docs/latest/` | latest | 500 | 1,000 | no |  |
| `sass-docs` | Sass | sass-lang.com | `/documentation/` | latest | 300 | 500 | no |  |
| `bootstrap-docs` | Bootstrap | getbootstrap.com | `/docs/5.3/` | 5.3 | 100 | 200 | no |  |
| `d3-docs` | D3 | d3js.org | `/` | 7.x | 150 | 300 | no |  |
| `mypy-docs` | mypy | mypy.readthedocs.io | `/en/stable/` | stable | 100 | 200 | no |  |
| `ruff-docs` | Ruff | docs.astral.sh | `/ruff/` | latest | 1,000 | 1,500 | no | Mostly one page per lint rule |
| `keras-docs` | Keras | keras.io | `/api/ /guides/ /examples/` | 3.x | 600 | 1,000 | no |  |
| `jax-docs` | JAX | docs.jax.dev | `/en/latest/` | latest | 600 | 1,000 | no |  |
| `ktor-docs` | Ktor | ktor.io | `/docs/` | 3.x | 400 | 800 | no |  |
| `gin-docs` | Gin | gin-gonic.com | `/en/docs/` | latest | 50 | 150 | no |  |
| `gorm-docs` | GORM | gorm.io | `/docs/` | latest | 100 | 200 | no |  |
| `phoenix-docs` | Phoenix | hexdocs.pm | `/phoenix/` | latest | 300 | 500 | no |  |
| `rails-api` | Rails API reference | api.rubyonrails.org | `/` | 8.x | 3,000 | 4,000 | no |  |

## Tier 3: infrastructure and tools (75)

| Slug | Name | Host | Path scope | Version | Est. docs | Max docs | MVP | Notes |
|---|---|---|---|---|---:|---:|---|---|
| `docker-docs` | Docker | docs.docker.com | `/get-started/ /engine/ /build/ /compose/ /reference/ /manuals/ /guides …` | latest | 2,500 | 4,000 | yes | Docs subtree only |
| `kubernetes-docs` | Kubernetes | kubernetes.io | `/docs/` | latest (v1.3x) | 1,500 | 3,000 | yes | /docs/ excludes /zh-cn/docs/ etc. robots blocks /legacy/, /v1.0/, /v1.1/ |
| `helm-docs` | Helm | helm.sh | `/docs/` | 3.x/4.x | 200 | 400 | yes | Helm docs |
| `podman-docs` | Podman | docs.podman.io | `/en/latest/` | latest | 200 | 400 | yes | CLI docs |
| `terraform-docs` | Terraform | developer.hashicorp.com | `/terraform/docs /terraform/language /terraform/cli /terraform/tutorial …` | latest | 3,000 | 5,000 | later | Provider docs live on registry.terraform.io (JS app); not included |
| `opentofu-docs` | OpenTofu | opentofu.org | `/docs/` | latest | 300 | 600 | later | Official docs |
| `ansible-docs` | Ansible | docs.ansible.com | `/ansible/latest/` | latest | 8,000 | 10,000 | later | Includes collection module docs (most of the 8K). docs.ansible.com reorganized in 2025 under /projects/; verify the redirect |
| `nginx-docs` | NGINX | nginx.org | `/en/docs/` | mainline | 300 | 500 | later | Official docs |
| `caddy-docs` | Caddy | caddyserver.com | `/docs/` | 2.x | 200 | 400 | later | Caddy docs |
| `traefik-docs` | Traefik | doc.traefik.io | `/traefik/` | v3 | 400 | 800 | later | Current reverse proxy docs |
| `redis-docs` | Redis | redis.io | `/docs/latest/` | latest | 5,000 | 6,000 | later | Current docs |
| `mongodb-docs` | MongoDB | www.mongodb.com | `/docs/manual/` | current (8.x) | 2,500 | 4,000 | later | Core database manual |
| `mysql-docs` | MySQL | dev.mysql.com | `/doc/refman/8.4/en/` | 8.4 LTS | 2,500 | 4,000 | later | Version-pinned MySQL manual |
| `mariadb-docs` | MariaDB | mariadb.com | `/docs/server/` | latest | 2,000 | 3,000 | later | Server docs |
| `elasticsearch-docs` | Elasticsearch | www.elastic.co | `/docs/reference/elasticsearch /docs/reference/query-languages /docs/ma …` | 9.x (unversioned /docs) | 5,000 | 8,000 | later | Narrowed from /docs/ (all Elastic products, ~40K) |
| `opensearch-docs` | OpenSearch | docs.opensearch.org | `/latest/` | latest | 2,000 | 3,000 | later | Current docs |
| `kafka-docs` | Apache Kafka | kafka.apache.org | `/documentation/` | latest (4.x) | 60 | 300 | later | Mostly a few very large pages |
| `rabbitmq-docs` | RabbitMQ | www.rabbitmq.com | `/docs` | 4.x | 300 | 600 | later | Current docs |
| `nats-docs` | NATS | docs.nats.io | `/` | latest | 400 | 800 | later | '/' is fine: docs-only host |
| `clickhouse-docs` | ClickHouse | clickhouse.com | `/docs` | latest | 3,000 | 5,000 | later | Translations live under /docs/zh/, /docs/ru/, /docs/jp/, which /docs admits; the cap bounds them until a deny list exists |
| `aws-ec2` | AWS EC2 Documentation | docs.aws.amazon.com | `/AWSEC2/latest/UserGuide/` | latest | 1,500 | 3,000 | later | EC2 only; large tree |
| `aws-s3` | AWS S3 Documentation | docs.aws.amazon.com | `/AmazonS3/latest/userguide/` | latest | 1,200 | 2,500 | later | S3 only; large tree |
| `aws-lambda` | AWS Lambda Documentation | docs.aws.amazon.com | `/lambda/latest/dg/` | latest | 800 | 1,500 | later | Lambda only |
| `aws-rds` | AWS RDS Documentation | docs.aws.amazon.com | `/AmazonRDS/latest/UserGuide/` | latest | 1,500 | 2,500 | later | RDS only |
| `aws-iam` | AWS IAM Documentation | docs.aws.amazon.com | `/IAM/latest/UserGuide/` | latest | 1,000 | 2,000 | later | IAM only |
| `aws-cloudwatch` | AWS CloudWatch Documentation | docs.aws.amazon.com | `/AmazonCloudWatch/latest/monitoring/` | latest | 800 | 1,500 | later | docs.aws.amazon.com robots: Crawl-delay 5, now enforced by HOST_MIN_INTERVAL_SECONDS in politeness_policy.py. Each aws-* row uses its own gu |
| `gcp-cloudrun` | Google Cloud Run | cloud.google.com | `/run/docs` | latest | 600 | 1,200 | later | Cloud Run docs only |
| `gcp-gcs` | Google Cloud Storage | cloud.google.com | `/storage/docs` | latest | 600 | 1,200 | later | Storage docs |
| `gcp-compute` | Google Compute Engine | cloud.google.com | `/compute/docs` | latest | 1,500 | 2,500 | later | Compute docs |
| `gcp-pubsub` | Google Pub/Sub | cloud.google.com | `/pubsub/docs` | latest | 400 | 800 | later | Pub/Sub docs |
| `gcp-bigquery` | Google BigQuery | cloud.google.com | `/bigquery/docs` | latest | 1,500 | 2,500 | later | robots disallows /<lang>/docs/reference/*; English unprefixed paths are fine |
| `azure-functions` | Azure Functions | learn.microsoft.com | `/en-us/azure/azure-functions/` | latest | 500 | 1,000 | later | Azure Functions only |
| `azure-blob` | Azure Blob Storage | learn.microsoft.com | `/en-us/azure/storage/blobs/` | latest | 300 | 600 | later | Blob Storage only |
| `azure-vm` | Azure Virtual Machines | learn.microsoft.com | `/en-us/azure/virtual-machines/` | latest | 1,000 | 2,000 | later | VM docs only |
| `prometheus-docs` | Prometheus | prometheus.io | `/docs/` | latest | 200 | 400 | later | Monitoring docs |
| `grafana-docs` | Grafana | grafana.com | `/docs/grafana/latest/` | latest | 2,000 | 3,000 | later | Grafana OSS docs |
| `opentelemetry-docs` | OpenTelemetry | opentelemetry.io | `/docs/` | latest | 1,000 | 2,000 | later | Core docs |
| `linux-manpages` | Linux man-pages | man7.org | `/linux/man-pages/` | latest man-pages release | 2,500 | 3,500 | later | Official online man-pages |
| `systemd-docs` | systemd Manual | www.freedesktop.org | `/software/systemd/man/latest/` | latest | 400 | 600 | later | systemd manuals |
| `curl-docs` | curl | curl.se | `/docs/` | latest | 400 | 800 | later | curl manual |
| `openssl-docs` | OpenSSL | docs.openssl.org | `/3.5/` | 3.5 LTS | 1,500 | 2,500 | later | Pinned to 3.5 LTS instead of /master/ |
| `github-actions-docs` | GitHub Actions | docs.github.com | `/en/actions` | latest | 600 | 1,200 | later | docs.github.com robots has no rules |
| `gitlab-ci-docs` | GitLab CI/CD | docs.gitlab.com | `/ci/` | latest | 500 | 1,000 | later | CI docs only |
| `circleci-docs` | CircleCI | circleci.com | `/docs/` | latest | 800 | 1,500 | later | CircleCI docs |
| `vscode-docs` | VS Code | code.visualstudio.com | `/docs /api` | latest | 500 | 1,000 | later | Added extension API docs |
| `npm-docs` | npm CLI | docs.npmjs.com | `/cli/` | latest CLI | 150 | 300 | later | npm CLI docs |
| `pypa-pip` | pip | pip.pypa.io | `/en/stable/` | stable | 100 | 200 | later | Stable pip docs |
| `python-poetry` | Poetry | python-poetry.org | `/docs/` | latest | 50 | 150 | later | Dependency manager docs |
| `astral-uv` | uv | docs.astral.sh | `/uv/` | latest | 150 | 300 | later | uv docs |
| `cargo-book` | Cargo Book | doc.rust-lang.org | `/cargo/` | stable | 200 | 400 | later | Official Cargo docs |
| `homebrew-docs` | Homebrew | docs.brew.sh | `/` | latest | 100 | 200 | later | '/' is fine: docs-only host |
| `github-cli-docs` | GitHub CLI | cli.github.com | `/manual/` | latest | 200 | 400 | later | gh commands |
| `maven-docs` | Apache Maven | maven.apache.org | `/guides/` | latest | 80 | 200 | later | Maven guide |
| `gradle-docs` | Gradle | docs.gradle.org | `/current/userguide/` | current | 500 | 1,000 | later | Gradle current docs |
| `vault-docs` | HashiCorp Vault | developer.hashicorp.com | `/vault/docs` | latest | 1,500 | 2,500 | no |  |
| `istio-docs` | Istio | istio.io | `/latest/docs/` | latest | 600 | 1,000 | no |  |
| `argocd-docs` | Argo CD | argo-cd.readthedocs.io | `/en/stable/` | stable | 400 | 800 | no |  |
| `jenkins-docs` | Jenkins | www.jenkins.io | `/doc/` | latest | 1,500 | 2,500 | no |  |
| `cloudflare-dev-docs` | Cloudflare developer docs | developers.cloudflare.com | `/workers/ /pages/ /r2/ /d1/ /kv/ /durable-objects/ /queues/ /dns/ /ssl …` | latest | 5,000 | 8,000 | no |  |
| `vercel-docs` | Vercel docs | vercel.com | `/docs` | latest | 800 | 1,500 | no |  |
| `supabase-docs` | Supabase docs | supabase.com | `/docs` | latest | 2,000 | 3,000 | no |  |
| `firebase-docs` | Firebase docs | firebase.google.com | `/docs` | latest | 3,000 | 5,000 | no | ?hl= locales: strip in normalizer |
| `heroku-devcenter` | Heroku Dev Center | devcenter.heroku.com | `/articles/ /categories/` | latest | 1,500 | 2,500 | no |  |
| `duckdb-docs` | DuckDB | duckdb.org | `/docs/stable/` | stable | 800 | 1,200 | no |  |
| `sqlalchemy-alembic` | Alembic | alembic.sqlalchemy.org | `/en/latest/` | latest | 60 | 150 | no |  |
| `grpc-docs` | gRPC | grpc.io | `/docs/` | latest | 300 | 500 | no |  |
| `protobuf-docs` | Protocol Buffers | protobuf.dev | `/` | latest | 150 | 300 | no |  |
| `graphql-docs` | GraphQL | graphql.org | `/learn/` | latest | 50 | 100 | no |  |
| `openapi-spec` | OpenAPI Specification | spec.openapis.org | `/oas/latest.html` | 3.2 | 1 | 5 | no |  |
| `owasp-cheatsheets` | OWASP Cheat Sheet Series | cheatsheetseries.owasp.org | `/` | living | 120 | 250 | yes | CC BY-SA |
| `letsencrypt-docs` | Let's Encrypt docs | letsencrypt.org | `/docs/` | latest | 60 | 150 | no | Locale trees under /<lang>/docs/ are excluded by prefix |
| `neovim-docs` | Neovim user docs | neovim.io | `/doc/user/` | stable | 150 | 300 | no |  |
| `powershell-docs` | PowerShell docs | learn.microsoft.com | `/en-us/powershell/` | 7.x | 3,000 | 4,000 | no | ?view= variants per version; strip in normalizer |
| `digitalocean-tutorials` | DigitalOcean community tutorials | www.digitalocean.com | `/community/tutorials` | n/a | 8,000 | 10,000 | no | robots allows /community/tutorials; sitemap.xml listed. Excellent English tutorials, content license: check per page |
| `baeldung` | Baeldung (Java/Spring) | www.baeldung.com | `/` | n/a | 6,000 | 8,000 | no | Commercial site: check terms before enabling |

## Tier 4: engineering blogs (RSS) (166)

| Slug | Name | Category | Feed URL | MVP | Notes |
|---|---|---|---|---|---|
| `cloudflare-blog` | Cloudflare Blog | Engineering blogs | https://blog.cloudflare.com/rss/ | yes | Prefer RSS and curated technical posts only |
| `netflix-techblog` | Netflix TechBlog | Engineering blogs | https://netflixtechblog.com/feed | yes | Find official publication feed; validate rights |
| `stripe-engineering` | Stripe Engineering | Engineering blogs | https://stripe.com/blog/feed.rss | yes | Filter engineering posts only |
| `discord-engineering` | Discord Engineering | Engineering blogs | https://discord.com/blog/rss.xml | no | Engineering posts only |
| `uber-engineering` | Uber Engineering | Engineering blogs | https://www.uber.com/blog/engineering/rss/ | no | Engineering posts only |
| `airbnb-engineering` | Airbnb Engineering | Engineering blogs | https://medium.com/feed/airbnb-engineering | no | Publication feed if available; medium.com allows generic crawlers but blocks named AI bots; use our own UA and keep the  |
| `shopify-engineering` | Shopify Engineering | Engineering blogs | https://shopify.engineering/blog.atom | no | Engineering only |
| `github-engineering` | GitHub Blog Engineering | Engineering blogs | https://github.blog/engineering/feed/ | yes | Engineering topics only |
| `gitlab-blog` | GitLab Blog Engineering | Engineering blogs | https://about.gitlab.com/atom.xml | no | Technical posts by curated topic |
| `mozilla-hacks` | Mozilla Hacks | Engineering blogs | https://hacks.mozilla.org/feed/ | no | Web engineering tutorials |
| `vercel-blog` | Vercel Blog | Engineering blogs | https://vercel.com/atom | no | Blocked: the feed is 4.75 MB, above the parser's 2 MB limit |
| `aws-architecture-blog` | AWS Architecture Blog | Engineering blogs | https://aws.amazon.com/blogs/architecture/feed/ | no | Architecture posts only |
| `google-cloud-blog` | Google Cloud Blog | Engineering blogs | https://cloudblog.withgoogle.com/rss/ | no | Engineering articles by curated topic |
| `microsoft-devblogs` | Microsoft DevBlogs | Engineering blogs | https://devblogs.microsoft.com/feed/ | no | Disabled: this is the all-products feed, and its '/' scope swallows the typescript-blog, dotnet-blog and oldnewthing row |
| `dropbox-techblog` | Dropbox Tech Blog | Engineering blogs | https://dropbox.tech/feed | no | Engineering articles |
| `slack-engineering` | Slack Engineering | Engineering blogs | https://slack.engineering/feed/ | no | Engineering articles |
| `figma-engineering` | Figma Engineering | Engineering blogs | https://www.figma.com/blog/feed/atom.xml | no | Technical posts only |
| `sentry-blog` | Sentry Engineering | Engineering blogs | https://blog.sentry.io/feed.xml | no | Engineering posts by curated tags |
| `realpython` | Real Python | Engineering blogs | https://realpython.com/atom.xml | yes | Curated Python tutorials; rights review |
| `webdev` | web.dev | Engineering blogs | https://web.dev/static/blog/feed.xml | no | Core tutorials and guides only |
| `css-tricks` | CSS-Tricks | Engineering blogs | https://css-tricks.com/feed/ | no | Curated CSS learning articles |
| `julia-evans` | Julia Evans | Engineering blogs | https://jvns.ca/atom.xml | yes | Technical blog; do not redistribute original illustrations without permission |
| `martin-fowler` | Martin Fowler | Engineering blogs | https://martinfowler.com/feed.atom | yes | Architecture and engineering essays |
| `dan-luu` | Dan Luu | Engineering blogs | https://danluu.com/atom.xml | no | Blocked: the feed is 6.66 MB, above the parser's 2 MB limit (it carries full post bodies). Needs a bigger limit for feed |
| `brendan-gregg` | Brendan Gregg | Engineering blogs | https://www.brendangregg.com/blog/rss.xml | no | Performance articles; avoid bulk media |
| `highscalability` | High Scalability | Engineering blogs | https://highscalability.com/rss/ | no | Curated systems architecture articles |
| `planet-python` | Planet Python | Engineering blogs | https://planetpython.org/rss20.xml | no | Blocked: every entry links to the original author's blog, so the host allowlist admits 0 of 25 entries. Use it to discov |
| `rust-blog` | Rust Blog | Engineering blogs | https://blog.rust-lang.org/feed.xml | yes | Official Rust development articles |
| `meta-engineering` | Engineering at Meta | Company engineering | https://engineering.fb.com/feed/ | yes |  |
| `google-developers-blog` | Google Developers Blog | Company engineering | https://developers.googleblog.com/rss/ | no |  |
| `google-research-blog` | Google Research Blog | Company engineering | https://research.google/blog/rss/ | no |  |
| `aws-news-blog` | AWS News Blog | Company engineering | https://aws.amazon.com/blogs/aws/feed/ | no |  |
| `aws-compute-blog` | AWS Compute Blog | Company engineering | https://aws.amazon.com/blogs/compute/feed/ | no |  |
| `aws-database-blog` | AWS Database Blog | Company engineering | https://aws.amazon.com/blogs/database/feed/ | no |  |
| `pinterest-engineering` | Pinterest Engineering | Company engineering | https://medium.com/feed/pinterest-engineering | no | medium.com allows generic crawlers but blocks named AI bots; use our own UA and keep the rate low |
| `lyft-engineering` | Lyft Engineering | Company engineering | https://eng.lyft.com/feed | no |  |
| `spotify-engineering` | Spotify Engineering | Company engineering | https://engineering.atspotify.com/feed/ | no |  |
| `etsy-codeascraft` | Etsy Code as Craft | Company engineering | https://www.etsy.com/codeascraft/rss | no |  |
| `instacart-tech` | Instacart Tech | Company engineering | https://tech.instacart.com/feed | no |  |
| `zalando-engineering` | Zalando Engineering | Company engineering | https://engineering.zalando.com/atom.xml | no |  |
| `heroku-engineering` | Heroku Engineering | Company engineering | https://blog.heroku.com/engineering/feed | no |  |
| `flyio-blog` | Fly.io Blog | Company engineering | https://fly.io/blog/feed.xml | no |  |
| `supabase-blog` | Supabase Blog | Company engineering | https://supabase.com/rss.xml | no |  |
| `tailscale-blog` | Tailscale Blog | Company engineering | https://tailscale.com/blog/index.xml | no |  |
| `grafana-blog` | Grafana Labs Blog | Company engineering | https://grafana.com/blog/index.xml | no |  |
| `elastic-blog` | Elastic Blog | Company engineering | https://www.elastic.co/blog/feed | no |  |
| `redis-blog` | Redis Blog | Company engineering | https://redis.io/blog/feed/ | no |  |
| `docker-blog` | Docker Blog | Company engineering | https://www.docker.com/blog/feed/ | no |  |
| `hashicorp-blog` | HashiCorp Blog | Company engineering | https://www.hashicorp.com/blog/feed.xml | no |  |
| `salesforce-engineering` | Salesforce Engineering | Company engineering | https://engineering.salesforce.com/feed/ | no |  |
| `grab-engineering` | Grab Engineering | Company engineering | https://engineering.grab.com/feed.xml | no |  |
| `yelp-engineering` | Yelp Engineering | Company engineering | https://engineeringblog.yelp.com/feed.xml | no |  |
| `palantir-blog` | Palantir Blog | Company engineering | https://blog.palantir.com/feed | no |  |
| `medium-engineering` | Medium Engineering | Company engineering | https://medium.engineering/feed | no |  |
| `expedia-tech` | Expedia Group Tech | Company engineering | https://medium.com/feed/expedia-group-tech | no | medium.com allows generic crawlers but blocks named AI bots; use our own UA and keep the rate low |
| `paypal-tech` | PayPal Tech | Company engineering | https://medium.com/feed/paypal-tech | no | medium.com allows generic crawlers but blocks named AI bots; use our own UA and keep the rate low |
| `37signals-dev` | 37signals Dev | Company engineering | https://dev.37signals.com/feed/posts.xml | no |  |
| `jane-street-tech` | Jane Street Tech Blog | Company engineering | https://blog.janestreet.com/feed.xml | no |  |
| `stackoverflow-blog` | Stack Overflow Blog | Company engineering | https://stackoverflow.blog/feed/ | no |  |
| `redhat-developers` | Red Hat Developer | Company engineering | https://developers.redhat.com/blog/feed | no |  |
| `ubuntu-blog` | Ubuntu Blog | Company engineering | https://ubuntu.com/blog/feed | no |  |
| `postman-blog` | Postman Blog | Company engineering | https://blog.postman.com/feed/ | no |  |
| `percona-blog` | Percona Blog | Databases | https://www.percona.com/blog/feed/ | no |  |
| `planet-postgresql` | Planet PostgreSQL | Databases | https://planet.postgresql.org/rss20.xml | no | Blocked: every entry links to the original author's blog, so the host allowlist admits 0 of 30 entries. Use it to discov |
| `duckdb-blog` | DuckDB Blog | Databases | https://duckdb.org/feed.xml | no |  |
| `opensource-connections` | OpenSource Connections (search relevance) | Databases | https://opensourceconnections.com/feed/ | no |  |
| `this-week-in-rust` | This Week in Rust | Official language blogs | https://this-week-in-rust.org/rss.xml | no | aggregator: entries link to other hosts, so follow_entry_links only fetches same-host pages |
| `go-blog` | The Go Blog | Official language blogs | https://go.dev/blog/feed.atom | yes |  |
| `python-insider` | Python Insider | Official language blogs | https://blog.python.org/feeds/posts/default | no |  |
| `nodejs-blog` | Node.js Blog | Official language blogs | https://nodejs.org/en/feed/blog.xml | no |  |
| `v8-blog` | V8 Blog | Official language blogs | https://v8.dev/blog.atom | no |  |
| `webkit-blog` | WebKit Blog | Official language blogs | https://webkit.org/feed/ | no |  |
| `chromium-blog` | Chromium Blog | Official language blogs | https://blog.chromium.org/feeds/posts/default | no |  |
| `typescript-blog` | TypeScript Blog | Official language blogs | https://devblogs.microsoft.com/typescript/feed/ | no |  |
| `dotnet-blog` | .NET Blog | Official language blogs | https://devblogs.microsoft.com/dotnet/feed/ | no |  |
| `oldnewthing` | The Old New Thing | Official language blogs | https://devblogs.microsoft.com/oldnewthing/feed | no |  |
| `kotlin-blog` | Kotlin Blog | Official language blogs | https://blog.jetbrains.com/kotlin/feed/ | no |  |
| `inside-java` | Inside Java | Official language blogs | https://inside.java/feed.xml | no |  |
| `spring-blog` | Spring Blog | Official language blogs | https://spring.io/blog.atom | no |  |
| `swift-blog` | Swift.org Blog | Official language blogs | https://www.swift.org/atom.xml | no |  |
| `android-dev-blog` | Android Developers Blog | Official language blogs | https://android-developers.googleblog.com/feeds/posts/default | no |  |
| `flutter-blog` | Flutter Blog | Official language blogs | https://blog.flutter.dev/feed | no |  |
| `ruby-news` | Ruby News | Official language blogs | https://www.ruby-lang.org/en/feeds/news.rss | no |  |
| `rails-blog` | Ruby on Rails Blog | Official language blogs | https://rubyonrails.org/feed.xml | no |  |
| `elixir-blog` | Elixir Blog | Official language blogs | https://elixir-lang.org/atom.xml | no |  |
| `llvm-blog` | LLVM Blog | Official language blogs | https://blog.llvm.org/index.xml | no |  |
| `django-weblog` | Django Weblog | Framework blogs | https://www.djangoproject.com/rss/weblog/ | no |  |
| `react-blog` | React Blog | Framework blogs | https://react.dev/rss.xml | no |  |
| `nextjs-blog` | Next.js Blog | Framework blogs | https://nextjs.org/feed.xml | no |  |
| `vue-blog` | Vue Blog | Framework blogs | https://blog.vuejs.org/feed.rss | no |  |
| `svelte-blog` | Svelte Blog | Framework blogs | https://svelte.dev/blog/rss.xml | no |  |
| `angular-blog` | Angular Blog | Framework blogs | https://blog.angular.dev/feed | no |  |
| `deno-blog` | Deno Blog | Framework blogs | https://deno.com/feed | no |  |
| `astro-blog` | Astro Blog | Framework blogs | https://astro.build/rss.xml | no |  |
| `kubernetes-blog` | Kubernetes Blog | Framework blogs | https://kubernetes.io/feed.xml | no |  |
| `cncf-blog` | CNCF Blog | Framework blogs | https://www.cncf.io/feed/ | no |  |
| `tensorflow-blog` | TensorFlow Blog | AI/ML | https://blog.tensorflow.org/feeds/posts/default | no |  |
| `pytorch-blog` | PyTorch Blog | AI/ML | https://pytorch.org/feed/ | no |  |
| `huggingface-blog` | Hugging Face Blog | AI/ML | https://huggingface.co/blog/feed.xml | no |  |
| `deepmind-blog` | Google DeepMind Blog | AI/ML | https://deepmind.google/blog/rss.xml | no |  |
| `karpathy-blog` | Andrej Karpathy | AI/ML | https://karpathy.github.io/feed.xml | no |  |
| `lilian-weng` | Lil'Log (Lilian Weng) | AI/ML | https://lilianweng.github.io/index.xml | no |  |
| `chip-huyen` | Chip Huyen | AI/ML | https://huyenchip.com/feed.xml | no |  |
| `eugene-yan` | Eugene Yan | AI/ML | https://eugeneyan.com/rss/ | no |  |
| `jay-alammar` | Jay Alammar | AI/ML | https://jalammar.github.io/feed.xml | no |  |
| `hamel-husain` | Hamel Husain | AI/ML | https://hamel.dev/index.xml | no |  |
| `sebastian-raschka` | Ahead of AI (Sebastian Raschka) | AI/ML | https://magazine.sebastianraschka.com/feed | no |  |
| `simon-willison` | Simon Willison | Individual engineers | https://simonwillison.net/atom/everything/ | yes |  |
| `joel-on-software` | Joel on Software | Individual engineers | https://www.joelonsoftware.com/feed/ | no |  |
| `coding-horror` | Coding Horror | Individual engineers | https://blog.codinghorror.com/rss/ | no |  |
| `russ-cox` | research!rsc (Russ Cox) | Individual engineers | https://research.swtch.com/feed.atom | no |  |
| `rachel-by-the-bay` | Rachel by the Bay | Individual engineers | https://rachelbythebay.com/w/atom.xml | no |  |
| `eli-bendersky` | Eli Bendersky | Individual engineers | https://eli.thegreenplace.net/feeds/all.atom.xml | no |  |
| `josh-comeau` | Josh W. Comeau | Individual engineers | https://www.joshwcomeau.com/rss.xml | no |  |
| `kent-c-dodds` | Kent C. Dodds | Individual engineers | https://kentcdodds.com/blog/rss.xml | no |  |
| `overreacted` | Overreacted (Dan Abramov) | Individual engineers | https://overreacted.io/rss.xml | no |  |
| `armin-ronacher` | Armin Ronacher | Individual engineers | https://lucumr.pocoo.org/feed.atom | no |  |
| `hynek` | Hynek Schlawack | Individual engineers | https://hynek.me/index.xml | no |  |
| `ned-batchelder` | Ned Batchelder | Individual engineers | https://nedbatchelder.com/blog/rss.xml | no |  |
| `charity-majors` | charity.wtf | Individual engineers | https://charity.wtf/feed/ | no |  |
| `jake-archibald` | Jake Archibald | Individual engineers | https://jakearchibald.com/posts.rss | no |  |
| `addy-osmani` | Addy Osmani | Individual engineers | https://addyosmani.com/rss.xml | no |  |
| `lea-verou` | Lea Verou | Individual engineers | https://lea.verou.me/feed.xml | no |  |
| `ahmad-shadeed` | Ahmad Shadeed | Individual engineers | https://ishadeed.com/feed.xml | no |  |
| `tkdodo` | TkDodo | Individual engineers | https://tkdodo.eu/blog/rss.xml | no |  |
| `matklad` | matklad | Individual engineers | https://matklad.github.io/feed.xml | no |  |
| `fasterthanlime` | fasterthanlime | Individual engineers | https://fasterthanli.me/index.xml | no |  |
| `without-boats` | without.boats | Individual engineers | https://without.boats/index.xml | no |  |
| `mitchell-hashimoto` | Mitchell Hashimoto | Individual engineers | https://mitchellh.com/feed.xml | no |  |
| `scott-hanselman` | Scott Hanselman | Individual engineers | https://feeds.hanselman.com/ScottHanselman | no |  |
| `andrew-lock` | .NET Escapades (Andrew Lock) | Individual engineers | https://andrewlock.net/rss.xml | no |  |
| `vlad-mihalcea` | Vlad Mihalcea | Individual engineers | https://vladmihalcea.com/feed/ | no |  |
| `dave-cheney` | Dave Cheney | Individual engineers | https://dave.cheney.net/feed | no |  |
| `swift-by-sundell` | Swift by Sundell | Individual engineers | https://www.swiftbysundell.com/rss | no |  |
| `hacking-with-swift` | Hacking with Swift | Individual engineers | https://www.hackingwithswift.com/articles/rss | no |  |
| `nshipster` | NSHipster | Individual engineers | https://nshipster.com/feed.xml | no |  |
| `evil-martians` | Evil Martians Chronicles | Individual engineers | https://evilmartians.com/chronicles.atom | no |  |
| `stitcher-io` | stitcher.io (PHP) | Individual engineers | https://stitcher.io/rss | no |  |
| `laravel-news` | Laravel News | Individual engineers | https://feed.laravel-news.com/ | no |  |
| `dashbit-blog` | Dashbit (Elixir) | Individual engineers | https://dashbit.co/feed | no |  |
| `will-larson` | Irrational Exuberance (Will Larson) | Individual engineers | https://lethain.com/feeds/ | no |  |
| `hillel-wayne` | Hillel Wayne | Individual engineers | https://www.hillelwayne.com/index.xml | no |  |
| `bartosz-ciechanowski` | Bartosz Ciechanowski | Individual engineers | https://ciechanow.ski/atom.xml | no |  |
| `xe-iaso` | Xe Iaso | Individual engineers | https://xeiaso.net/blog.rss | no |  |
| `drew-devault` | Drew DeVault | Individual engineers | https://drewdevault.com/blog/index.xml | no |  |
| `daniel-stenberg` | Daniel Stenberg (curl) | Individual engineers | https://daniel.haxx.se/blog/feed/ | no |  |
| `lemire` | Daniel Lemire | Individual engineers | https://lemire.me/blog/feed/ | no |  |
| `fabien-sanglard` | Fabien Sanglard | Individual engineers | https://fabiensanglard.net/rss.xml | no |  |
| `thorsten-ball` | Register Spill (Thorsten Ball) | Individual engineers | https://registerspill.thorstenball.com/feed | no |  |
| `marc-brooker` | Marc Brooker | Systems and databases | https://brooker.co.za/blog/rss.xml | no |  |
| `murat-demirbas` | Metadata (Murat Demirbas) | Systems and databases | https://muratbuffalo.blogspot.com/feeds/posts/default | no |  |
| `aphyr` | Aphyr (Jepsen) | Systems and databases | https://aphyr.com/posts.atom | no |  |
| `phil-eaton` | Phil Eaton | Systems and databases | https://notes.eatonphil.com/rss.xml | no |  |
| `jack-vanlightly` | Jack Vanlightly | Systems and databases | https://jack-vanlightly.com/blog?format=rss | no |  |
| `troy-hunt` | Troy Hunt | Security | https://www.troyhunt.com/rss/ | no |  |
| `portswigger-research` | PortSwigger Research | Security | https://portswigger.net/research/rss | no |  |
| `project-zero` | Google Project Zero | Security | https://googleprojectzero.blogspot.com/feeds/posts/default | no |  |
| `trail-of-bits` | Trail of Bits Blog | Security | https://blog.trailofbits.com/feed/ | no |  |
| `smashing-magazine` | Smashing Magazine | Publications | https://www.smashingmagazine.com/feed/ | no |  |
| `a-list-apart` | A List Apart | Publications | https://alistapart.com/main/feed/ | no |  |
| `lwn` | LWN.net | Publications | https://lwn.net/headlines/rss | no | partly paywalled: index only the free text the page serves |
| `infoq` | InfoQ | Publications | https://feed.infoq.com/ | no |  |
| `freecodecamp-news` | freeCodeCamp News | Publications | https://www.freecodecamp.org/news/rss/ | no |  |
| `pragmatic-engineer` | The Pragmatic Engineer | Publications | https://newsletter.pragmaticengineer.com/feed | no | partly paywalled: index only the free text the page serves |
| `bytebytego` | ByteByteGo | Publications | https://blog.bytebytego.com/feed | no | partly paywalled: index only the free text the page serves |
| `devto` | DEV Community | Publications | https://dev.to/feed | no | aggregator: entries link to other hosts, so follow_entry_links only fetches same-host pages |

## Special sources: discussions (3)

| Slug | Name | Host | Path scope | Version | Est. docs | Max docs | MVP | Notes |
|---|---|---|---|---|---:|---:|---|---|
| `github-curated-issues` | GitHub issues (curated repos) | api.github.com | `` | n/a | 100,000 | 100,000 | no | **blocked_needs_crawler_work**. Blocked on 3 crawler gaps: (1) no auth header support, unauthenticated limit is 60 req/h; needs GITHUB_TOKEN from env (5000 req/h). (2) pagi |
| `stackoverflow-api-sample` | Stack Overflow top-voted Q&A (API sample) | api.stackexchange.com | `` | n/a | 100 | 10,000 | no | Small live sample only; the bulk path is the offline dump (offline_datasets.json). Counted as 100 docs: the first page is the only one reach |
| `stack-overflow-dump` | Stack Overflow data dump | (offline) | `` | latest dump | 500,000 | 500,000 | no | Offline importer; archive.org mirror frozen in 2024 |
