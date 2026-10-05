# Developer's Eye

Developer's Eye is a developer-focused search engine that aggregates, normalizes, and ranks technical knowledge from across the developer ecosystem.

Instead of searching the entire web like a general-purpose search engine, Developer's Eye focuses on the sources developers actually use:

- Official documentation
- GitHub repositories
- GitHub issues and discussions
- Stack Overflow
- Reddit
- DEV Community and technical blogs
- Developer events
- LeetCode and learning resources when relevant

The goal is to make technical search faster, more structured, and more useful for developers.

---


# For Developer’s Eye, the main estimated stack we settled on is:
- Backend: Python, FastAPI, Pydantic, SQLAlchemy
- Database: PostgreSQL
- Crawler: httpx + BeautifulSoup / lxml
- Search: custom inverted index + BM25
- Background jobs: Redis + ARQ
- Frontend: Next.js + TypeScript
- Infrastructure: Docker + Docker Compose

## Example

A developer searches:

```text
fastapi async backend
```

Developer's Eye may return:

### Documentation

- FastAPI async and concurrency documentation
- Python `asyncio` documentation

### GitHub

- Relevant FastAPI repositories
- GitHub issues discussing async behavior
- Example implementations

### Discussions

- Stack Overflow questions about `async def`
- Reddit discussions about async FastAPI in production

### Articles

- DEV Community tutorials
- Engineering blog posts

### Events

- Relevant Python or backend meetups, if any exist

Developer's Eye should not blindly search every source for every query.

The system should determine which source categories are useful for the user's intent.

For example:

```text
two pointer palindrome
```

may surface:

- LeetCode problems
- Algorithm explanations
- GitHub implementations
- Stack Overflow discussions

While:

```text
python conference nyc
```

may prioritize:

- Developer events
- Conference pages
- Community discussions

---

# Why Developer's Eye?

Developers currently search across many separate platforms:

```text
Google
GitHub
Stack Overflow
Reddit
Documentation
DEV Community
LeetCode
Luma
```

Developer's Eye attempts to combine these into one search experience.

Instead of manually searching:

```text
fastapi async reddit
fastapi async github
fastapi async stackoverflow
fastapi async docs
```

the user searches once:

```text
fastapi async
```

and Developer's Eye gathers relevant developer-specific sources automatically.

---

# Core Idea

Developer's Eye treats different sources as different kinds of technical evidence.

| Source | Purpose |
|---|---|
| Official Docs | Authoritative explanations |
| GitHub Repositories | Real implementations |
| GitHub Issues | Real engineering problems |
| Stack Overflow | Debugging and Q&A |
| Reddit | Developer discussions and opinions |
| DEV / Blogs | Tutorials and deep dives |
| LeetCode | Related algorithm practice |
| Events | Relevant meetups and conferences |

The search engine can then group and rank results based on relevance.

---

# High-Level Architecture

```text
                        User Query
                            |
                            v
                     Query Analyzer
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
        Docs              Code            Discussions
          |                 |                  |
     Documentation        GitHub        Reddit / StackOverflow
          |                 |                  |
          +-----------------+------------------+
                            |
                            v
                       Normalization
                            |
                            v
                       Search Index
                            |
                            v
                     Ranking / BM25
                            |
                            v
                        FastAPI API
                            |
                            v
                       Next.js UI
```

---

# Data Acquisition

Developer's Eye uses two primary methods to collect data.

## 1. Crawling

Used for sources such as:

- Documentation websites
- Technical blogs
- Developer tutorials

Pipeline:

```text
URL
 |
 v
Crawler
 |
 v
HTML
 |
 v
Parser
 |
 v
Clean Text
 |
 v
Normalized Document
 |
 v
Search Index
```

The crawler will eventually support:

- URL normalization
- duplicate detection
- crawl depth limits
- rate limiting
- retries
- timeouts
- `robots.txt`
- recrawling
- content-change detection

---

## 2. APIs

Structured platforms should use APIs where appropriate.

Examples:

```text
GitHub API
Reddit API
Stack Exchange API
Event APIs / feeds
```

These results will be converted into the same internal document format used by crawled pages.

---

# Normalized Document Model

Different sources should eventually become a common document representation.

Example:

```python
Document(
    id=123,
    source="github",
    type="issue",
    title="FastAPI async database calls",
    content="...",
    url="https://github.com/...",
    author="...",
    tags=["python", "fastapi", "async"],
    created_at="...",
    indexed_at="...",
)
```

This allows the ranking system to search across different platforms consistently.

---

# Search Engine

The first search implementation will use traditional information retrieval.

## Tokenization

Example:

```text
FastAPI background tasks with Redis
```

becomes:

```text
fastapi
background
tasks
redis
```

---

## Inverted Index

Instead of scanning every document for every query, Developer's Eye creates an inverted index.

Example documents:

```text
Document 1:
FastAPI background tasks

Document 2:
Redis background workers

Document 3:
FastAPI authentication
```

Index:

