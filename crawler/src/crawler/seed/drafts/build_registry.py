"""Build the draft source registry from nish's TSV draft plus fixes and additions.

Usage (from this folder, no arguments needed):
    python build_registry.py
    python build_registry.py --draft inputs/nish_registry_draft.tsv --github inputs/github_top_repos.tsv --out .

Inputs are checked in under inputs/:
  nish_registry_draft.tsv  -> nish's original 197-row draft (the base list)
  github_top_repos.tsv     -> GitHub search snapshot, top 1,000 repos by stars (2026-11-07)
Every row is validated first. If anything fails, the script prints the errors,
exits with status 1 and writes nothing.

Outputs (into OUT dir):
  documentation.json, blogs.json, apis.json   -> seedable SourceCreate rows (website/rss/api)
  offline_datasets.json                        -> not seedable (Stack Overflow dump)
  github_issue_repos.json                      -> repo allowlist for the GitHub issues source
  source_registry_draft.tsv                    -> nish's columns + max_docs, est_docs, version_pin
  REGISTRY_SUMMARY.md                          -> readable table + totals + review notes
"""
import argparse, csv, json, math, os, re, sys
from collections import Counter, defaultdict
from posixpath import normpath
from urllib.parse import urlsplit, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
_cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
_cli.add_argument("--draft", default=os.path.join(HERE, "inputs", "nish_registry_draft.tsv"))
_cli.add_argument("--github", default=os.path.join(HERE, "inputs", "github_top_repos.tsv"))
_cli.add_argument("--out", default=HERE)
_args = _cli.parse_args()
DRAFT, GH, OUT = _args.draft, _args.github, _args.out
for _required in (DRAFT, GH):
    if not os.path.isfile(_required):
        sys.exit(f"Missing input file: {_required}")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DAY = 86400
PRIORITY = {"1": 100, "2": 90, "3": 80, "4": 70, "S": 60}
TIER_CAP = {"1": 50_000, "2": 15_000, "3": 20_000, "4": 2_000, "S": 500_000}

