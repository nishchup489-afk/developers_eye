
1. **Offline ingestion**: crawl/index content before users search.
2. **Live/fresh connectors**: selectively call third-party APIs at query time when freshness matters.


```text
                           DEVELOPER'S EYE
================================================================================

                               USER
                                |
                                v
                         Next.js Frontend
                                |
                                v
                      Load Balancer / Gateway
                                |
                                v
                           FastAPI API
                                |
                                v
                      SEARCH ORCHESTRATOR
                                |
              +-----------------+------------------+
              |                 |                  |
              v                 v                  v
        Query Processor    Source Router      Search Cache
              |                 |                Redis
              |                 |
              +--------+--------+
                       |
                       v
                Candidate Retrieval
                       |
         +-------------+--------------+
         |                            |
         v                            v
   LOCAL SEARCH INDEX           LIVE CONNECTORS
         |                            |
   Docs / Blogs /            GitHub / Reddit /
   stored API data           Stack Exchange / Events
         |                            |
         +-------------+--------------+
                       |
                       v
                 Result Merger
                       |
                       v
                 Deduplication
                       |
                       v
                     Ranker
                       |
                       v
              Diversity / Grouping
                       |
                       v
               Snippet Generator
                       |
                       v
                Response Builder
                       |
                       v
                     USER
```

## 1. The two halves



```text
OFFLINE SIDE
collect → clean → normalize → deduplicate → index

ONLINE SIDE
query → understand → retrieve → rank → serve
```

But Developer’s Eye adds a third concept:

```text
LIVE THIRD-PARTY RETRIEVAL
```

because GitHub, Reddit, events, etc. can change rapidly.

So the full architecture becomes:

```text
                  OFFLINE
                     |
        crawlers + API ingestion
                     |
                     v
                local index
                     |
                     |
USER → ONLINE SEARCH + optional LIVE API calls
                     |
                     v
                  ranking
```

---

# 2. Source Registry

Before crawling anything, have a central registry describing every source Developer’s Eye knows about.

Example:

```python
Source(
    name="fastapi_docs",
    source_type="documentation",
    acquisition="crawler",
    base_url="https://fastapi.tiangolo.com",
    authority_score=0.95,
    recrawl_interval_hours=48,
)
```

Another:

```python
Source(
    name="github",
    source_type="code",
    acquisition="api",
    authority_score=0.90,
)
```

Another:

```python
Source(
    name="reddit",
    source_type="discussion",
    acquisition="api",
    authority_score=0.65,
)
```

This lets the system know:

```text
FastAPI docs
→ crawl

GitHub
→ API

Reddit
→ API

Stack Overflow
→ API

random engineering blog
→ crawl
```

---

# 3. Offline pipeline

This is where most of the search-engine engineering happens.

```text
                         SOURCE REGISTRY
                               |
                               v
                         SCHEDULER
                               |
               +---------------+---------------+
               |                               |
               v                               v
        WEB CRAWL PIPELINE              API INGESTION
               |                               |
               v                               v
         URL Frontier                   GitHub API
               |                        Reddit API
               |                        Stack Exchange API
               |                        etc.
               v                               |
        Crawler Workers                        |
               |                               |
               +---------------+---------------+
                               |
                               v
                          RAW CONTENT
                               |
                               v
                         NORMALIZATION
                               |
                               v
                        DEDUPLICATION
                               |
                               v
                           INDEXER
                               |
                               v
                         SEARCH INDEX
```

---

# 4. Crawler subsystem

Your crawler itself should have several components.

```text
Seed URLs
   |
   v
URL Discovery
   |
   v
URL Canonicalizer
   |
   v
Robots Service
   |
   v
Crawl Frontier
   |
   v
Priority Scheduler
   |
   v
Fetcher Workers
   |
   v
HTML Parser
   |
   +------> Discover new URLs
   |
   v
Content Extractor
```

### Seed URLs

You don't “scan the internet.”

You start with trusted domains.

Example:

```text
https://fastapi.tiangolo.com/
https://docs.python.org/
https://redis.io/docs/
https://docs.djangoproject.com/
```

Those become seeds.

---

# 5. URL discovery

Crawler fetches:

```text
fastapi.tiangolo.com/tutorial/
```

and discovers:

```text
/tutorial/body/
/tutorial/query-params/
/tutorial/dependencies/
/async/
```