```text
fastapi
  -> document 1
  -> document 3

background
  -> document 1
  -> document 2

redis
  -> document 2
```

---

# Ranking

The initial ranking algorithm will use **BM25**.

Pipeline:

```text
Query
 |
 v
Tokenization
 |
 v
Inverted Index Lookup
 |
 v
Candidate Documents
 |
 v
BM25 Scoring
 |
 v
Sort by Relevance
 |
 v
Search Results
```

Example:

```text
Query:
fastapi background jobs
```

Possible output:

```text
1. FastAPI Background Tasks        14.82
2. Redis Workers with FastAPI       9.47
3. Async Task Processing            6.22
```

---

# Query-Aware Search

Not every source should be searched for every query.

Developer's Eye should eventually classify the user's intent.

Example:

```text
fastapi async backend
```

Relevant sources:

```text
Docs
GitHub
Stack Overflow
Reddit
Blogs
```

Probably irrelevant:

```text
LeetCode
```

Another example:

```text
binary search rotated array
```

Relevant:

```text
LeetCode
Algorithm documentation
GitHub
Stack Overflow
Blogs
```

Another example:

```text
python meetup nyc
```

Relevant:

```text
Events
Meetups
Community discussions
```

---

# MVP

The first version should stay intentionally small.

## Developer's Eye v0.1

Initial sources:

```text
Documentation
GitHub
Reddit
```

Initial flow:

```text
User Query
    |
    v
+---------+---------+---------+
|         |         |         |
Docs    GitHub    Reddit
|         |         |
+---------+---------+
          |
          v
      Normalize
          |
          v
        BM25
          |
          v
      FastAPI
          |
          v
    Search Results
```

### v0.1 Goals

- Crawl one documentation website
- Store documents in PostgreSQL
- Normalize document content
- Tokenize documents
- Build an inverted index
- Implement BM25 ranking
- Integrate GitHub search
- Integrate Reddit search
- Expose search through FastAPI
- Return ranked search results as JSON

Example API:

```http
GET /search?q=fastapi+async
```

Example response:

```json
{
  "query": "fastapi async",
  "results": [
    {
      "title": "Concurrency and async / await",
      "source": "docs",
      "url": "https://fastapi.tiangolo.com/...",
      "snippet": "Details about async and await...",
      "score": 14.82
    }
  ]
}
```

---

# Planned Versions

## v0.2

Add:

- Stack Overflow
- source filtering
- result categories
- better snippets

## v0.3

Add:

- DEV Community
- technical blogs
- improved ranking
- popularity signals
- freshness signals

## v0.4

Add:

- developer events
- Luma / event integrations
- location-aware event results

## v0.5

Add:

- LeetCode
- learning resources
- query-aware vertical search

## Future

Possible future features:

- semantic search
- embeddings
- hybrid BM25 + vector ranking
- query understanding
- result deduplication
- source authority scoring
- personalization
- AI-generated result summaries
- RAG-based answers
- distributed crawling
- distributed indexing
- observability
- caching
- search analytics

---

# Tech Stack

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
```

## Database

```text
PostgreSQL
```

## Crawling

```text
httpx
BeautifulSoup / lxml
```

## Search

```text
BM25
Custom inverted index
```

## Background Jobs

Planned:

```text
Redis
ARQ
```

## Frontend

Planned:

```text
Next.js
TypeScript
```

## Infrastructure

Planned:

```text
Docker
Docker Compose
```

---

# Project Structure

```text
developers-eye/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   │
│   ├── crawler/
│   │   ├── fetcher.py
│   │   ├── parser.py
│   │   └── crawler.py
│   │
│   ├── search/
│   │   ├── tokenizer.py
│   │   ├── index.py
│   │   ├── bm25.py
│   │   └── ranking.py
│   │
│   ├── integrations/
│   │   ├── github/
│   │   └── reddit/
│   │
│   ├── workers/
│   │
│   └── tests/
│
├── frontend/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# Development Philosophy

Developer's Eye is primarily a **search-engine and backend engineering project**.

The focus is not on building a complex frontend or wrapping an LLM around existing search APIs.

The project is intended to explore:

```text
Web crawling
Information retrieval
Search indexing
Ranking algorithms
Backend APIs
Async programming
Databases
Caching
Background workers
Distributed systems
Developer APIs
```

AI features can be added later, but the core search infrastructure should work independently.

---

# Current Status

```text
[ ] Project setup
[ ] FastAPI backend
[ ] PostgreSQL
[ ] Documentation crawler
[ ] Content parser
[ ] Document normalization
[ ] Tokenizer
[ ] Inverted index
[ ] BM25 ranking
[ ] Search API
[ ] GitHub integration
[ ] Reddit integration
[ ] Frontend
```

---

# First Milestone

The first milestone is simple:

```bash
curl "http://localhost:8000/search?q=fastapi+background+tasks"
```

Developer's Eye should return ranked results from its own indexed developer content.

Once that works, the project has a functioning search-engine core.