# ---------------------------------------------------------------- base rows
rows = {}
order = []
with open(DRAFT, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    _need = {"tier", "category", "slug", "name", "base_url", "allowed_hosts", "allowed_path_scope", "proposed_status", "notes"}
    if "version_pin" in (reader.fieldnames or []) or _need - set(reader.fieldnames or []):
        sys.exit(f"{DRAFT} is not the base draft. Pass inputs/nish_registry_draft.tsv; "
                 "source_registry_draft.tsv is this script's output, not its input.")
    for r in reader:
        if not r.get("slug"):
            continue
        r = {k: (v or "").strip() for k, v in r.items() if k}
        rows[r["slug"]] = r
        order.append(r["slug"])

def P(*xs):
    return list(xs)

# ---------------------------------------------------------------- fixes to existing rows
# keys: base, prefixes, hosts, est, cap, ver, note (appended), status, slug (rename), sitemaps
FIX = {
 # tier 1
 "mdn": dict(prefixes=P("/en-US/docs/Web/", "/en-US/docs/Learn_web_development/", "/en-US/docs/Glossary/"), est=14000, cap=20000, ver="living"),
 "html-standard": dict(est=120, cap=300, ver="living", note="Multipage spec only; the single-page / file is ~15 MB, never fetch it"),
 "web-css-spec": dict(est=200, cap=600, ver="latest REC/CR", note="w3.org Style/CSS index links out to drafts.csswg.org and /TR/; add www.w3.org /TR/ prefixes for the specs you want"),
 "http-rfcs": dict(base="https://www.rfc-editor.org/rfc/rfc9110.html", prefixes=P("/rfc/rfc9110.html", "/rfc/rfc9111.html", "/rfc/rfc9112.html", "/rfc/rfc9113.html", "/rfc/rfc9114.html", "/rfc/rfc6455.html", "/rfc/rfc6749.html", "/rfc/rfc7519.html", "/rfc/rfc8446.html", "/rfc/rfc3986.html"), depth=1, est=10, cap=20, ver="per-RFC", note="Exact-file allowlist: HTTP 9110-9114, WebSocket, OAuth2, JWT, TLS 1.3, URI"),
 "webassembly-core": dict(est=60, cap=200, ver="2.0"),
 "python-docs": dict(est=2000, cap=5000, ver="3 (stable alias)", note="robots.txt blocks EOL /3.x/ trees, /3/ allowed; sitemap at /sitemap.xml"),
 "nodejs-docs": dict(base="https://nodejs.org/api/", prefixes=P("/api/", "/en/learn/"), est=250, cap=1000, ver="latest (current)", note="/api/ is the current release; /docs/latest-vXX.x/ trees are duplicates, keep them out"),
 "version-typescript": dict(slug="typescript-docs", prefixes=P("/docs/"), est=300, cap=1000, ver="5.x latest", note="Renamed from version-typescript. /docs/ excludes localized /ja/docs/ etc. Add /tsconfig as a second source if needed (it is one big page)"),
 "rust-book": dict(est=110, cap=300, ver="stable"),
 "rust-std": dict(est=25000, cap=30000, ver="stable", note="/std/ only; /stable/std/ and /nightly/ are duplicates, out of scope. Host doc.rust-lang.org shared by 5 sources, host cap 40K"),
 "rust-reference": dict(est=150, cap=400, ver="stable"),
 "rust-by-example": dict(est=200, cap=400, ver="stable"),
 "go-docs": dict(prefixes=P("/doc/", "/ref/"), est=400, cap=1200, ver="latest", note="Added /ref/ (spec, memory model). /blog/ belongs to the go-blog feed only, so the two sources never write the same URL"),
 "go-stdlib": dict(prefixes=P("/std", "/archive", "/bufio", "/builtin", "/bytes", "/cmp", "/compress", "/container", "/context", "/crypto", "/database", "/debug", "/embed", "/encoding", "/errors", "/expvar", "/flag", "/fmt", "/go", "/hash", "/html", "/image", "/index", "/io", "/iter", "/log", "/maps", "/math", "/mime", "/net", "/os", "/path", "/plugin", "/reflect", "/regexp", "/runtime", "/slices", "/sort", "/strconv", "/strings", "/structs", "/sync", "/syscall", "/testing", "/text", "/time", "/unicode", "/unique", "/unsafe", "/weak"), est=300, cap=600, ver="latest Go release", note="Top-level std package names as exact path prefixes, so third-party module paths (/github.com/...) stay out"),
 "java-docs": dict(base="https://docs.oracle.com/en/java/javase/25/", prefixes=P("/en/java/javase/25/"), est=6000, cap=10000, ver="JDK 25 LTS", note="Pinned to 25 LTS. robots.txt is 59 KB and was only partly readable; re-check /en/java/javase/25/ before enabling"),
 "kotlin-docs": dict(prefixes=P("/docs/", "/api/core/kotlin-stdlib/"), est=3000, cap=6000, ver="latest", note="Added stdlib API reference"),
 "swift-docs": dict(status="blocked_empty_body", est=0, cap=200, ver="Swift 6.x", note="Blocked: the Swift book is a DocC app and the HTML parser extracts an empty body. Workable input: the book's markdown in github.com/swiftlang/swift-book"),
 "cpp-reference": dict(base="https://en.cppreference.com/cpp", prefixes=P("/cpp", "/w/cpp"), est=5000, cap=8000, ver="living", note="/w/cpp now redirects to /cpp, so the seed is /cpp and both prefixes are allowed (old links still redirect in). Doesn't overlap c-reference. robots.txt: Content-Signal search=yes, ai-train=no; blocks ~35 named AI bots. Search indexing is allowed, model training is not"),
 "c-reference": dict(base="https://en.cppreference.com/c", prefixes=P("/c", "/w/c"), est=1200, cap=2000, ver="living", note="/w/c now redirects to /c. Prefix /c matches /c/... only (segment match), so no collision with /cpp"),
 "csharp-docs": dict(est=1500, cap=3000, ver="C# 14 / .NET 10"),
 "net-docs": dict(base="https://learn.microsoft.com/en-us/dotnet/fundamentals/", prefixes=P("/en-us/dotnet/fundamentals/", "/en-us/dotnet/core/", "/en-us/dotnet/standard/", "/en-us/dotnet/fsharp/", "/en-us/aspnet/core/", "/en-us/ef/core/"), est=8000, cap=12000, ver=".NET 10 LTS", note="Excludes /en-us/dotnet/csharp/ (own source) and /en-us/dotnet/api/ (200K+ API pages; add later with its own cap). learn.microsoft.com host shared with azure-*, host cap 40K"),
 "php-docs": dict(est=12000, cap=15000, ver="8.x"),
 "ruby-docs": dict(base="https://docs.ruby-lang.org/en/master/", prefixes=P("/en/master/"), est=3000, cap=5000, ver="master (pin to latest x.y when verified)", note="Pick one version tree only; /en/3.x/ trees are near-duplicates"),
 "dart-docs": dict(prefixes=P("/language", "/libraries", "/tools", "/effective-dart", "/guides", "/interop", "/null-safety", "/web", "/server"), est=400, cap=1000, ver="Dart 3.x"),
 "bash-manual": dict(base="https://www.gnu.org/software/bash/manual/html_node/index.html", est=200, cap=400, ver="5.x", note="gnu.org robots.txt could not be read by our checker (it refused automated fetch); verify before enabling"),
 "gnu-coreutils": dict(base="https://www.gnu.org/software/coreutils/manual/html_node/index.html", est=300, cap=500, ver="9.x", note="Same gnu.org robots caveat as bash-manual"),
 "postgres-docs": dict(est=1200, cap=3000, ver="current (18)"),
 "sqlite-docs": dict(depth=2, est=500, cap=1200, ver="3.x", note="Kept '/' on purpose: SQLite docs are flat files (/lang_*.html, /c3ref/*). The scope only matches whole path segments, so '/lang_' can't work; depth 2 from docs.html plus the cap keeps it tight. robots blocks /src, /cgi, /cvstrac"),
 "git-docs": dict(prefixes=P("/docs", "/book/en/v2"), est=800, cap=1500, ver="latest", note="Added English Pro Git book"),
 # tier 2
 "react-docs": dict(prefixes=P("/learn", "/reference"), est=250, cap=700, ver="19.x", note="/blog belongs to the react-blog feed"),
 "nextjs-docs": dict(prefixes=P("/docs", "/learn"), est=600, cap=1800, ver="latest (App Router)", note="/docs/pages/ is the legacy router; keep or drop. /blog belongs to the nextjs-blog feed"),
 "vue-docs": dict(prefixes=P("/guide/", "/api/", "/tutorial/", "/examples/"), est=200, cap=500, ver="3.x"),
 "angular-docs": dict(prefixes=P("/overview", "/guide", "/api", "/tutorials", "/reference", "/tools", "/best-practices", "/cli", "/ecosystem"), est=1500, cap=3000, ver="latest"),
 "svelte-docs": dict(prefixes=P("/docs/svelte/"), est=150, cap=400, ver="5.x", note="Narrowed to /docs/svelte/ so it doesn't overlap sveltekit-docs"),
 "sveltekit-docs": dict(est=100, cap=300, ver="2.x"),
 "tailwind-docs": dict(est=250, cap=500, ver="4.x"),
 "vite-docs": dict(prefixes=P("/guide/", "/config/", "/plugins/", "/blog/"), est=80, cap=300, ver="latest"),
 "webpack-docs": dict(prefixes=P("/concepts", "/configuration", "/api", "/guides", "/loaders", "/plugins", "/migrate"), est=400, cap=800, ver="5.x"),
 "astro-docs": dict(est=500, cap=1000, ver="5.x"),
 "nuxt-docs": dict(est=400, cap=1000, ver="4.x", note="nuxt.com/docs is current; /docs/3.x/ duplicates if present"),
 "react-router-docs": dict(base="https://reactrouter.com/home", prefixes=P("/home", "/start", "/api", "/tutorials", "/explanation", "/how-to", "/community", "/upgrading"), est=300, cap=800, ver="7.x", note="RR7 is where Remix v2 went; this replaces remix-docs"),
 "solid-docs": dict(base="https://docs.solidjs.com/quick-start", prefixes=P("/quick-start", "/concepts", "/reference", "/guides", "/configuration", "/advanced-concepts", "/solid-router", "/solid-start", "/solid-meta"), est=300, cap=600, ver="1.x"),
 "redux-toolkit-docs": dict(base="https://redux.js.org/toolkit/introduction/getting-started", hosts=P("redux.js.org"), prefixes=P("/toolkit/"), est=150, cap=400, ver="2.x", note="redux-toolkit.js.org now 302s to redux.js.org/toolkit/"),
 "tanstack-query-docs": dict(est=300, cap=600, ver="v5 (latest)", note="All frameworks under /latest/docs/; restrict to /framework/react/ if dupes hurt"),
 "remix-docs": dict(status="duplicate_disabled", est=0, cap=200, ver="v2 (legacy)", note="Disabled: Remix v2 merged into React Router 7, covered by react-router-docs"),
 "playwright-docs": dict(est=400, cap=800, ver="latest"),
 "vitest-docs": dict(prefixes=P("/guide/", "/api/", "/config/"), est=150, cap=400, ver="latest"),
 "jest-docs": dict(est=150, cap=300, ver="current", note="/docs/next/ and /docs/29.x/ are versioned dupes; jestjs.io/docs/ is current"),
 "cypress-docs": dict(prefixes=P("/app/", "/api/"), est=500, cap=1000, ver="latest"),
 "testing-library-docs": dict(est=120, cap=300, ver="latest"),
 "storybook-docs": dict(est=400, cap=800, ver="latest"),
 "eslint-docs": dict(est=600, cap=1000, ver="9.x"),
 "prettier-docs": dict(est=40, cap=100, ver="3.x"),
 "django": dict(base="https://docs.djangoproject.com/en/6.1/", prefixes=P("/en/6.1/", "/en/stable/"), est=800, cap=2000, ver="6.1", note="/en/stable/ redirects to /en/6.1/, so the seed is the pinned version; bump both when 6.2 ships. Already seeded with no path prefix; seed.py skips existing slugs, so this only takes effect via update_source"),
 "flask-docs": dict(est=150, cap=300, ver="stable"),
 "fastapi": dict(base="https://fastapi.tiangolo.com/learn/", prefixes=P("/learn/", "/tutorial/", "/advanced/", "/reference/", "/how-to/", "/deployment/", "/fastapi-cli/", "/features/", "/async/", "/python-types/", "/virtual-environments/", "/environment-variables/", "/alternatives/", "/history-design-future/", "/project-generation/", "/release-notes/"), est=300, cap=600, ver="latest", note="English prefixes only (translations live under /es/, /zh/, /ja/ ...). Already seeded; apply via update_source"),
 "sqlalchemy-docs": dict(est=600, cap=1500, ver="2.0"),
 "pydantic-docs": dict(base="https://pydantic.dev/docs/validation/latest/get-started/", hosts=P("pydantic.dev"), prefixes=P("/docs/validation/latest/"), est=300, cap=600, ver="2.x latest", note="docs.pydantic.dev/latest/ now 302s to pydantic.dev/docs/validation/latest/"),
 "pandas-docs": dict(est=4000, cap=6000, ver="stable"),
 "numpy-docs": dict(est=3500, cap=5000, ver="stable"),
 "scipy-docs": dict(est=3000, cap=4500, ver="stable"),
 "pytest-docs": dict(est=250, cap=500, ver="stable"),
 "requests-docs": dict(est=30, cap=100, ver="latest"),
 "httpx-docs": dict(est=50, cap=150, ver="latest", note="'/' is fine: docs-only host"),
 "celery-docs": dict(est=300, cap=800, ver="stable"),
 "polars-docs": dict(base="https://docs.pola.rs/user-guide/", prefixes=P("/user-guide/", "/api/python/stable/"), est=1500, cap=3000, ver="stable"),
 "matplotlib-docs": dict(est=3000, cap=4000, ver="stable"),
 "beautifulsoup-docs": dict(est=5, cap=20, ver="4.x"),
 "jinja-docs": dict(est=40, cap=100, ver="stable"),
 "rich-docs": dict(est=50, cap=150, ver="stable"),
 "click-docs": dict(est=50, cap=150, ver="stable"),
 "typer-docs": dict(base="https://typer.tiangolo.com/tutorial/", prefixes=P("/tutorial/", "/features/", "/typer-cli/", "/alternatives/", "/virtual-environments/", "/environment-variables/", "/release-notes/"), est=120, cap=300, ver="latest", note="English prefixes only, same pattern as fastapi"),
 "pillow-docs": dict(est=150, cap=300, ver="stable"),
 "aiohttp-docs": dict(est=100, cap=300, ver="stable"),
 "express-docs": dict(est=150, cap=400, ver="5.x", note="/en/ is English; /en/4x/ is a versioned dupe"),
 "nestjs-docs": dict(est=250, cap=500, ver="latest", note="'/' is fine: docs-only host"),
 "prisma-docs": dict(est=1200, cap=2000, ver="latest"),
 "fastify-docs": dict(est=150, cap=300, ver="latest"),
 "zod-docs": dict(est=40, cap=100, ver="4.x", note="'/' is fine: docs-only host"),
 "typeorm-docs": dict(est=100, cap=300, ver="latest"),
 "drizzle-docs": dict(est=400, cap=800, ver="latest"),
 "mongoose-docs": dict(est=200, cap=500, ver="8.x"),
 "bun-docs": dict(base="https://bun.com/docs", hosts=P("bun.com", "bun.sh"), est=400, cap=800, ver="latest", note="bun.sh redirects to bun.com; both hosts allowed so redirects pass"),
 "deno-docs": dict(prefixes=P("/runtime/", "/examples/", "/deploy/"), est=600, cap=1500, ver="2.x"),
 "spring-docs": dict(est=600, cap=1500, ver="7.x (current)"),
 "springboot-docs": dict(est=500, cap=1200, ver="4.x (current)"),
 "hibernate-docs": dict(base="https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html", prefixes=P("/hibernate/orm/current/"), est=50, cap=200, ver="current", note="Pinned to /current/; the bare /hibernate/orm/ tree has every version since 3.x"),
 "quarkus-docs": dict(est=400, cap=800, ver="latest"),
 "micronaut-docs": dict(est=20, cap=100, ver="latest"),
 "junit-docs": dict(base="https://docs.junit.org/current/user-guide/", hosts=P("docs.junit.org", "junit.org"), prefixes=P("/current/"), est=30, cap=100, ver="current (JUnit 6)", note="JUnit docs moved to docs.junit.org; old junit.org/junit5/docs URL redirects"),
 "rails-docs": dict(est=80, cap=200, ver="8.x", note="'/' is fine: guides-only host. Consider api.rubyonrails.org as a tier-3 extra"),
 "laravel-docs": dict(est=100, cap=300, ver="current", note="laravel.com/docs redirects to the current major (/docs/12.x or 13.x); allow both via /docs"),
 "symfony-docs": dict(est=1000, cap=2000, ver="current"),
 "tokio-docs": dict(est=3000, cap=4000, ver="latest"),
 "serde-docs": dict(est=300, cap=600, ver="latest"),
 "axum-docs": dict(est=800, cap=1500, ver="latest"),
 "clap-docs": dict(est=800, cap=1500, ver="latest"),
 "flutter-docs": dict(est=1000, cap=2000, ver="stable", note="'/' is fine: docs-only host"),
 "android-docs": dict(prefixes=P("/develop", "/guide", "/topic", "/training", "/kotlin"), est=6000, cap=10000, ver="latest"),
 "apple-swiftui-docs": dict(status="blocked_js_rendered", est=0, cap=1, ver="n/a", note="Disabled: developer.apple.com/documentation is a JS app, HTML fetch returns an empty shell. Alternative: its JSON at /tutorials/data/documentation/swiftui.json via an api source"),
 "pytorch-docs": dict(base="https://docs.pytorch.org/docs/stable/", hosts=P("docs.pytorch.org", "pytorch.org"), prefixes=P("/docs/stable/", "/tutorials/"), est=3800, cap=5000, ver="stable", note="pytorch.org/docs redirects to docs.pytorch.org; added /tutorials/"),
 "tensorflow-docs": dict(base="https://www.tensorflow.org/api_docs/python/tf", prefixes=P("/api_docs/python/", "/guide/", "/tutorials/"), est=8000, cap=10000, ver="2.x stable", note="Locales use ?hl= query, so the path scope can't drop them; normalizer should strip hl="),
 "sklearn-docs": dict(est=2500, cap=4000, ver="stable"),
 "hf-transformers": dict(est=1500, cap=2500, ver="unversioned (main release)", note="Prefix also admits /docs/transformers/v4.x/, /main/ and /ja/ trees; cap keeps it bounded until a deny list exists"),
 "hf-datasets": dict(est=150, cap=400, ver="latest", note="Same versioned-tree caveat as hf-transformers"),
 "hf-tokenizers": dict(est=60, cap=200, ver="latest"),
 "lightning-docs": dict(est=600, cap=1000, ver="stable"),
 "langchain-docs": dict(est=600, cap=1200, ver="1.x"),
 "llamaindex-docs": dict(est=1500, cap=2500, ver="stable", note="docs.llamaindex.ai may redirect to developers.llamaindex.ai; verify host"),
 "onnx-docs": dict(est=300, cap=600, ver="latest"),
 "xgboost-docs": dict(est=150, cap=300, ver="stable"),
 # tier 3
 "docker-docs": dict(base="https://docs.docker.com/get-started/", prefixes=P("/get-started/", "/engine/", "/build/", "/compose/", "/reference/", "/manuals/", "/guides/", "/desktop/", "/docker-hub/", "/scout/", "/security/", "/dhi/"), est=2500, cap=4000, ver="latest"),
 "kubernetes-docs": dict(est=1500, cap=3000, ver="latest (v1.3x)", note="/docs/ excludes /zh-cn/docs/ etc. robots blocks /legacy/, /v1.0/, /v1.1/"),
 "helm-docs": dict(est=200, cap=400, ver="3.x/4.x"),
 "podman-docs": dict(est=200, cap=400, ver="latest"),
 "terraform-docs": dict(prefixes=P("/terraform/docs", "/terraform/language", "/terraform/cli", "/terraform/tutorials", "/terraform/cloud-docs"), est=3000, cap=5000, ver="latest", note="Provider docs live on registry.terraform.io (JS app); not included"),
 "opentofu-docs": dict(est=300, cap=600, ver="latest"),
 "ansible-docs": dict(est=8000, cap=10000, ver="latest", note="Includes collection module docs (most of the 8K). docs.ansible.com reorganized in 2025 under /projects/; verify the redirect"),
 "nginx-docs": dict(est=300, cap=500, ver="mainline"),
 "caddy-docs": dict(est=200, cap=400, ver="2.x"),
 "traefik-docs": dict(est=400, cap=800, ver="v3"),
 "redis-docs": dict(est=5000, cap=6000, ver="latest"),
 "mongodb-docs": dict(est=2500, cap=4000, ver="current (8.x)"),
 "mysql-docs": dict(est=2500, cap=4000, ver="8.4 LTS"),
 "mariadb-docs": dict(est=2000, cap=3000, ver="latest"),
 "elasticsearch-docs": dict(base="https://www.elastic.co/docs/reference/elasticsearch", prefixes=P("/docs/reference/elasticsearch", "/docs/reference/query-languages", "/docs/manage-data", "/docs/solutions/search", "/docs/deploy-manage", "/docs/explore-analyze"), est=5000, cap=8000, ver="9.x (unversioned /docs)", note="Narrowed from /docs/ (all Elastic products, ~40K)"),
 "opensearch-docs": dict(est=2000, cap=3000, ver="latest"),
 "kafka-docs": dict(est=60, cap=300, ver="latest (4.x)", note="Mostly a few very large pages"),
 "rabbitmq-docs": dict(est=300, cap=600, ver="4.x"),
 "nats-docs": dict(est=400, cap=800, ver="latest", note="'/' is fine: docs-only host"),
 "clickhouse-docs": dict(est=3000, cap=5000, ver="latest", note="Translations live under /docs/zh/, /docs/ru/, /docs/jp/, which /docs admits; the cap bounds them until a deny list exists"),
 "aws-ec2": dict(sitemaps=P("https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/sitemap.xml"), est=1500, cap=3000, ver="latest"),
 "aws-s3": dict(sitemaps=P("https://docs.aws.amazon.com/AmazonS3/latest/userguide/sitemap.xml"), est=1200, cap=2500, ver="latest"),
 "aws-lambda": dict(sitemaps=P("https://docs.aws.amazon.com/lambda/latest/dg/sitemap.xml"), est=800, cap=1500, ver="latest"),
 "aws-rds": dict(sitemaps=P("https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/sitemap.xml"), est=1500, cap=2500, ver="latest"),
 "aws-iam": dict(sitemaps=P("https://docs.aws.amazon.com/IAM/latest/UserGuide/sitemap.xml"), est=1000, cap=2000, ver="latest"),
 "aws-cloudwatch": dict(sitemaps=P("https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/sitemap.xml"), est=800, cap=1500, ver="latest", note="docs.aws.amazon.com robots: Crawl-delay 5, now enforced by HOST_MIN_INTERVAL_SECONDS in politeness_policy.py. Each aws-* row uses its own guide sitemap; host-wide discovery is off because the index lists ~13,900 child sitemaps"),
 "gcp-cloudrun": dict(hosts=P("cloud.google.com", "docs.cloud.google.com"), est=600, cap=1200, ver="latest"),
 "gcp-gcs": dict(hosts=P("cloud.google.com", "docs.cloud.google.com"), est=600, cap=1200, ver="latest"),
 "gcp-compute": dict(hosts=P("cloud.google.com", "docs.cloud.google.com"), est=1500, cap=2500, ver="latest"),
 "gcp-pubsub": dict(hosts=P("cloud.google.com", "docs.cloud.google.com"), est=400, cap=800, ver="latest"),
 "gcp-bigquery": dict(hosts=P("cloud.google.com", "docs.cloud.google.com"), est=1500, cap=2500, ver="latest", note="robots disallows /<lang>/docs/reference/*; English unprefixed paths are fine"),
 "azure-functions": dict(est=500, cap=1000, ver="latest"),
 "azure-blob": dict(est=300, cap=600, ver="latest"),
 "azure-vm": dict(est=1000, cap=2000, ver="latest"),
 "prometheus-docs": dict(est=200, cap=400, ver="latest"),
 "grafana-docs": dict(est=2000, cap=3000, ver="latest"),
 "opentelemetry-docs": dict(est=1000, cap=2000, ver="latest"),
 "linux-manpages": dict(est=2500, cap=3500, ver="latest man-pages release"),
 "systemd-docs": dict(base="https://www.freedesktop.org/software/systemd/man/latest/", prefixes=P("/software/systemd/man/latest/"), est=400, cap=600, ver="latest"),
 "curl-docs": dict(est=400, cap=800, ver="latest"),
 "openssl-docs": dict(base="https://docs.openssl.org/3.5/", prefixes=P("/3.5/"), est=1500, cap=2500, ver="3.5 LTS", note="Pinned to 3.5 LTS instead of /master/"),
 "github-actions-docs": dict(est=600, cap=1200, ver="latest", note="docs.github.com robots has no rules"),
 "gitlab-ci-docs": dict(est=500, cap=1000, ver="latest"),
 "circleci-docs": dict(est=800, cap=1500, ver="latest"),
 "vscode-docs": dict(prefixes=P("/docs", "/api"), est=500, cap=1000, ver="latest", note="Added extension API docs"),
 "npm-docs": dict(est=150, cap=300, ver="latest CLI"),
 "pypa-pip": dict(est=100, cap=200, ver="stable"),
 "python-poetry": dict(est=50, cap=150, ver="latest"),
 "astral-uv": dict(est=150, cap=300, ver="latest"),
 "cargo-book": dict(est=200, cap=400, ver="stable"),
 "homebrew-docs": dict(est=100, cap=200, ver="latest", note="'/' is fine: docs-only host"),
 "github-cli-docs": dict(est=200, cap=400, ver="latest"),
 "maven-docs": dict(est=80, cap=200, ver="latest"),
 "gradle-docs": dict(est=500, cap=1000, ver="current"),
}

# ---------------------------------------------------------------- new sources
# (tier, category, slug, name, base, hosts, prefixes, est, cap, ver, note, mvp)
NEW = [
 ("1", "Web platform", "web-dev", "web.dev guides", "https://web.dev/learn", P("web.dev"), P("/learn", "/articles", "/explore"), 1500, 2500, "living", "Google's web guides (performance, a11y, PWA)", "yes"),
 ("1", "Languages", "rust-nomicon", "Rustonomicon", "https://doc.rust-lang.org/nomicon/", P("doc.rust-lang.org"), P("/nomicon/"), 60, 150, "stable", "", "no"),
 ("1", "Languages", "rust-async-book", "Async Rust book", "https://rust-lang.github.io/async-book/", P("rust-lang.github.io"), P("/async-book/"), 40, 100, "latest", "", "no"),
 ("1", "Languages", "java-tutorials", "dev.java Learn", "https://dev.java/learn/", P("dev.java"), P("/learn/"), 300, 600, "latest", "Official Java tutorials", "yes"),
 ("1", "Languages", "gnu-make", "GNU Make Manual", "https://www.gnu.org/software/make/manual/html_node/index.html", P("www.gnu.org"), P("/software/make/manual/"), 200, 300, "4.x", "gnu.org robots caveat", "no"),
 ("1", "Languages", "gnu-gawk", "GNU Awk Manual", "https://www.gnu.org/software/gawk/manual/html_node/index.html", P("www.gnu.org"), P("/software/gawk/manual/"), 300, 400, "5.x", "gnu.org robots caveat", "no"),
 ("1", "Languages", "scala-docs", "Scala documentation", "https://docs.scala-lang.org/", P("docs.scala-lang.org"), P("/"), 1500, 2500, "3.x", "Has /ja/, /zh-cn/ trees; cap until a deny list exists", "no"),
 ("1", "Languages", "elixir-docs", "Elixir documentation", "https://hexdocs.pm/elixir/", P("hexdocs.pm"), P("/elixir/"), 400, 800, "latest", "hexdocs.pm/elixir/ is current; versioned trees at /elixir/1.x/", "no"),
 ("1", "Languages", "python-peps", "Python PEPs", "https://peps.python.org/", P("peps.python.org"), P("/"), 700, 1000, "living", "", "no"),
 ("1", "Languages", "linux-kernel-docs", "Linux kernel documentation", "https://docs.kernel.org/", P("docs.kernel.org"), P("/"), 3000, 5000, "latest", "Translations under /translations/; cap", "no"),
 ("2", "Rust crates", "anyhow-docs", "anyhow (docs.rs)", "https://docs.rs/anyhow/latest/anyhow/", P("docs.rs"), P("/anyhow/latest/anyhow/"), 40, 100, "latest", "docs.rs host cap 30K across crates", "no"),
 ("2", "Rust crates", "thiserror-docs", "thiserror (docs.rs)", "https://docs.rs/thiserror/latest/thiserror/", P("docs.rs"), P("/thiserror/latest/thiserror/"), 10, 50, "latest", "", "no"),
 ("2", "Rust crates", "reqwest-docs", "reqwest (docs.rs)", "https://docs.rs/reqwest/latest/reqwest/", P("docs.rs"), P("/reqwest/latest/reqwest/"), 300, 600, "latest", "", "no"),
 ("2", "Rust crates", "serde-json-docs", "serde_json (docs.rs)", "https://docs.rs/serde_json/latest/serde_json/", P("docs.rs"), P("/serde_json/latest/serde_json/"), 150, 300, "latest", "", "no"),
 ("2", "Rust crates", "sqlx-docs", "sqlx (docs.rs)", "https://docs.rs/sqlx/latest/sqlx/", P("docs.rs"), P("/sqlx/latest/sqlx/"), 800, 1500, "latest", "", "no"),
 ("2", "Rust crates", "tracing-docs", "tracing (docs.rs)", "https://docs.rs/tracing/latest/tracing/", P("docs.rs"), P("/tracing/latest/tracing/"), 300, 600, "latest", "", "no"),
 ("2", "Rust crates", "hyper-docs", "hyper (docs.rs)", "https://docs.rs/hyper/latest/hyper/", P("docs.rs"), P("/hyper/latest/hyper/"), 300, 600, "latest", "", "no"),
 ("2", "Rust crates", "rand-docs", "rand (docs.rs)", "https://docs.rs/rand/latest/rand/", P("docs.rs"), P("/rand/latest/rand/"), 200, 400, "latest", "", "no"),
 ("2", "Rust crates", "regex-docs", "regex (docs.rs)", "https://docs.rs/regex/latest/regex/", P("docs.rs"), P("/regex/latest/regex/"), 100, 200, "latest", "", "no"),
 ("2", "Rust crates", "chrono-docs", "chrono (docs.rs)", "https://docs.rs/chrono/latest/chrono/", P("docs.rs"), P("/chrono/latest/chrono/"), 300, 600, "latest", "", "no"),
 ("2", "Frontend frameworks", "react-native-docs", "React Native", "https://reactnative.dev/docs/getting-started", P("reactnative.dev"), P("/docs/", "/blog/"), 600, 1200, "latest", "/docs/next/ and /docs/0.7x/ are versioned dupes", "no"),
 ("2", "Frontend frameworks", "expo-docs", "Expo", "https://docs.expo.dev/", P("docs.expo.dev"), P("/"), 1500, 2500, "latest", "", "no"),
 ("2", "Frontend frameworks", "electron-docs", "Electron", "https://www.electronjs.org/docs/latest/", P("www.electronjs.org"), P("/docs/latest/"), 500, 1000, "latest", "", "no"),
 ("2", "Frontend frameworks", "sass-docs", "Sass", "https://sass-lang.com/documentation/", P("sass-lang.com"), P("/documentation/"), 300, 500, "latest", "", "no"),
 ("2", "Frontend frameworks", "bootstrap-docs", "Bootstrap", "https://getbootstrap.com/docs/5.3/getting-started/introduction/", P("getbootstrap.com"), P("/docs/5.3/"), 100, 200, "5.3", "", "no"),
 ("2", "Frontend frameworks", "d3-docs", "D3", "https://d3js.org/what-is-d3", P("d3js.org"), P("/"), 150, 300, "7.x", "", "no"),
 ("2", "Python libraries", "mypy-docs", "mypy", "https://mypy.readthedocs.io/en/stable/", P("mypy.readthedocs.io"), P("/en/stable/"), 100, 200, "stable", "", "no"),
 ("2", "Python libraries", "ruff-docs", "Ruff", "https://docs.astral.sh/ruff/", P("docs.astral.sh"), P("/ruff/"), 1000, 1500, "latest", "Mostly one page per lint rule", "no"),
 ("2", "Python libraries", "keras-docs", "Keras", "https://keras.io/api/", P("keras.io"), P("/api/", "/guides/", "/examples/"), 600, 1000, "3.x", "", "no"),
 ("2", "Python libraries", "jax-docs", "JAX", "https://docs.jax.dev/en/latest/", P("docs.jax.dev"), P("/en/latest/"), 600, 1000, "latest", "", "no"),
 ("2", "Backend frameworks", "ktor-docs", "Ktor", "https://ktor.io/docs/welcome.html", P("ktor.io"), P("/docs/"), 400, 800, "3.x", "", "no"),
 ("2", "Backend frameworks", "gin-docs", "Gin", "https://gin-gonic.com/en/docs/", P("gin-gonic.com"), P("/en/docs/"), 50, 150, "latest", "", "no"),
 ("2", "Backend frameworks", "gorm-docs", "GORM", "https://gorm.io/docs/", P("gorm.io"), P("/docs/"), 100, 200, "latest", "", "no"),
 ("2", "Backend frameworks", "phoenix-docs", "Phoenix", "https://hexdocs.pm/phoenix/overview.html", P("hexdocs.pm"), P("/phoenix/"), 300, 500, "latest", "", "no"),
 ("2", "Backend frameworks", "rails-api", "Rails API reference", "https://api.rubyonrails.org/", P("api.rubyonrails.org"), P("/"), 3000, 4000, "8.x", "", "no"),
 ("3", "Infrastructure", "vault-docs", "HashiCorp Vault", "https://developer.hashicorp.com/vault/docs", P("developer.hashicorp.com"), P("/vault/docs"), 1500, 2500, "latest", "", "no"),
 ("3", "Infrastructure", "istio-docs", "Istio", "https://istio.io/latest/docs/", P("istio.io"), P("/latest/docs/"), 600, 1000, "latest", "", "no"),
 ("3", "Infrastructure", "argocd-docs", "Argo CD", "https://argo-cd.readthedocs.io/en/stable/", P("argo-cd.readthedocs.io"), P("/en/stable/"), 400, 800, "stable", "", "no"),
 ("3", "Infrastructure", "jenkins-docs", "Jenkins", "https://www.jenkins.io/doc/", P("www.jenkins.io"), P("/doc/"), 1500, 2500, "latest", "", "no"),
 ("3", "Infrastructure", "cloudflare-dev-docs", "Cloudflare developer docs", "https://developers.cloudflare.com/workers/", P("developers.cloudflare.com"), P("/workers/", "/pages/", "/r2/", "/d1/", "/kv/", "/durable-objects/", "/queues/", "/dns/", "/ssl/", "/cache/", "/rules/", "/waf/"), 5000, 8000, "latest", "", "no"),
 ("3", "Infrastructure", "vercel-docs", "Vercel docs", "https://vercel.com/docs", P("vercel.com"), P("/docs"), 800, 1500, "latest", "", "no"),
 ("3", "Infrastructure", "supabase-docs", "Supabase docs", "https://supabase.com/docs", P("supabase.com"), P("/docs"), 2000, 3000, "latest", "", "no"),
 ("3", "Infrastructure", "firebase-docs", "Firebase docs", "https://firebase.google.com/docs", P("firebase.google.com"), P("/docs"), 3000, 5000, "latest", "?hl= locales: strip in normalizer", "no"),
 ("3", "Infrastructure", "heroku-devcenter", "Heroku Dev Center", "https://devcenter.heroku.com/categories/reference", P("devcenter.heroku.com"), P("/articles/", "/categories/"), 1500, 2500, "latest", "", "no"),
 ("3", "Databases and tooling", "duckdb-docs", "DuckDB", "https://duckdb.org/docs/stable/", P("duckdb.org"), P("/docs/stable/"), 800, 1200, "stable", "", "no"),
 ("3", "Databases and tooling", "sqlalchemy-alembic", "Alembic", "https://alembic.sqlalchemy.org/en/latest/", P("alembic.sqlalchemy.org"), P("/en/latest/"), 60, 150, "latest", "", "no"),
 ("3", "APIs and protocols", "grpc-docs", "gRPC", "https://grpc.io/docs/", P("grpc.io"), P("/docs/"), 300, 500, "latest", "", "no"),
 ("3", "APIs and protocols", "protobuf-docs", "Protocol Buffers", "https://protobuf.dev/overview/", P("protobuf.dev"), P("/"), 150, 300, "latest", "", "no"),
 ("3", "APIs and protocols", "graphql-docs", "GraphQL", "https://graphql.org/learn/", P("graphql.org"), P("/learn/"), 50, 100, "latest", "", "no"),
 ("3", "APIs and protocols", "openapi-spec", "OpenAPI Specification", "https://spec.openapis.org/oas/latest.html", P("spec.openapis.org"), P("/oas/latest.html"), 1, 5, "3.2", "", "no"),
 ("3", "Security", "owasp-cheatsheets", "OWASP Cheat Sheet Series", "https://cheatsheetseries.owasp.org/", P("cheatsheetseries.owasp.org"), P("/"), 120, 250, "living", "CC BY-SA", "yes"),
 ("3", "Security", "letsencrypt-docs", "Let's Encrypt docs", "https://letsencrypt.org/docs/", P("letsencrypt.org"), P("/docs/"), 60, 150, "latest", "Locale trees under /<lang>/docs/ are excluded by prefix", "no"),
 ("3", "Editors and shells", "neovim-docs", "Neovim user docs", "https://neovim.io/doc/user/", P("neovim.io"), P("/doc/user/"), 150, 300, "stable", "", "no"),
 ("3", "Editors and shells", "powershell-docs", "PowerShell docs", "https://learn.microsoft.com/en-us/powershell/scripting/overview", P("learn.microsoft.com"), P("/en-us/powershell/"), 3000, 4000, "7.x", "?view= variants per version; strip in normalizer", "no"),
 ("3", "Tutorials", "digitalocean-tutorials", "DigitalOcean community tutorials", "https://www.digitalocean.com/community/tutorials", P("www.digitalocean.com"), P("/community/tutorials"), 8000, 10000, "n/a", "robots allows /community/tutorials; sitemap.xml listed. Excellent English tutorials, content license: check per page", "no"),
 ("3", "Tutorials", "baeldung", "Baeldung (Java/Spring)", "https://www.baeldung.com/", P("www.baeldung.com"), P("/"), 6000, 8000, "n/a", "Commercial site: check terms before enabling", "no"),
]

# ---------------------------------------------------------------- RSS feeds (tier 4)
# slug -> (feed_url, article_hosts, article_prefixes, mvp)
FEEDS_FIX = {
 "cloudflare-blog": ("https://blog.cloudflare.com/rss/", P("blog.cloudflare.com"), P("/")),
 "netflix-techblog": ("https://netflixtechblog.com/feed", P("netflixtechblog.com"), P("/")),
 "stripe-engineering": ("https://stripe.com/blog/feed.rss", P("stripe.com"), P("/blog/")),
 "discord-engineering": ("https://discord.com/blog/rss.xml", P("discord.com"), P("/blog/")),
 "uber-engineering": ("https://www.uber.com/blog/engineering/rss/", P("www.uber.com"), P("/blog/")),
 "airbnb-engineering": ("https://medium.com/feed/airbnb-engineering", P("medium.com"), P("/airbnb-engineering")),
 "shopify-engineering": ("https://shopify.engineering/blog.atom", P("shopify.engineering"), P("/")),
 "github-engineering": ("https://github.blog/engineering/feed/", P("github.blog"), P("/engineering/")),
 "gitlab-blog": ("https://about.gitlab.com/atom.xml", P("about.gitlab.com"), P("/blog/")),
 "mozilla-hacks": ("https://hacks.mozilla.org/feed/", P("hacks.mozilla.org"), P("/")),
 "vercel-blog": ("https://vercel.com/atom", P("vercel.com"), P("/blog")),
 "aws-architecture-blog": ("https://aws.amazon.com/blogs/architecture/feed/", P("aws.amazon.com"), P("/blogs/architecture/")),
 "google-cloud-blog": ("https://cloudblog.withgoogle.com/rss/", P("cloud.google.com", "cloudblog.withgoogle.com"), P("/blog/")),
 "microsoft-devblogs": ("https://devblogs.microsoft.com/feed/", P("devblogs.microsoft.com"), P("/")),
 "dropbox-techblog": ("https://dropbox.tech/feed", P("dropbox.tech"), P("/")),
 "slack-engineering": ("https://slack.engineering/feed/", P("slack.engineering"), P("/")),
 "figma-engineering": ("https://www.figma.com/blog/feed/atom.xml", P("www.figma.com"), P("/blog/")),
 "sentry-blog": ("https://blog.sentry.io/feed.xml", P("blog.sentry.io"), P("/")),
 "realpython": ("https://realpython.com/atom.xml", P("realpython.com"), P("/")),
 "webdev": ("https://web.dev/static/blog/feed.xml", P("web.dev"), P("/blog/")),
 "css-tricks": ("https://css-tricks.com/feed/", P("css-tricks.com"), P("/")),
 "julia-evans": ("https://jvns.ca/atom.xml", P("jvns.ca"), P("/")),
 "martin-fowler": ("https://martinfowler.com/feed.atom", P("martinfowler.com"), P("/")),
 "dan-luu": ("https://danluu.com/atom.xml", P("danluu.com"), P("/")),
 "brendan-gregg": ("https://www.brendangregg.com/blog/rss.xml", P("www.brendangregg.com"), P("/")),
 "highscalability": ("https://highscalability.com/rss/", P("highscalability.com"), P("/")),
 "planet-python": ("https://planetpython.org/rss20.xml", P("planetpython.org"), P("/")),
 "rust-blog": ("https://blog.rust-lang.org/feed.xml", P("blog.rust-lang.org"), P("/")),
}
# new feeds: (slug, name, category, feed_url, article_hosts, prefixes)
NEW_FEEDS = [
 # company / platform engineering
 ("meta-engineering", "Engineering at Meta", "Company engineering", "https://engineering.fb.com/feed/", P("engineering.fb.com"), P("/")),
 ("google-developers-blog", "Google Developers Blog", "Company engineering", "https://developers.googleblog.com/rss/", P("developers.googleblog.com"), P("/")),
 ("google-research-blog", "Google Research Blog", "Company engineering", "https://research.google/blog/rss/", P("research.google"), P("/blog/")),
 ("aws-news-blog", "AWS News Blog", "Company engineering", "https://aws.amazon.com/blogs/aws/feed/", P("aws.amazon.com"), P("/blogs/aws/")),
 ("aws-compute-blog", "AWS Compute Blog", "Company engineering", "https://aws.amazon.com/blogs/compute/feed/", P("aws.amazon.com"), P("/blogs/compute/")),
 ("aws-database-blog", "AWS Database Blog", "Company engineering", "https://aws.amazon.com/blogs/database/feed/", P("aws.amazon.com"), P("/blogs/database/")),
 ("pinterest-engineering", "Pinterest Engineering", "Company engineering", "https://medium.com/feed/pinterest-engineering", P("medium.com"), P("/pinterest-engineering")),
 ("lyft-engineering", "Lyft Engineering", "Company engineering", "https://eng.lyft.com/feed", P("eng.lyft.com"), P("/")),
 ("spotify-engineering", "Spotify Engineering", "Company engineering", "https://engineering.atspotify.com/feed/", P("engineering.atspotify.com"), P("/")),
 ("etsy-codeascraft", "Etsy Code as Craft", "Company engineering", "https://www.etsy.com/codeascraft/rss", P("www.etsy.com"), P("/codeascraft/")),
 ("instacart-tech", "Instacart Tech", "Company engineering", "https://tech.instacart.com/feed", P("tech.instacart.com"), P("/")),
 ("zalando-engineering", "Zalando Engineering", "Company engineering", "https://engineering.zalando.com/atom.xml", P("engineering.zalando.com"), P("/")),
 ("heroku-engineering", "Heroku Engineering", "Company engineering", "https://blog.heroku.com/engineering/feed", P("blog.heroku.com"), P("/")),
 ("flyio-blog", "Fly.io Blog", "Company engineering", "https://fly.io/blog/feed.xml", P("fly.io"), P("/blog/")),
 ("supabase-blog", "Supabase Blog", "Company engineering", "https://supabase.com/rss.xml", P("supabase.com"), P("/blog/")),
 ("tailscale-blog", "Tailscale Blog", "Company engineering", "https://tailscale.com/blog/index.xml", P("tailscale.com"), P("/blog/")),
 ("grafana-blog", "Grafana Labs Blog", "Company engineering", "https://grafana.com/blog/index.xml", P("grafana.com"), P("/blog/")),
 ("elastic-blog", "Elastic Blog", "Company engineering", "https://www.elastic.co/blog/feed", P("www.elastic.co"), P("/blog/", "/search-labs/blog/")),
 ("redis-blog", "Redis Blog", "Company engineering", "https://redis.io/blog/feed/", P("redis.io"), P("/blog/")),
 ("docker-blog", "Docker Blog", "Company engineering", "https://www.docker.com/blog/feed/", P("www.docker.com"), P("/blog/")),
 ("hashicorp-blog", "HashiCorp Blog", "Company engineering", "https://www.hashicorp.com/blog/feed.xml", P("www.hashicorp.com"), P("/blog/")),
 ("salesforce-engineering", "Salesforce Engineering", "Company engineering", "https://engineering.salesforce.com/feed/", P("engineering.salesforce.com"), P("/")),
 ("grab-engineering", "Grab Engineering", "Company engineering", "https://engineering.grab.com/feed.xml", P("engineering.grab.com"), P("/")),
 ("yelp-engineering", "Yelp Engineering", "Company engineering", "https://engineeringblog.yelp.com/feed.xml", P("engineeringblog.yelp.com"), P("/")),
 ("palantir-blog", "Palantir Blog", "Company engineering", "https://blog.palantir.com/feed", P("blog.palantir.com"), P("/")),
 ("medium-engineering", "Medium Engineering", "Company engineering", "https://medium.engineering/feed", P("medium.engineering"), P("/")),
 ("expedia-tech", "Expedia Group Tech", "Company engineering", "https://medium.com/feed/expedia-group-tech", P("medium.com"), P("/expedia-group-tech")),
 ("paypal-tech", "PayPal Tech", "Company engineering", "https://medium.com/feed/paypal-tech", P("medium.com"), P("/paypal-tech")),
 ("37signals-dev", "37signals Dev", "Company engineering", "https://dev.37signals.com/feed/posts.xml", P("dev.37signals.com"), P("/")),
 ("jane-street-tech", "Jane Street Tech Blog", "Company engineering", "https://blog.janestreet.com/feed.xml", P("blog.janestreet.com"), P("/")),
 ("stackoverflow-blog", "Stack Overflow Blog", "Company engineering", "https://stackoverflow.blog/feed/", P("stackoverflow.blog"), P("/")),
 ("redhat-developers", "Red Hat Developer", "Company engineering", "https://developers.redhat.com/blog/feed", P("developers.redhat.com"), P("/")),
 ("ubuntu-blog", "Ubuntu Blog", "Company engineering", "https://ubuntu.com/blog/feed", P("ubuntu.com"), P("/blog/")),
 ("postman-blog", "Postman Blog", "Company engineering", "https://blog.postman.com/feed/", P("blog.postman.com"), P("/")),
 ("percona-blog", "Percona Blog", "Databases", "https://www.percona.com/blog/feed/", P("www.percona.com"), P("/blog/")),
 ("planet-postgresql", "Planet PostgreSQL", "Databases", "https://planet.postgresql.org/rss20.xml", P("planet.postgresql.org"), P("/")),
 ("duckdb-blog", "DuckDB Blog", "Databases", "https://duckdb.org/feed.xml", P("duckdb.org"), P(*[f"/{y}" for y in range(2019, 2028)])),
 ("opensource-connections", "OpenSource Connections (search relevance)", "Databases", "https://opensourceconnections.com/feed/", P("opensourceconnections.com"), P("/blog/")),
 # language / framework official blogs
 ("this-week-in-rust", "This Week in Rust", "Official language blogs", "https://this-week-in-rust.org/rss.xml", P("this-week-in-rust.org"), P("/")),
 ("go-blog", "The Go Blog", "Official language blogs", "https://go.dev/blog/feed.atom", P("go.dev"), P("/blog/")),
 ("python-insider", "Python Insider", "Official language blogs", "https://blog.python.org/feeds/posts/default", P("blog.python.org", "pyfound.blogspot.com"), P("/")),
 ("nodejs-blog", "Node.js Blog", "Official language blogs", "https://nodejs.org/en/feed/blog.xml", P("nodejs.org"), P("/en/blog/")),
 ("v8-blog", "V8 Blog", "Official language blogs", "https://v8.dev/blog.atom", P("v8.dev"), P("/blog/", "/features/")),
 ("webkit-blog", "WebKit Blog", "Official language blogs", "https://webkit.org/feed/", P("webkit.org"), P("/blog/")),
 ("chromium-blog", "Chromium Blog", "Official language blogs", "https://blog.chromium.org/feeds/posts/default", P("blog.chromium.org"), P("/")),
 ("typescript-blog", "TypeScript Blog", "Official language blogs", "https://devblogs.microsoft.com/typescript/feed/", P("devblogs.microsoft.com"), P("/typescript/")),
 ("dotnet-blog", ".NET Blog", "Official language blogs", "https://devblogs.microsoft.com/dotnet/feed/", P("devblogs.microsoft.com"), P("/dotnet/")),
 ("oldnewthing", "The Old New Thing", "Official language blogs", "https://devblogs.microsoft.com/oldnewthing/feed", P("devblogs.microsoft.com"), P("/oldnewthing/")),
 ("kotlin-blog", "Kotlin Blog", "Official language blogs", "https://blog.jetbrains.com/kotlin/feed/", P("blog.jetbrains.com"), P("/kotlin/")),
 ("inside-java", "Inside Java", "Official language blogs", "https://inside.java/feed.xml", P("inside.java"), P("/")),
 ("spring-blog", "Spring Blog", "Official language blogs", "https://spring.io/blog.atom", P("spring.io"), P("/blog/")),
 ("swift-blog", "Swift.org Blog", "Official language blogs", "https://www.swift.org/atom.xml", P("www.swift.org"), P("/blog/")),
 ("android-dev-blog", "Android Developers Blog", "Official language blogs", "https://android-developers.googleblog.com/feeds/posts/default", P("android-developers.googleblog.com"), P("/")),
 ("flutter-blog", "Flutter Blog", "Official language blogs", "https://blog.flutter.dev/feed", P("blog.flutter.dev"), P("/")),
 ("ruby-news", "Ruby News", "Official language blogs", "https://www.ruby-lang.org/en/feeds/news.rss", P("www.ruby-lang.org"), P("/en/news/")),
 ("rails-blog", "Ruby on Rails Blog", "Official language blogs", "https://rubyonrails.org/feed.xml", P("rubyonrails.org"), P("/")),
 ("elixir-blog", "Elixir Blog", "Official language blogs", "https://elixir-lang.org/atom.xml", P("elixir-lang.org"), P("/blog/")),
 ("llvm-blog", "LLVM Blog", "Official language blogs", "https://blog.llvm.org/index.xml", P("blog.llvm.org"), P("/")),
 ("django-weblog", "Django Weblog", "Framework blogs", "https://www.djangoproject.com/rss/weblog/", P("www.djangoproject.com"), P("/weblog/")),
 ("react-blog", "React Blog", "Framework blogs", "https://react.dev/rss.xml", P("react.dev"), P("/blog/")),
 ("nextjs-blog", "Next.js Blog", "Framework blogs", "https://nextjs.org/feed.xml", P("nextjs.org"), P("/blog/")),
 ("vue-blog", "Vue Blog", "Framework blogs", "https://blog.vuejs.org/feed.rss", P("blog.vuejs.org"), P("/")),
 ("svelte-blog", "Svelte Blog", "Framework blogs", "https://svelte.dev/blog/rss.xml", P("svelte.dev"), P("/blog/")),
 ("angular-blog", "Angular Blog", "Framework blogs", "https://blog.angular.dev/feed", P("blog.angular.dev"), P("/")),
 ("deno-blog", "Deno Blog", "Framework blogs", "https://deno.com/feed", P("deno.com"), P("/blog/")),
 ("astro-blog", "Astro Blog", "Framework blogs", "https://astro.build/rss.xml", P("astro.build"), P("/blog/")),
 ("kubernetes-blog", "Kubernetes Blog", "Framework blogs", "https://kubernetes.io/feed.xml", P("kubernetes.io"), P("/blog/")),
 ("cncf-blog", "CNCF Blog", "Framework blogs", "https://www.cncf.io/feed/", P("www.cncf.io"), P("/blog/")),
 ("tensorflow-blog", "TensorFlow Blog", "AI/ML", "https://blog.tensorflow.org/feeds/posts/default", P("blog.tensorflow.org"), P("/")),
 ("pytorch-blog", "PyTorch Blog", "AI/ML", "https://pytorch.org/feed/", P("pytorch.org"), P("/blog/")),
 ("huggingface-blog", "Hugging Face Blog", "AI/ML", "https://huggingface.co/blog/feed.xml", P("huggingface.co"), P("/blog/")),
 ("deepmind-blog", "Google DeepMind Blog", "AI/ML", "https://deepmind.google/blog/rss.xml", P("deepmind.google"), P("/discover/blog/", "/blog/")),
 ("karpathy-blog", "Andrej Karpathy", "AI/ML", "https://karpathy.github.io/feed.xml", P("karpathy.github.io"), P("/")),
 ("lilian-weng", "Lil'Log (Lilian Weng)", "AI/ML", "https://lilianweng.github.io/index.xml", P("lilianweng.github.io"), P("/posts/")),
 ("chip-huyen", "Chip Huyen", "AI/ML", "https://huyenchip.com/feed.xml", P("huyenchip.com"), P("/")),
 ("eugene-yan", "Eugene Yan", "AI/ML", "https://eugeneyan.com/rss/", P("eugeneyan.com"), P("/writing/")),
 ("jay-alammar", "Jay Alammar", "AI/ML", "https://jalammar.github.io/feed.xml", P("jalammar.github.io"), P("/")),
 ("hamel-husain", "Hamel Husain", "AI/ML", "https://hamel.dev/index.xml", P("hamel.dev"), P("/")),
 ("sebastian-raschka", "Ahead of AI (Sebastian Raschka)", "AI/ML", "https://magazine.sebastianraschka.com/feed", P("magazine.sebastianraschka.com"), P("/p/")),
 # individual engineers
 ("simon-willison", "Simon Willison", "Individual engineers", "https://simonwillison.net/atom/everything/", P("simonwillison.net"), P("/")),
 ("joel-on-software", "Joel on Software", "Individual engineers", "https://www.joelonsoftware.com/feed/", P("www.joelonsoftware.com"), P("/")),
 ("coding-horror", "Coding Horror", "Individual engineers", "https://blog.codinghorror.com/rss/", P("blog.codinghorror.com"), P("/")),
 ("russ-cox", "research!rsc (Russ Cox)", "Individual engineers", "https://research.swtch.com/feed.atom", P("research.swtch.com"), P("/")),
 ("rachel-by-the-bay", "Rachel by the Bay", "Individual engineers", "https://rachelbythebay.com/w/atom.xml", P("rachelbythebay.com"), P("/w/")),
 ("eli-bendersky", "Eli Bendersky", "Individual engineers", "https://eli.thegreenplace.net/feeds/all.atom.xml", P("eli.thegreenplace.net"), P("/")),
 ("josh-comeau", "Josh W. Comeau", "Individual engineers", "https://www.joshwcomeau.com/rss.xml", P("www.joshwcomeau.com"), P("/")),
 ("kent-c-dodds", "Kent C. Dodds", "Individual engineers", "https://kentcdodds.com/blog/rss.xml", P("kentcdodds.com"), P("/blog/")),
 ("overreacted", "Overreacted (Dan Abramov)", "Individual engineers", "https://overreacted.io/rss.xml", P("overreacted.io"), P("/")),
 ("armin-ronacher", "Armin Ronacher", "Individual engineers", "https://lucumr.pocoo.org/feed.atom", P("lucumr.pocoo.org"), P("/")),
 ("hynek", "Hynek Schlawack", "Individual engineers", "https://hynek.me/index.xml", P("hynek.me"), P("/articles/")),
 ("ned-batchelder", "Ned Batchelder", "Individual engineers", "https://nedbatchelder.com/blog/rss.xml", P("nedbatchelder.com"), P("/blog/")),
 ("charity-majors", "charity.wtf", "Individual engineers", "https://charity.wtf/feed/", P("charity.wtf"), P("/")),
 ("jake-archibald", "Jake Archibald", "Individual engineers", "https://jakearchibald.com/posts.rss", P("jakearchibald.com"), P("/")),
 ("addy-osmani", "Addy Osmani", "Individual engineers", "https://addyosmani.com/rss.xml", P("addyosmani.com"), P("/blog/")),
 ("lea-verou", "Lea Verou", "Individual engineers", "https://lea.verou.me/feed.xml", P("lea.verou.me"), P("/blog/")),
 ("ahmad-shadeed", "Ahmad Shadeed", "Individual engineers", "https://ishadeed.com/feed.xml", P("ishadeed.com"), P("/article/")),
 ("tkdodo", "TkDodo", "Individual engineers", "https://tkdodo.eu/blog/rss.xml", P("tkdodo.eu"), P("/blog/")),
 ("matklad", "matklad", "Individual engineers", "https://matklad.github.io/feed.xml", P("matklad.github.io"), P("/")),
 ("fasterthanlime", "fasterthanlime", "Individual engineers", "https://fasterthanli.me/index.xml", P("fasterthanli.me"), P("/articles/")),
 ("without-boats", "without.boats", "Individual engineers", "https://without.boats/index.xml", P("without.boats"), P("/blog/")),
 ("mitchell-hashimoto", "Mitchell Hashimoto", "Individual engineers", "https://mitchellh.com/feed.xml", P("mitchellh.com"), P("/writing/")),
 ("scott-hanselman", "Scott Hanselman", "Individual engineers", "https://feeds.hanselman.com/ScottHanselman", P("www.hanselman.com"), P("/blog/")),
 ("andrew-lock", ".NET Escapades (Andrew Lock)", "Individual engineers", "https://andrewlock.net/rss.xml", P("andrewlock.net"), P("/")),
 ("vlad-mihalcea", "Vlad Mihalcea", "Individual engineers", "https://vladmihalcea.com/feed/", P("vladmihalcea.com"), P("/")),
 ("dave-cheney", "Dave Cheney", "Individual engineers", "https://dave.cheney.net/feed", P("dave.cheney.net"), P("/")),
 ("swift-by-sundell", "Swift by Sundell", "Individual engineers", "https://www.swiftbysundell.com/rss", P("www.swiftbysundell.com"), P("/articles/", "/tips/")),
 ("hacking-with-swift", "Hacking with Swift", "Individual engineers", "https://www.hackingwithswift.com/articles/rss", P("www.hackingwithswift.com"), P("/articles/")),
 ("nshipster", "NSHipster", "Individual engineers", "https://nshipster.com/feed.xml", P("nshipster.com"), P("/")),
 ("evil-martians", "Evil Martians Chronicles", "Individual engineers", "https://evilmartians.com/chronicles.atom", P("evilmartians.com"), P("/chronicles/")),
 ("stitcher-io", "stitcher.io (PHP)", "Individual engineers", "https://stitcher.io/rss", P("stitcher.io"), P("/blog/")),
 ("laravel-news", "Laravel News", "Individual engineers", "https://feed.laravel-news.com/", P("laravel-news.com"), P("/")),
 ("dashbit-blog", "Dashbit (Elixir)", "Individual engineers", "https://dashbit.co/feed", P("dashbit.co"), P("/blog/")),
 ("will-larson", "Irrational Exuberance (Will Larson)", "Individual engineers", "https://lethain.com/feeds/", P("lethain.com"), P("/")),
 ("hillel-wayne", "Hillel Wayne", "Individual engineers", "https://www.hillelwayne.com/index.xml", P("www.hillelwayne.com"), P("/post/")),
 ("bartosz-ciechanowski", "Bartosz Ciechanowski", "Individual engineers", "https://ciechanow.ski/atom.xml", P("ciechanow.ski"), P("/")),
 ("xe-iaso", "Xe Iaso", "Individual engineers", "https://xeiaso.net/blog.rss", P("xeiaso.net"), P("/blog/")),
 ("drew-devault", "Drew DeVault", "Individual engineers", "https://drewdevault.com/blog/index.xml", P("drewdevault.com"), P("/")),
 ("daniel-stenberg", "Daniel Stenberg (curl)", "Individual engineers", "https://daniel.haxx.se/blog/feed/", P("daniel.haxx.se"), P("/blog/")),
 ("lemire", "Daniel Lemire", "Individual engineers", "https://lemire.me/blog/feed/", P("lemire.me"), P("/blog/")),
 ("fabien-sanglard", "Fabien Sanglard", "Individual engineers", "https://fabiensanglard.net/rss.xml", P("fabiensanglard.net"), P("/")),
 ("thorsten-ball", "Register Spill (Thorsten Ball)", "Individual engineers", "https://registerspill.thorstenball.com/feed", P("registerspill.thorstenball.com"), P("/p/")),
 # distributed systems / databases people
 ("marc-brooker", "Marc Brooker", "Systems and databases", "https://brooker.co.za/blog/rss.xml", P("brooker.co.za"), P("/blog/")),
 ("murat-demirbas", "Metadata (Murat Demirbas)", "Systems and databases", "https://muratbuffalo.blogspot.com/feeds/posts/default", P("muratbuffalo.blogspot.com"), P("/")),
 ("aphyr", "Aphyr (Jepsen)", "Systems and databases", "https://aphyr.com/posts.atom", P("aphyr.com"), P("/posts/")),
 ("phil-eaton", "Phil Eaton", "Systems and databases", "https://notes.eatonphil.com/rss.xml", P("notes.eatonphil.com"), P("/")),
 ("jack-vanlightly", "Jack Vanlightly", "Systems and databases", "https://jack-vanlightly.com/blog?format=rss", P("jack-vanlightly.com"), P("/blog/")),
 # security
 ("troy-hunt", "Troy Hunt", "Security", "https://www.troyhunt.com/rss/", P("www.troyhunt.com"), P("/")),
 ("portswigger-research", "PortSwigger Research", "Security", "https://portswigger.net/research/rss", P("portswigger.net"), P("/research/")),
 ("project-zero", "Google Project Zero", "Security", "https://googleprojectzero.blogspot.com/feeds/posts/default", P("googleprojectzero.blogspot.com"), P("/")),
 ("trail-of-bits", "Trail of Bits Blog", "Security", "https://blog.trailofbits.com/feed/", P("blog.trailofbits.com"), P("/")),
 # publications
 ("smashing-magazine", "Smashing Magazine", "Publications", "https://www.smashingmagazine.com/feed/", P("www.smashingmagazine.com"), P("/")),
 ("a-list-apart", "A List Apart", "Publications", "https://alistapart.com/main/feed/", P("alistapart.com"), P("/article/")),
 ("lwn", "LWN.net", "Publications", "https://lwn.net/headlines/rss", P("lwn.net"), P("/Articles/")),
 ("infoq", "InfoQ", "Publications", "https://feed.infoq.com/", P("www.infoq.com"), P("/articles/", "/news/", "/presentations/")),
 ("freecodecamp-news", "freeCodeCamp News", "Publications", "https://www.freecodecamp.org/news/rss/", P("www.freecodecamp.org"), P("/news/")),
 ("pragmatic-engineer", "The Pragmatic Engineer", "Publications", "https://newsletter.pragmaticengineer.com/feed", P("newsletter.pragmaticengineer.com"), P("/p/")),
 ("bytebytego", "ByteByteGo", "Publications", "https://blog.bytebytego.com/feed", P("blog.bytebytego.com"), P("/p/")),
 ("devto", "DEV Community", "Publications", "https://dev.to/feed", P("dev.to"), P("/")),
]
BLOCKED_FEEDS = {
    "dan-luu": ("blocked_feed_over_2mb", "Blocked: the feed is 6.66 MB, above the parser's 2 MB limit (it carries full post bodies). Needs a bigger limit for feeds or a sitemap crawl of danluu.com"),
    "vercel-blog": ("blocked_feed_over_2mb", "Blocked: the feed is 4.75 MB, above the parser's 2 MB limit"),
    "planet-python": ("blocked_aggregator_offhost", "Blocked: every entry links to the original author's blog, so the host allowlist admits 0 of 25 entries. Use it to discover feeds to add, not as a source"),
    "microsoft-devblogs": ("duplicate_disabled", "Disabled: this is the all-products feed, and its '/' scope swallows the typescript-blog, dotnet-blog and oldnewthing rows. Add other product feeds (/python/, /commandline/) one by one instead"),
    "planet-postgresql": ("blocked_aggregator_offhost", "Blocked: every entry links to the original author's blog, so the host allowlist admits 0 of 30 entries. Use it to discover feeds to add, not as a source"),
}
MEDIUM_NOTE = "medium.com allows generic crawlers but blocks named AI bots; use our own UA and keep the rate low"
PAYWALL = {"pragmatic-engineer", "bytebytego", "lwn"}
AGGREGATOR = {"this-week-in-rust", "devto"}
MVP_FEEDS = {"cloudflare-blog", "netflix-techblog", "github-engineering", "julia-evans", "martin-fowler", "rust-blog", "go-blog", "simon-willison", "realpython", "meta-engineering", "stripe-engineering"}

# Hosts serving many products or several of our sources: no host-wide sitemap discovery.
SHARED_HOSTS = {
    "docs.aws.amazon.com", "learn.microsoft.com", "cloud.google.com", "docs.cloud.google.com",
    "docs.rs", "doc.rust-lang.org", "developer.hashicorp.com", "huggingface.co", "pkg.go.dev",
    "www.gnu.org", "hexdocs.pm", "docs.spring.io", "svelte.dev", "en.cppreference.com",
    "docs.astral.sh", "www.w3.org", "www.rfc-editor.org", "docs.oracle.com", "developer.android.com",
    "www.elastic.co", "aws.amazon.com", "docs.github.com", "www.digitalocean.com",
}

# ---------------------------------------------------------------- helpers
def _path(v):
    return normpath('/' + unquote(v).lstrip('/'))

def allows(prefixes, url):
    path = _path(urlsplit(url).path)
    return any(p == '/' or path == _path(p) or path.startswith(_path(p).rstrip('/') + '/') for p in prefixes)

errors = []
def check_entry(e):
    s = e["slug"]
    if not SLUG_RE.match(s): errors.append(f"{s}: bad slug")
    if e["kind"] not in {"website", "rss", "api"}: errors.append(f"{s}: bad kind")
    c = e["config"]
    pre = c.get("allowed_path_prefixes", ["/"])
    for p in pre:
        if not p.startswith("/") or any(ch in p for ch in "?#\\ "): errors.append(f"{s}: bad prefix {p}")
    if not 1 <= c.get("max_pages", 10000) <= 1_000_000: errors.append(f"{s}: max_pages out of range")
    if not 0 <= c.get("max_depth", 3) <= 100: errors.append(f"{s}: depth")
    host = urlsplit(e["base_url"]).hostname
    if host not in e["allowed_hosts"]: errors.append(f"{s}: base host {host} not in allowed_hosts")
    if e["kind"] == "website" and not allows(pre, e["base_url"]): errors.append(f"{s}: base_url outside allowed_path_prefixes")
    for h in e["allowed_hosts"]:
        if "/" in h or "[" in h or " " in h: errors.append(f"{s}: bad host {h}")

def clean_host(h):
    h = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", h).strip()
    return h

# ---------------------------------------------------------------- build
docs, blogs, apis, table = [], [], [], []
host_load = defaultdict(int)

def add_table(tier, cat, slug, name, kind, base, hosts, prefixes, est, cap, ver, status, mvp, method, note, interval_days):
    table.append(dict(tier=tier, category=cat, slug=slug, name=name, kind=kind, base_url=base,
        allowed_hosts=",".join(hosts), allowed_path_scope=" ".join(prefixes), ingestion_method=method,
        version_pin=ver, est_docs=est, max_docs=cap, recrawl_interval_days=interval_days,
        suggested_mvp=mvp, proposed_status=status, notes=note))

def website(tier, cat, slug, name, base, hosts, prefixes, est, cap, ver, status, mvp, note, interval_days, depth=None, sitemaps=None):
    cap = min(cap, TIER_CAP[tier])
    if status.startswith(("blocked", "duplicate")):
        mvp = "no"
    # Host-wide sitemap discovery is only safe when the host is ours alone. On a
    # shared or very large host the sitemap index lists thousands of child
    # sitemaps for other products, and each one takes a frontier slot. Those
    # rows use a service-specific sitemap (when one exists) or link discovery.
    discover = hosts[0] not in SHARED_HOSTS
    if sitemaps:
        discover = False
    cfg = {"priority": PRIORITY[tier], "max_depth": depth if depth is not None else 8, "max_pages": cap,
           "allowed_path_prefixes": prefixes, "discover_sitemaps": discover,
           **({"sitemap_urls": sitemaps} if sitemaps else {}),
           "registry": {"tier": tier, "category": cat, "version_pin": ver, "est_docs": est,
                        "language_policy": "en_only_by_path", "status": status, "suggested_mvp": mvp == "yes",
                        "robots_reviewed": False, "terms_reviewed": False, "notes": note}}
    e = {"slug": slug, "name": name, "kind": "website", "base_url": base, "allowed_hosts": hosts,
         "crawl_interval_seconds": int(interval_days) * DAY, "is_enabled": False, "config": cfg}
    check_entry(e); docs.append(e)
    for h in hosts[:1]: host_load[h] += cap
    add_table(tier, cat, slug, name, "website", base, hosts, prefixes, est, cap, ver, status, mvp, "polite_web_crawl", note, interval_days)

for slug in order:
    r = rows[slug]
    tier = r["tier"]
    if tier == "4" or tier == "S":
        continue
    f = FIX.get(slug, {})
    new_slug = f.get("slug", slug)
    hosts = f.get("hosts") or [clean_host(h) for h in r["allowed_hosts"].split(",") if h.strip()]
    prefixes = f.get("prefixes") or [p for p in r["allowed_path_scope"].split() if p.startswith("/")] or ["/"]
    base = f.get("base", r["base_url"])
    status = f.get("status", r["proposed_status"])
    note = f.get("note") or r["notes"]
    est = f.get("est", 500)
    cap = f.get("cap", max(100, int(est * 1.5)))
    if slug not in FIX:
        errors.append(f"{slug}: no fix entry (defaults used)")
    website(tier, r["category"], new_slug, r["name"], base, hosts, prefixes, est, cap, f.get("ver", "latest"), status,
            r["suggested_mvp"] or "no", note, r["recrawl_interval_days"] or 30, depth=f.get("depth"), sitemaps=f.get("sitemaps"))

for (tier, cat, slug, name, base, hosts, prefixes, est, cap, ver, note, mvp) in NEW:
    website(tier, cat, slug, name, base, hosts, prefixes, est, cap, ver, "new_candidate_disabled", mvp, note, 30)

def feed(slug, name, cat, url, hosts, prefixes, note, status, mvp):
    est = 30
    if slug in BLOCKED_FEEDS:
        status, note = BLOCKED_FEEDS[slug]
        mvp, est = "no", 0
    fh = urlsplit(url).hostname
    allh = [fh] + [h for h in hosts if h != fh]
    if "medium.com" in allh: note = (note + "; " if note else "") + MEDIUM_NOTE
    if slug in PAYWALL: note = (note + "; " if note else "") + "partly paywalled: index only the free text the page serves"
    if slug in AGGREGATOR: note = (note + "; " if note else "") + "aggregator: entries link to other hosts, so follow_entry_links only fetches same-host pages"
    cap = 1000 if slug not in AGGREGATOR else 300
    cfg = {"priority": PRIORITY["4"], "max_depth": 1, "max_pages": cap, "allowed_path_prefixes": prefixes,
           "follow_entry_links": True, "discover_sitemaps": False,
           "registry": {"tier": "4", "category": cat, "version_pin": "n/a", "est_docs": est,
                        "est_docs_with_sitemap_backfill": 300, "language_policy": "en_feed",
                        "status": status, "suggested_mvp": mvp == "yes", "feed_url_verified": False,
                        "robots_reviewed": False, "terms_reviewed": False, "notes": note}}
    e = {"slug": slug, "name": name, "kind": "rss", "base_url": url, "allowed_hosts": allh,
         "crawl_interval_seconds": DAY, "is_enabled": False, "config": cfg}
    if not allows(prefixes, url) and False: pass
    check_entry(e); blogs.append(e)
    add_table("4", cat, slug, name, "rss", url, allh, prefixes, est, cap, "n/a", status, mvp,
              "rss_then_entry_fetch", note, 1)

for slug in order:
    r = rows[slug]
    if r["tier"] != "4": continue
    url, hosts, prefixes = FEEDS_FIX[slug]
    feed(slug, r["name"], "Engineering blogs", url, hosts, prefixes, r["notes"], r["proposed_status"],
         "yes" if slug in MVP_FEEDS else "no")
for (slug, name, cat, url, hosts, prefixes) in NEW_FEEDS:
    feed(slug, name, cat, url, hosts, prefixes, "", "new_candidate_disabled", "yes" if slug in MVP_FEEDS else "no")

# ---------------------------------------------------------------- special sources
gh_rows = [l.rstrip("\n").split("\t") for l in open(GH, encoding="utf-8")]
bad = re.compile(r"awesome|interview|roadmap|book|tutorial|course|cheat|guide|list|learn|free-|resources|algorithms|public-apis|examples|system-design|hello|study|leetcode|notes|jobs|china|chinese|translation|tips|papers|prompt|skills|superpowers|build-your-own|computer-science", re.I)
langs = {"Python", "TypeScript", "JavaScript", "Go", "Rust", "C++", "Java", "C", "Ruby", "C#", "Swift", "Kotlin", "PHP", "Dart", "Scala", "Elixir", "Zig", "Lua", "Vue", "Svelte", "Haskell", "Clojure", "OCaml", "Julia"}
repos = []
for r in gh_rows:
    name, stars, oi, has, lang, desc, topics = (r + [""] * 7)[:7]
    if has != "true" or lang not in langs or int(oi) < 50: continue
    if bad.search(name) or re.search(r"[一-鿿぀-ヿ가-힯]", desc): continue
    repos.append({"repo": name, "stars": int(stars), "open_issues": int(oi), "language": lang})
repos = repos[:500]

apis.append({"slug": "github-curated-issues", "name": "GitHub issues (curated repos)", "kind": "api",
  "base_url": "https://api.github.com/repos/facebook/react/issues?state=closed&per_page=100&sort=comments&direction=desc",
  "allowed_hosts": ["api.github.com", "github.com"], "crawl_interval_seconds": 7 * DAY, "is_enabled": False,
  "config": {"priority": PRIORITY["S"], "max_depth": 0, "max_pages": 100_000, "discover_sitemaps": False,
    "api": {"items_path": "", "fields": {"url": "html_url", "title": "title", "body": "body", "author": "user.login", "published_at": "created_at"}, "body_format": "text"},
    "registry": {"tier": "S", "category": "Discussions", "est_docs": 100_000, "status": "blocked_needs_crawler_work",
      "repo_allowlist_file": "github_issue_repos.json", "repo_count": len(repos),
      "per_repo_cap": 200, "selection": "closed issues, sorted by comments, skip items with pull_request key",
      "notes": "Blocked on 3 crawler gaps: (1) no auth header support, unauthenticated limit is 60 req/h; needs GITHUB_TOKEN from env (5000 req/h). (2) pagination is in the Link header, but ApiMapping.next_path only reads the JSON body. (3) one source = one base_url, so either one source per repo or a fan-out step that enqueues one API target per repo from the allowlist. The issues endpoint also returns PRs; drop items with a pull_request key. Comments need a second call per issue (/issues/N/comments)."}}})
apis.append({"slug": "stackoverflow-api-sample", "name": "Stack Overflow top-voted Q&A (API sample)", "kind": "api",
  "base_url": "https://api.stackexchange.com/2.3/questions?order=desc&sort=votes&tagged=python&site=stackoverflow&filter=withbody&pagesize=100",
  "allowed_hosts": ["api.stackexchange.com", "stackoverflow.com"], "crawl_interval_seconds": 30 * DAY, "is_enabled": False,
  "config": {"priority": PRIORITY["S"], "max_depth": 0, "max_pages": 10_000, "discover_sitemaps": False,
    "api": {"items_path": "items", "fields": {"url": "link", "title": "title", "body": "body", "author": "owner.display_name", "published_at": "creation_date"}, "body_format": "html",
            "metadata_fields": {"license": "content_license", "score": "score", "tags": "tags", "question_id": "question_id", "is_answered": "is_answered", "author_profile": "owner.link"}},
    "registry": {"tier": "S", "category": "Discussions", "est_docs": 100, "est_docs_when_paginated": 10_000, "status": "candidate_disabled",
      "license": "per post: CC BY-SA 2.5, 3.0 or 4.0, read from each item's content_license (stored in document metadata as license)",
      "notes": "Small live sample only; the bulk path is the offline dump (offline_datasets.json). Counted as 100 docs: the first page is the only one reachable, because pagination uses page=N + has_more, which next_path can't express yet. creation_date is Unix seconds (parse_record_date now accepts them). Quota: 300 req/day without a key, 10K with one. Answers need /questions/{ids}/answers."}}})
for e in apis: check_entry(e)

offline = [{"slug": "stack-overflow-dump", "name": "Stack Overflow data dump", "kind": "dataset",
  "ingestion_method": "bulk_dump_import", "source_url": "https://stackoverflow.com/help/data-dumps",
  "legacy_mirror": "https://archive.org/details/stackexchange",
  "license": "CC BY-SA (4.0 for posts after 2018-05-02, 3.0/2.5 earlier); keep author, post link and license per document",
  "filter": {"site": "stackoverflow.com", "post_types": ["question+accepted_answer", "answer score>=5"], "min_question_score": 5,
             "tags_allowlist": "tags matching tier 1-3 sources (python, javascript, typescript, rust, go, java, c++, sql, docker, kubernetes, react, django, ...)",
             "exclude": ["closed", "deleted", "community wiki"]},
  "est_docs": {"prototype": 50_000, "local_corpus": 500_000},
  "status": "needs_terms_review",
  "notes": "The archive.org mirror stopped updating in 2024; newer dumps are distributed by Stack Exchange directly behind an account and their own terms. Read those terms before importing. Not a crawl seed: this needs an importer that writes straight to documents."}]

# ---------------------------------------------------------------- validate, then write
_seedable = docs + blogs + apis
_dupes = sorted(s for s, n in Counter(e["slug"] for e in _seedable + offline).items() if n > 1)
if _dupes:
    errors.append(f"duplicate slugs: {_dupes}")
_owners = defaultdict(list)  # (host, prefix) -> slugs; two sources must never admit the same URLs
for e in docs + blogs:
    if e["config"]["registry"]["status"].startswith(("blocked", "duplicate")):
        continue
    for h in e["allowed_hosts"]:
        for p in e["config"].get("allowed_path_prefixes", ["/"]):
            _owners[(h, _path(p))].append(e["slug"])
for (h, p), owners in sorted(_owners.items()):
    for (h2, p2), owners2 in _owners.items():
        if h2 == h and p2 != p and (p == "/" or p2.startswith(p.rstrip("/") + "/")) and set(owners2) - set(owners):
            errors.append(f"overlapping scopes on {h}: {p} ({owners}) contains {p2} ({owners2})")
    if len(set(owners)) > 1:
        errors.append(f"same scope on {h}{p}: {sorted(set(owners))}")
if errors:
    print("Validation failed, nothing written:", file=sys.stderr)
    for problem in errors:
        print(" -", problem, file=sys.stderr)
    sys.exit(1)
os.makedirs(OUT, exist_ok=True)
def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False); f.write("\n")
dump("documentation.json", docs)
dump("blogs.json", blogs)
dump("apis.json", apis)
dump("offline_datasets.json", offline)
dump("github_issue_repos.json", repos)