Those URLs enter the crawler frontier.

Not immediately fetched.

They are scheduled.

---

# 6. URL canonicalizer

URLs can represent the same page:

```text
example.com/page
example.com/page/
example.com/page?utm_source=twitter
example.com/page#section
```

Normalize them into one canonical URL.

Example:

```text
https://example.com/page
```

This prevents duplicate crawling.

---

# 7. Robots service

Separate component:

```text
domain
   |
   v
robots.txt lookup
   |
   v
Redis cache
```

Example key:

```text
robots:fastapi.tiangolo.com
```

Crawler asks:

```text
Can DeveloperEyeBot fetch /tutorial/async/?
```

The cached rules answer.

You don't fetch `robots.txt` for every URL.

---

# 8. Crawl frontier

The URL frontier is effectively the crawler's task queue.

Example:

```text
Priority 100
FastAPI docs

Priority 90
Python docs

Priority 70
popular engineering blog

Priority 20
old article
```

You can initially implement this with Redis.

Conceptually:

```text
Redis priority queue

score     URL
100       fastapi.tiangolo.com/async
95        docs.python.org/asyncio
80        redis.io/docs
```

---

# 9. Crawl priority

Eventually:

```text
crawl_priority =
    source_authority
  + popularity
  + freshness_requirement
  + update_frequency
  - crawl_depth_penalty
```

You do not need that algorithm immediately.

v0:

```text
docs > blogs
```

is enough.

---

# 10. Fetcher

Technology:

```text
Python
httpx
asyncio
```

Fetcher responsibilities:

```text
HTTP GET
timeouts
redirects
retry
compression
rate limits
status codes
content type detection
```

Example flow:

```text
URL
 ↓
httpx
 ↓
200 OK
 ↓
HTML
```

---

# 11. Parser / extractor

Technology:

```text
BeautifulSoup
or
lxml
```

Extract:

```text
title
main text
headings
links
code blocks
description
canonical URL
language hints
published date
author
```

Developer’s Eye should care about **code blocks** much more than a generic search engine.

For example:

```html
<pre>
async def endpoint():
    ...
</pre>
```

should not simply disappear during cleaning.

---

# 12. Raw storage

Your earlier S3 understanding fits here.

Later:

```text
                    RAW DATA

Crawler ────────────────> S3 / Cloudflare R2

raw HTML
PDF
JSON responses
possibly archived versions
```

But v0.1:

```text
PostgreSQL is enough.
```

Don't add S3 just because Google uses blob storage.

Add it when you actually have significant raw content.

---

# 13. API ingestion workers

The other side of ingestion:

```text
                API INGESTION
                     |
       +-------------+--------------+
       |             |              |
       v             v              v
    GitHub         Reddit       Stack Exchange
```

### GitHub

Use GitHub's REST API initially.

GitHub officially exposes repositories and issues through its REST API, and public repository resources can often be read without authentication, while authentication provides broader access and higher limits. [GitHub Docs](https://docs.github.com/en/rest/issues/issues?utm_source=chatgpt.com)

You want things like:

```text
repositories
issues
pull requests
possibly discussions
metadata
stars
languages
updated_at
comments
```

Example normalized result:

```python
Document(
    source="github",
    document_type="issue",
    title="Async database connections leaking",
    body="...",
    url="...",
    popularity_score=143,
)
```

---

# 14. Reddit connector

Prefer Reddit's API rather than crawling Reddit pages.

Reddit provides an API with OAuth-scoped endpoints and listing-based pagination. [Reddit](https://www.reddit.com/dev/api/?utm_source=chatgpt.com)

You care about:

```text
post title
post body
subreddit
score
comment count
created_at
top comments
URL
```

Possible Developer’s Eye document:

```python
Document(
    source="reddit",
    document_type="discussion",
    title="FastAPI async vs sync in production",
    body="...",
    community="r/FastAPI",
    popularity_score=...
)
```

---

# 15. Stack Overflow

Use the Stack Exchange API.

The current official API is v2.3 and provides application keys/OAuth plus throttling controls. [Stack Exchange](https://api.stackexchange.com/?utm_source=chatgpt.com)

Collect:

```text
question title
question body
tags
score
accepted answer
answer score
creation time
last activity
```

Normalize:

```python
Document(
    source="stackoverflow",
    document_type="qa",
    title="When should I use async def in FastAPI?",
    body="...",
    tags=["python", "fastapi", "async"],
)
```

---

# 16. DEV / engineering blogs

Two possibilities:

```text
API
or
crawler
```

If the platform exposes an appropriate API, use it.

Otherwise:

```text
HTTP crawler
→ HTML extraction
```

For random engineering blogs, crawling is the natural approach.

---

# 17. Events

This should be a separate **vertical**.

Possible sources:

```text
Luma
Meetup
conference sites
community pages
```

Do not make event retrieval part of every query.

Query:

```text
fastapi async backend
```

probably:

```text
events = low priority
```

Query:

```text
python meetup NYC
```

then:

```text
events = high priority
```

Use an API/feed where available and permitted. Otherwise crawl public event pages while respecting site rules.

---

# 18. LeetCode

I would **not make LeetCode ingestion part of v1**.

Reason:

You don't need it to prove your architecture, and relying on unofficial endpoints or scraping is unnecessary complexity.

Later, query routing can recognize:

```text
binary search rotated sorted array
```

and present a learning/practice vertical.

---

# 19. Normalization engine

This is critical.

Every source has different data.

GitHub:

```json
{
  "name": "...",
  "body": "...",
  "stargazers_count": 4000
}
```

Reddit:

```json
{
  "title": "...",
  "selftext": "...",
  "score": 900
}
```

Crawler:

```html
<title>...</title>
<p>...</p>
```

All become:

```python
Document(
    id=UUID,
    source="github",
    external_id="...",
    document_type="issue",

    title="...",
    body="...",
    url="...",
    canonical_url="...",

    author="...",
    language="en",

    tags=["python", "fastapi"],

    published_at=...,
    updated_at=...,
    indexed_at=...,

    popularity_score=...,
    authority_score=...,

    content_hash="..."
)
```

That common schema is one of the central abstractions of Developer’s Eye.

---

# 20. Deduplication engine

You need two kinds.

### URL dedupe

```text
canonical_url already exists?
```

### Content dedupe

```text
hash(cleaned_content)
```

Example:

```text
SHA-256(content)
```

Then:

```text
same hash
→ same content
```

Eventually you can add near-duplicate detection for copied blog posts.

Not necessary initially.

---

# 21. Database layout

### PostgreSQL

Use it for:

```text
documents
sources
URLs
crawl states
API metadata
authors
tags
crawl history
timestamps
jobs
```

Example:

```text
documents
---------
id
source_id
type
title
body
url
canonical_url
content_hash
language
published_at
updated_at
indexed_at
```

---

# 22. Redis

Redis has several jobs.

```text
Redis
├── crawl frontier
├── ARQ queue
├── robots.txt cache
├── search-result cache
├── rate-limit counters
└── temporary distributed locks
```

This makes Redis genuinely useful here instead of adding it to the resume for no reason.

---

# 23. Background jobs

Use:

```text
ARQ + Redis
```

Workers:

```text
crawler_worker
github_ingestion_worker
reddit_ingestion_worker
stackoverflow_worker
indexing_worker
recrawl_worker
cleanup_worker
```

Architecture:

```text
              Scheduler
                  |
                  v
                Redis
                  |
          +-------+-------+
          |       |       |
          v       v       v
        Worker  Worker  Worker
```

---

# 24. Indexer

Now your documents are normalized.

Indexer pipeline:

```text
Document
   |
   v
text normalization
   |
   v
tokenization
   |
   v
term extraction
   |
   v
document statistics
   |
   v
inverted index
```

---

# 25. Inverted index

Example corpus:

```text
doc1 = "FastAPI async endpoints"
doc2 = "Python async programming"
doc3 = "FastAPI authentication"
```

Index:

```text
fastapi
→ doc1
→ doc3

async
→ doc1
→ doc2

python
→ doc2
```

But your real posting entry becomes closer to:

```text
async:
[
    {doc_id: 1, tf: 2, positions: [3, 17]},
    {doc_id: 2, tf: 5, positions: [8, 21, 44, 90, 121]}
]
```

---

# 26. Search index storage

For your learning project:

### v1

Build it yourself.

```text
Python
custom inverted index
BM25
```

This demonstrates you understand IR.

Later:

```text
OpenSearch
Elasticsearch
Typesense
Meilisearch
```

could replace or supplement it.

But if you immediately use Elasticsearch, you hide much of the interesting engineering.

---

# 27. Offline index architecture

Eventually:

```text
                    INDEXER
                       |
             +---------+---------+
             |         |         |
             v         v         v
           Shard 0   Shard 1   Shard 2
```

Shard selection might use:

```python
shard_id = hash(document_id) % shard_count
```

But again:

**do not implement distributed shards for v1.**

Learn it.

Document it.

Scale into it later.

---

# 28. Online side

User searches:

```text
fastapi async backend
```

Request:

```http
GET /search?q=fastapi+async+backend
```

Flow:

```text
User
 ↓
Next.js
 ↓
FastAPI
 ↓
Query Processor
 ↓
Source Router
 ↓
Retriever
 ↓
Ranker
 ↓
Result Merger
 ↓
Response
```

---

# 29. Query processor

Input:

```text
FastAPI async backend!!!!
```

Normalize:

```text
fastapi async backend
```

Tokenize:

```python
["fastapi", "async", "backend"]
```

Later:

```text
spell correction
synonyms
stemming
language detection
entity recognition
intent detection
```

---

# 30. Query intent engine

This is one of Developer’s Eye's defining pieces.

Input:

```text
fastapi async backend
```

Could classify:

```text
intent:
    technical_learning

verticals:
    docs
    github
    stackoverflow
    reddit
    blogs
```

Input:

```text
two sum leetcode
```

becomes:

```text
intent:
    algorithm_practice

verticals:
    leetcode
    github
    articles
```

Input:

```text
python meetup NYC
```

becomes:

```text
intent:
    events

verticals:
    events
```

Initially this can be rules.

Do NOT immediately use an LLM.

Example:

```python
if "meetup" in query or "conference" in query:
    vertical = "events"
```

Later, ML/LLMs can improve classification.

---

# 31. Source router

Once intent is known:

```text
Query Analyzer
      |
      v
Source Router
      |
 +----+----------------+
 |    |       |        |
Docs GitHub Reddit StackOverflow
```

The router decides:

```text
search local index?
call live API?
skip source?
```

---

# 32. Hybrid retrieval

This is where Developer’s Eye becomes more interesting.

Search from two places simultaneously:

```text
                     Query
                       |
              +--------+--------+
              |                 |
              v                 v
        LOCAL RETRIEVAL      LIVE APIs
              |                 |
         BM25 index         GitHub
                           Reddit
                           events
              |                 |
              +--------+--------+
                       |
                       v
                 candidate pool
```

Why?

Your local index is:

```text
fast
controlled
rankable
```

Live APIs are:

```text
fresh
dynamic
```

---

# 33. Search cache

Before expensive retrieval:

```text
Redis
```

Key:

```text
search:v1:fastapi_async_backend
```

If query was searched recently:

```text
cache hit
→ return results
```

Otherwise:

```text
cache miss
→ retrieval pipeline
```

TTL:

```text
5-30 minutes
```

depending on source freshness.

---

# 34. Candidate retrieval

Suppose query:

```text
fastapi async backend
```

Local BM25 might retrieve:

```text
500 candidate documents
```

You do not perform expensive ranking against the entire corpus.

You rank candidates.

```text
10,000,000 documents
        ↓
inverted index
        ↓
500 candidate docs
        ↓
ranking
        ↓
20 results
```

---

# 35. BM25

Initial ranking:

```text
BM25(query, document)
```

Measures roughly:

```text
term relevance
term rarity
term frequency
document length
```

Example:

```text
Official FastAPI async docs        13.8
GitHub FastAPI async issue          9.7
Random Python article               5.4
```

---

# 36. Developer’s Eye ranking

BM25 alone isn't enough eventually.

Use:

```text
final_score =
    BM25
  + source_authority
  + freshness
  + popularity
  + exact_title_match
  + developer_quality
```

Conceptually:

```python
score = (
    bm25_score
    + 2.0 * authority
    + 1.2 * freshness
    + 0.8 * popularity
    + 1.5 * title_match
)
```

Don't copy these exact weights. Tune experimentally.

---

# 37. Source-specific quality signals

### GitHub

```text
stars
forks
activity
last update
issue comments
repository health
```

### Reddit

```text
score
comments
subreddit relevance
freshness
```

### Stack Overflow

```text
accepted answer
question score
answer score
views
```

### Documentation

```text
official domain
version
freshness
```

---

# 38. Authority model

Example:

```text
FastAPI official docs     1.00
Python docs               1.00
GitHub official repo      0.95
Stack Overflow            0.80
Reddit                    0.60
random blog               0.40
```

But authority should not completely override relevance.

A perfectly matching GitHub issue may still beat a barely related official documentation page.

---

# 39. Diversity engine

Without diversity:

```text
1 Reddit
2 Reddit
3 Reddit
4 Reddit
5 Reddit
```

Bad experience.

Instead:

```text
1 Official docs
2 GitHub issue
3 Stack Overflow
4 Reddit
5 Blog
```

Possible algorithm:

```text
maximum N results per source in top K
```

Later use more sophisticated diversification.

---

# 40. Deduplication during search

You may have:

```text
DEV article
personal blog mirror
Medium repost
```

all containing the same article.

Search-time dedupe removes redundant results.

---

# 41. Snippet engine

Search result:

```text
FastAPI Concurrency and async / await
fastapi.tiangolo.com
```

needs:

```text
"...when your path operation uses async def,
FastAPI executes..."
```

Snippet generation should locate passages containing query terms.

This is not an LLM requirement.

Simple algorithm:

```text
find best text window containing most query terms
```

---

# 42. Result grouping

Developer’s Eye UI could display:

```text
BEST RESULTS

Documentation
GitHub
Discussions
Articles
Events
Practice
```

instead of one giant flat list.

This is a real product differentiator.

---

# 43. API response

Example:

```json
{
  "query": "fastapi async backend",
  "took_ms": 84,
  "results": [
    {
      "title": "Concurrency and async / await",
      "source": "fastapi_docs",
      "type": "documentation",
      "url": "...",
      "snippet": "...",
      "score": 14.92
    },
    {
      "title": "Async SQLAlchemy connection handling",
      "source": "github",
      "type": "issue",
      "url": "...",
      "snippet": "...",
      "score": 12.43
    }
  ]
}
```

---

# 44. Developer’s Eye API

Eventually:

```text
GET /search

GET /search/suggestions

GET /sources

GET /documents/{id}

GET /related

GET /health
```

Internal/admin:

```text
POST /crawl

POST /sources

GET /crawl/jobs

POST /reindex

GET /metrics
```

---

# 45. Search suggestions

As users type:

```text
fastapi as...
```

you could return:

```text
fastapi async
fastapi asyncio
fastapi async sqlalchemy
```

Initially based on:

```text
previous queries
popular indexed terms
```

Redis can cache these.

---

# 46. Observability

Later:

```text
OpenTelemetry
Prometheus
Grafana
structured logging
```

Metrics:

```text
search latency
p50
p95
p99

crawl success rate
crawl queue size
API errors
documents indexed/sec
cache hit rate
GitHub API quota
Reddit API quota
```

---

# 47. Third-party API rate limiting

Every connector needs its own limiter.

```text
GitHub connector
      |
      v
GitHub rate limiter

Reddit connector
      |
      v
Reddit rate limiter
```

Never allow:

```text
100 users
×
5 API calls
=
500 uncontrolled outbound calls
```

Use:

```text
Redis counters
queueing
caching
backoff
```

GitHub documents rate limiting and recommends authentication for higher limits. [GitHub Docs](https://docs.github.com/en/rest/using-the-rest-api?utm_source=chatgpt.com)

---

# 48. Failure handling

Suppose Reddit goes down.

Developer’s Eye should still work.

```text
Docs       ✓
GitHub     ✓
Reddit     X
Stack      ✓
```

Response can simply omit Reddit or mark it temporarily unavailable.

Do not make:

```text
Reddit failure
→ whole search request = HTTP 500
```

Each connector gets:

```text
timeout
retry
circuit breaker later
fallback to stored index
```

---

# 49. Security

API secrets:

```text
.env locally
secret manager in production
```

Never frontend.

Wrong:

```text
Next.js browser
→ GitHub token
```

Correct:

```text
Browser
→ FastAPI
→ GitHub API
```

---

# 50. Final technology stack

Your actual Developer’s Eye stack:

```text
Frontend
--------
Next.js
TypeScript

Backend
-------
Python
FastAPI
Pydantic
SQLAlchemy
asyncio

Database
--------
PostgreSQL

Crawler
-------
httpx
BeautifulSoup / lxml

Queues / Cache
--------------
Redis
ARQ

Search
------
custom tokenizer
custom inverted index
BM25

Third-party integrations
------------------------
GitHub REST API
Reddit API
Stack Exchange API
event APIs / feeds where available

Infrastructure
--------------
Docker
Docker Compose

Later
-----
S3 / Cloudflare R2
OpenTelemetry
Prometheus
Grafana
Kubernetes
possibly OpenSearch
```

---

# 51. Full production-style architecture

```text
                                  ┌─────────────────────┐
                                  │       USERS         │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │      Next.js        │
                                  │      Frontend       │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │ Load Balancer/API   │
                                  │       Gateway       │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │      FastAPI        │
                                  │     Search API      │
                                  └──────────┬──────────┘
                                             │
                                    ┌────────┴────────┐
                                    │ Search Cache    │
                                    │     Redis       │
                                    └────────┬────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │ Query Processor     │
                                  │ tokenizer           │
                                  │ intent classifier   │
                                  │ language detector   │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │    Source Router    │
                                  └───────┬─────┬───────┘
                                          │     │
                       ┌──────────────────┘     └──────────────────┐
                       ▼                                           ▼

              LOCAL SEARCH ENGINE                          LIVE CONNECTORS
              ───────────────────                          ───────────────

              Inverted Index                              GitHub API
                    │                                     Reddit API
                    ▼                                     Stack Exchange
                  BM25                                    Event APIs
                    │                                          │
                    └─────────────────┬────────────────────────┘
                                      │
                                      ▼
                              Candidate Merger
                                      │
                                      ▼
                              Search Deduplication
                                      │
                                      ▼
                                   Ranker
                                      │
                                      ▼
                                Diversifier
                                      │
                                      ▼
                              Snippet Generator
                                      │
                                      ▼
                              Response Builder
                                      │
                                      ▼
                                    USER


=============================== OFFLINE =================================


                            SOURCE REGISTRY
                                  │
                                  ▼
                              Scheduler
                                  │
                   ┌──────────────┴──────────────┐
                   │                             │
                   ▼                             ▼
             CRAWLER SYSTEM                API INGESTION
                   │                             │
            Seed Manager                  GitHub worker
                   │                      Reddit worker
            URL Discovery                 Stack worker
                   │                      Events worker
             Canonicalizer                      │
                   │                             │
             robots.txt                         │
                cache                           │
                   │                             │
              Frontier                          │
                   │                             │
             Prioritizer                        │
                   │                             │
             Fetch workers                      │
                   │                             │
              HTML parser                       │
                   │                             │
             ┌─────┴─────────────────────────────┘
             │
             ▼
       Normalization Engine
             │
             ▼
        Deduplication
       URL + content hash
             │
       ┌─────┴──────────┐
       │                │
       ▼                ▼
 PostgreSQL        Blob Storage
 metadata           raw HTML
 documents          PDFs/etc.
 crawl states
       │
       ▼
    INDEXER
       │
       ▼
 Tokenization
       │
       ▼
 Inverted Index
       │
       ▼
 BM25 Statistics
       │
       ▼
 Search Index
```

That is the **whole system** I would design toward.

But do not make the mistake of trying to implement that entire diagram immediately.

Your build order should be:

```text
v0.1
Crawler
→ parser
→ PostgreSQL
→ tokenizer
→ inverted index
→ BM25
→ /search
```

Then:

```text
v0.2
Redis
→ ARQ
→ crawler workers
→ crawl frontier
→ robots cache
```

Then:

```text
v0.3
GitHub API
→ normalized documents
→ unified search
```

Then:

```text
v0.4
Reddit + Stack Overflow
→ source router
→ merged ranking
→ diversity
```

Then:

```text
v0.5
Next.js UI
→ snippets
→ filters
→ grouped results
```

Then:

```text
v1.0
recrawling
freshness ranking
query cache
observability
live retrieval
failure handling
production deployment
```

If you actually implement even **60–70% of this yourself and can explain every box you drew**, no competent backend recruiter should categorize it as AI slop. There is almost no AI required for the core system at all. This is **information retrieval + backend + distributed-systems engineering**.