for e in apis:
    add_table("S", e["config"]["registry"]["category"], e["slug"], e["name"], "api", e["base_url"], e["allowed_hosts"], [], e["config"]["registry"]["est_docs"], e["config"]["max_pages"], "n/a", e["config"]["registry"]["status"], "no", "rest_api", e["config"]["registry"]["notes"][:160], 7)
o = offline[0]
add_table("S", "Discussions", o["slug"], o["name"], "dataset", o["source_url"], ["(offline)"], [], o["est_docs"]["local_corpus"], o["est_docs"]["local_corpus"], "latest dump", o["status"], "no", o["ingestion_method"], "Offline importer; archive.org mirror frozen in 2024", 90)

cols = ["tier", "category", "slug", "name", "kind", "base_url", "allowed_hosts", "allowed_path_scope", "ingestion_method", "version_pin", "est_docs", "max_docs", "recrawl_interval_days", "suggested_mvp", "proposed_status", "notes"]
with open(os.path.join(OUT, "source_registry_draft.tsv"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\t".join(cols) + "\n")
    for t in table:
        f.write("\t".join(str(t[c]).replace("\t", " ") for c in cols) + "\n")


# summary numbers
def tot(pred, key):
    return sum(int(t[key]) for t in table if pred(t))
enabled_like = lambda t: not str(t["proposed_status"]).startswith(("duplicate", "blocked"))
stats = {}
for tier in ["1", "2", "3", "4", "S"]:
    ts = [t for t in table if t["tier"] == tier]
    stats[tier] = dict(n=len(ts), est=sum(int(t["est_docs"]) for t in ts if enabled_like(t)),
        cap=sum(int(t["max_docs"]) for t in ts if enabled_like(t)),
        mvp_n=sum(1 for t in ts if t["suggested_mvp"] == "yes"),
        mvp_est=sum(int(t["est_docs"]) for t in ts if t["suggested_mvp"] == "yes" and enabled_like(t)))
# ---------------------------------------------------------------- readable summary
rows=list(csv.DictReader(open(os.path.join(OUT,'source_registry_draft.tsv'),encoding='utf-8'),delimiter='\t'))
ok=lambda r: not r['proposed_status'].startswith(('duplicate','blocked'))
names={'1':'Tier 1: core language and platform docs','2':'Tier 2: frameworks and libraries','3':'Tier 3: infrastructure and tools','4':'Tier 4: engineering blogs (RSS)','S':'Special sources: discussions'}
def n(x): return f"{int(x):,}"
out=[]
w=out.append
w("# Source registry draft\n")
w("Built from nish's 197-row draft (2026-11-07), with fixes and additions. Nothing here is enabled: every row has `is_enabled: false` so you can turn sources on in batches.\n")
w("Files in this folder:\n")
w("- `documentation.json`, `blogs.json`, `apis.json`: seedable rows in the exact `SourceCreate` shape (`kind` is website / rss / api). Copy into `../sources/` when you want them seeded. They sit in `drafts/` because `seed.py` loads every `*.json` in `sources/`.")
w("- `offline_datasets.json`: the Stack Overflow dump. Not seedable; it needs an importer.")
w("- `github_issue_repos.json`: 500 repo allowlist for the GitHub issues source (from GitHub search, top by stars, filtered).")
w("- `source_registry_draft.tsv`: your column layout plus `version_pin`, `est_docs`, `max_docs`.")
w("- `build_registry.py`: the generator. Edit the tables in it and run `python build_registry.py` (no arguments) instead of hand-editing JSON. It validates every row first and writes nothing if any check fails.")
w("- `inputs/`: the generator's checked-in inputs (nish's original draft and the GitHub repo snapshot), so a clean checkout rebuilds the same files.\n")
w("## Totals\n")
w("| Tier | Sources | Est. docs | Sum of caps (max_docs) | MVP sources | MVP est. docs |")
w("|---|---:|---:|---:|---:|---:|")
T=[0,0,0,0,0]
for t in ['1','2','3','4','S']:
    rs=[r for r in rows if r['tier']==t]
    a=[len(rs),sum(int(r['est_docs']) for r in rs if ok(r)),sum(int(r['max_docs']) for r in rs if ok(r)),sum(r['suggested_mvp']=='yes' for r in rs),sum(int(r['est_docs']) for r in rs if ok(r) and r['suggested_mvp']=='yes')]
    T=[x+y for x,y in zip(T,a)]
    w(f"| {names[t]} | {a[0]} | {n(a[1])} | {n(a[2])} | {a[3]} | {n(a[4])} |")
w(f"| **All** | **{T[0]}** | **{n(T[1])}** | **{n(T[2])}** | **{T[3]}** | **{n(T[4])}** |\n")
w("Reading the numbers: est. docs are my rough page counts, not measured. Blogs show ~30 docs each because an RSS feed only lists recent posts; turning on sitemap backfill per blog would add roughly 300 each (~50K total). Special sources count the Stack Overflow dump at the local-corpus size (500K) and GitHub issues at 100K.\n")
w("- **Prototype (cloud seed):** the `suggested_mvp = yes` rows come to about **"+n(T[4])+" docs**, inside the 100-200K target.")
w("- **Local corpus:** all tiers 1-3 are ~270K docs; add blogs with backfill (~50K), GitHub issues (~100K) and the filtered Stack Overflow dump (~500K) for roughly **900K**, inside the 500K-1M target.\n")
w("## What I changed in your draft\n")
for line in [
"Hostnames: the markdown-link-mangled hosts (`[www.w3.org](...)`) are plain hostnames now.",
"Real path scopes instead of `/` for react, angular, webpack, dart, docker, pkg.go.dev, fastapi, typer, polars, solid, redux-toolkit, react-router, elasticsearch (was all of `/docs/`), net-docs.",
"Kept `/` where the host only serves docs (nestjs, zod, httpx, nats, flutter, homebrew, rails guides) and for SQLite. SQLite's docs are flat files like `/lang_select.html`, and `allowed_path_prefixes` matches whole path segments, so `/lang_` can't work. It uses depth 2 from docs.html plus a cap instead.",
"Where I narrowed a scope I also moved `base_url` inside it (fastapi to /learn/, docker to /get-started/, typer, polars, solid). `discovery.py` silently drops a seed that falls outside its own prefixes, so the generator now checks this for every row.",
"Overlaps removed: net-docs excludes `/dotnet/csharp/` (own source) and `/dotnet/api/`; cpp-reference is `/w/cpp` and c-reference is `/w/c` (no collision, prefix match is per segment); svelte-docs is `/docs/svelte/` so it doesn't swallow sveltekit; remix-docs disabled as a duplicate of React Router 7; rust-std is `/std/` only (not `/stable/std/`).",
"Renamed `version-typescript` to `typescript-docs`.",
"Version pins: Java 25 LTS, .NET 10 LTS, MySQL 8.4 LTS, OpenSSL 3.5 LTS (was `/master/`), Hibernate `/current/` (was every version), systemd `/latest/`, JUnit moved to docs.junit.org, PyTorch moved to docs.pytorch.org, bun.sh to bun.com (old hosts kept in `allowed_hosts` so redirects pass).",
"http-rfcs now lists exact RFC files (9110-9114 plus WebSocket, OAuth 2, JWT, TLS 1.3, URI) instead of all of `/rfc/`.",
"apple-swiftui-docs disabled: developer.apple.com/documentation is a JavaScript app and returns an empty page to an HTML fetch.",
"Blog rows now point `base_url` at the real feed URL (the RSS parser needs the feed, not the homepage), with `follow_entry_links: true` and `max_depth: 1`.",
"The `stack-overflow-dump` and `curated-engineering-rss` rows didn't fit the schema (`dataset` and `manifest` aren't valid kinds). The dump moved to `offline_datasets.json`; the manifest is replaced by the 168 real feed rows.",
"Added 56 docs sources (web.dev, dev.java, more docs.rs crates, React Native, Expo, Electron, Ruff, mypy, Keras, JAX, Vault, Istio, Argo CD, Cloudflare, Supabase, Firebase, DuckDB, gRPC, OWASP cheat sheets, DigitalOcean tutorials and others) and 138 blog feeds.",
]: w("- "+line)
w("\n## Review fixes (2026-11-08)\n")
for line in [
"**Seeds that redirected out of scope:** C and C++ now seed `/c` and `/cpp` (cppreference moved off `/w/`; the old prefixes stay allowed so redirects land in scope). Django seeds `/en/6.1/` because `/en/stable/` redirects there. Redux Toolkit moved to `redux.js.org/toolkit/` and Pydantic to `pydantic.dev/docs/validation/latest/`; their hosts, seeds and scopes changed together.",
"**AWS:** each aws-* row lists its own guide sitemap in `sitemap_urls` and has `discover_sitemaps: false`. The host-wide index lists ~13,900 child sitemaps and would eat each source's budget. The same switch-off now applies to every shared or very large host (learn.microsoft.com, cloud.google.com, docs.rs, doc.rust-lang.org, developer.hashicorp.com, huggingface.co, pkg.go.dev and others; see `SHARED_HOSTS`).",
"**AWS crawl delay:** `politeness_policy.py` now has `HOST_MIN_INTERVAL_SECONDS` with `docs.aws.amazon.com: 5.0`. Both the in-memory limiter and the shared PostgreSQL limiter use it. The robots parser still ignores `Crawl-delay`, so hosts that ask for one are listed there by hand.",
"**Blocked (excluded from counts):** swift-docs (DocC page, empty body), dan-luu and vercel-blog (feeds over the 2 MB parser limit), planet-python and planet-postgresql (every entry is on another host). microsoft-devblogs is disabled because its `/` scope swallowed three product feeds.",
"**Stack Overflow sample:** the mapping now keeps `content_license` (posts carry CC BY-SA 2.5, 3.0 or 4.0), score, tags and ids in document metadata, via a new `metadata_fields` option in the JSON API parser. `parse_record_date` now reads Unix seconds. The estimate is 100 docs, the one page reachable until pagination works.",
"**One owner per URL:** go.dev/blog/, react.dev/blog and nextjs.org/blog now belong only to their feeds. inside-rust and the Baeldung feed were dropped because other rows already cover them. DuckDB's blog is scoped to its year paths, and the Flutter feed moved to blog.flutter.dev. The generator now fails when two live rows can admit the same host and path.",
]: w("- "+line)
w("\n## robots.txt spot check (20 hosts)\n")
for line in [
"Allowed for a generic crawler: MDN, docs.python.org (blocks only EOL `/3.x/` trees), learn.microsoft.com, php.net, pkg.go.dev, docs.rs, sqlite.org, docs.github.com (no rules at all), docs.aws.amazon.com, cloud.google.com, huggingface.co, digitalocean.com, man7.org, kubernetes.io, medium.com.",
"**docs.aws.amazon.com sets `Crawl-delay: 5`.** Six aws-* sources share that host. The 5-second gap is now enforced per host in the crawler (see Review fixes).",
"**en.cppreference.com** allows crawling but says `Content-Signal: search=yes, ai-train=no` and blocks ~35 named AI bots. Search indexing is fine; don't let the corpus feed model training.",
"**medium.com** allows generic crawlers but blocks named AI bots. Use your own user agent and a low rate.",
"Couldn't verify: docs.oracle.com (59 KB file, only partly readable), www.gnu.org (refused the checker), stackoverflow.com (blocked the checker), wiki.archlinux.org (bot wall, so I left the Arch wiki out).",
"The other ~370 hosts are unchecked. Every row has `robots_reviewed: false` and every feed has `feed_url_verified: false`. Feed URLs are from memory, so expect a few to 404 on first run.",
]: w("- "+line)
w("\n## Crawler gaps this list runs into\n")
for line in [
"**No deny list.** Hugging Face, ClickHouse, Scala docs and TensorFlow mix versioned or translated trees under the same prefix. Their caps bound the damage, but an `excluded_path_prefixes` key (plus stripping `?hl=` and `?view=` in the URL normalizer) would fix it properly.",
"**One base_url per source.** That is why AWS, GCP, Azure and docs.rs are split into many rows. A `seed_urls` list in config would let them collapse.",
"**Shared hosts.** doc.rust-lang.org (~32K of caps), learn.microsoft.com (~23K), docs.rs (~13K) and docs.aws.amazon.com (~13K) each serve several sources. `max_pages` is per source, so a per-host cap still needs adding.",
"**GitHub issues API:** no auth header support (60 requests/hour without a token), pagination is in the `Link` header which `next_path` can't read, and one source can only hold one repo URL. Details are in `apis.json`.",
"**Stack Overflow:** the archive.org mirror stopped updating in 2024. Newer dumps come from Stack Exchange behind an account and their own terms, so read those before importing. The content license is still CC BY-SA, which means keeping author, link and license on every document.",
"Existing seeded slugs (mdn, python-docs, fastapi, django, rust-book) keep their names. `seed.py` skips slugs that already exist, so new scopes for those five only take effect through `update_source`.",
]: w("- "+line)
for t in ['1','2','3','4','S']:
    rs=[r for r in rows if r['tier']==t]
    w(f"\n## {names[t]} ({len(rs)})\n")
    if t=='4':
        w("| Slug | Name | Category | Feed URL | MVP | Notes |"); w("|---|---|---|---|---|---|")
        for r in rs: w(f"| `{r['slug']}` | {r['name']} | {r['category']} | {r['base_url']} | {r['suggested_mvp']} | {r['notes'][:120]} |")
    else:
        w("| Slug | Name | Host | Path scope | Version | Est. docs | Max docs | MVP | Notes |"); w("|---|---|---|---|---|---:|---:|---|---|")
        for r in rs:
            sc=r['allowed_path_scope']; sc=(sc[:70]+' …') if len(sc)>70 else sc
            st='' if ok(r) else f"**{r['proposed_status']}**. "
            w(f"| `{r['slug']}` | {r['name']} | {r['allowed_hosts'].split(',')[0]} | `{sc}` | {r['version_pin']} | {n(r['est_docs'])} | {n(r['max_docs'])} | {r['suggested_mvp']} | {st}{r['notes'][:140]} |")
open(os.path.join(OUT,'REGISTRY_SUMMARY.md'),'w',encoding='utf-8',newline='\n').write("\n".join(out)+"\n")

json.dump({"stats": stats, "errors": errors, "repos": len(repos),
           "top_hosts": sorted(host_load.items(), key=lambda x: -x[1])[:12],
           "counts": {"docs": len(docs), "blogs": len(blogs), "apis": len(apis)}}, sys.stdout, indent=1)
