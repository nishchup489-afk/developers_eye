# Developer's Eye — Indexer: Selector

**Stage 01: Finding which documents need indexing**  
**File:** `crawler/src/indexer/selector.py`

---

## What is the selector?

We already built a crawler. It fetches developer documentation, extracts the useful content, and stores it in our PostgreSQL `document` table.

But our search engine cannot efficiently search through thousands of raw documents one by one. We need an **indexer** to prepare the searchable representation and save it in `search_index`.

Here comes the problem: **How does the indexer know what to work on?**

Imagine we have **15,600 documents** in our database:

- 12,000 were indexed yesterday.
- 2,000 are new and have never been indexed.
- 1,600 were indexed before, but their content has since changed.

We should not rebuild all 15,600 indexes every time the worker runs. That would waste CPU, database writes, and time.

**The selector's job is to find only the documents that need work.** It does not build indexes or write anything to the database.

```text
Crawler → document table
                |
                v
        SELECTOR (this file)
                |
                v
       IndexCandidate objects
                |
                v
        Builder / Analyzer
                |
                v
       Writer → search_index
```

The selector also finds documents that have become unavailable, so their old search results can be removed.

---

## First, understand the two tables

### `document` (crawler's stored content)

```text
id              = 42
canonical_url   = https://docs.python.org/3/tutorial/datastructures.html
title           = Data Structures
body            = ...
content_hash    = <SHA-256 of normalized document content>
updated_at      = Oct 23, 10:00 AM
last_seen_at    = Oct 26, 10:00 AM
is_available    = True
```

### `search_index` (searchable version)

```text
document_id     = 42
search_vector   = <PostgreSQL TSVECTOR>
indexed_hash    = v1:<SHA-256 of index-relevant data>
indexed_at      = Oct 24, 11:00 AM
```

**`last_seen_at` vs `updated_at`:** The crawler can see the same document 100 times without its content changing. `last_seen_at` changes on observation; `updated_at` changes when stored, index-relevant content changes. We care about `updated_at`, not every crawl.

**`content_hash` vs `indexed_hash`:** They are hashes of different representations, so we do **not** compare them directly. The `indexed_hash` starts with a version prefix such as `v1:`. The selector uses that prefix to detect indexes built by an old version of our indexing rules.

---

## When should a document be indexed?

We have three main cases:

| Case | Example | Selector result |
| --- | --- | --- |
| Never indexed | `document.id = 42` has no matching `search_index` row | Select it |
| Content changed | `updated_at` is newer than `indexed_at` | Select it |
| Indexer upgraded | Current version is `v2`, stored hash starts with `v1:` | Select it |
| Already up to date | Indexed after content update, correct version | Skip it |
| Page unavailable | `is_available = False` | Don't rebuild; check for removal |

This rule is the heart of our selector.

---

## Function 01: `_check_document_id()`

```python
def _check_document_id(document_id: int) -> None:
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")
```

Before querying the database, we reject invalid input.

```python
_check_document_id(42)     # Valid
_check_document_id(0)      # ValueError
_check_document_id(-5)     # ValueError
_check_document_id("42")   # ValueError
_check_document_id(True)   # ValueError
```

**Why `type(value) is int` instead of `isinstance(value, int)`?** Because Python treats `bool` as a subclass of `int`. With `isinstance`, `True` would accidentally be accepted as an ID.

---

## Function 02: `_outdated_index_condition()`

```python
def _outdated_index_condition(config: IndexerConfig):
    return or_(
        SearchIndex.document_id.is_(None),
        SearchIndex.indexed_at < Document.updated_at,
        ~SearchIndex.indexed_hash.startswith(config.index_hash_prefix),
    )
```

This is our **decision-making rule**. It builds a SQL condition using `or_()`, meaning **any one** of the three conditions is enough.

1. **No index exists:** `SearchIndex.document_id.is_(None)`. After an outer join, the missing index row appears as SQL `NULL`.
2. **Document changed:** The content's `updated_at` is later than the last successful indexing time.
3. **Old indexing version:** If our current `index_version = 2`, the configuration expects a `v2:` prefix. An index with `v1:` is stale even if the document content itself never changed.

The `~` before `.startswith()` means **NOT**.

Think of it as:

```text
needs_indexing = (
    index_does_not_exist
    OR document_changed_after_indexing
    OR index_version_is_old
)
```

**Important:** This function only constructs SQL. It doesn't execute a query or return `True` / `False` for a particular document.

---

## Function 03: `is_index_current()`

Sometimes we want to check **one specific document** instead of scanning the database.

```python
statement = (
    select(
        Document.is_available,
        Document.updated_at,
        SearchIndex.indexed_at,
        SearchIndex.indexed_hash,
    )
    .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
    .where(Document.id == document_id)
)

row = (await session.execute(statement)).one_or_none()
```

### What's happening here?

- `select(...)` chooses the columns we need, not the entire document body.
- `.outerjoin(...)` combines the document with its index, **even if the index doesn't exist yet**.
- `.where(Document.id == document_id)` restricts the query to one document.
- `await session.execute(statement)` sends the query to PostgreSQL.
- `.one_or_none()` gives one row or `None`. Since `Document.id` is a primary key, there can be at most one matching document.

Roughly equivalent SQL:

```sql
SELECT
    d.is_available,
    d.updated_at,
    s.indexed_at,
    s.indexed_hash
FROM document AS d
LEFT JOIN search_index AS s
    ON s.document_id = d.id
WHERE d.id = 42;
```

The return logic:

```python
if row is None or not row.is_available or row.indexed_at is None:
    return False

return (
    row.indexed_at >= row.updated_at
    and row.indexed_hash is not None
    and row.indexed_hash.startswith(config.index_hash_prefix)
)
```

Imagine document 42 was updated on **Oct 23** and indexed on **Oct 24** with the correct version. It returns `True`.

But if the crawler changes the document on **Oct 26**, then `updated_at > indexed_at`, so it returns `False`.

`False` means **not currently indexed according to our freshness rules**. It can mean a missing row, unavailable page, stale content, or old index version.

---

## Function 04: `select_index_candidates()`

This is the **main function the indexer worker will call**.

```python
statement = (
    select(Document.id, Document.updated_at)
    .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
    .where(
        Document.id > after_document_id,
        Document.is_available.is_(True),
        _outdated_index_condition(config),
    )
    .order_by(Document.id.asc())
    .limit(config.batch_size)
)
```

Let's break it down:

1. **Select only `id` and `updated_at`:** We don't transfer a huge document body just to decide whether it needs indexing.
2. **Outer join:** Include never-indexed documents. A normal inner join would silently miss them.
3. **`id > after_document_id`:** Continue after the previous batch instead of repeating the beginning.
4. **`is_available = True`:** Don't index pages that the crawler has marked unavailable.
5. **Outdated condition:** Select only missing, changed, or old-version index rows.
6. **Order by ID:** Make scanning deterministic.
7. **Limit:** Respect `config.batch_size`, which defaults to `100`.

Rough SQL:

```sql
SELECT d.id, d.updated_at
FROM document AS d
LEFT JOIN search_index AS s
    ON s.document_id = d.id
WHERE d.id > :after_document_id
  AND d.is_available = TRUE
  AND (
      s.document_id IS NULL
      OR s.indexed_at < d.updated_at
      OR s.indexed_hash NOT LIKE :current_version_prefix
  )
ORDER BY d.id ASC
LIMIT :batch_size;
```

In that conceptual SQL, the version parameter is a prefix pattern such as `v1:%`. SQLAlchemy constructs/binds the actual expression.

### What does this function return?

```python
[
    IndexCandidate(document_id=12, source_updated_at=<datetime>),
    IndexCandidate(document_id=19, source_updated_at=<datetime>),
    IndexCandidate(document_id=42, source_updated_at=<datetime>),
]
```

An `IndexCandidate` is a **lightweight instruction**: *"Document 42 looked like it needed indexing, and here is the source update timestamp I observed."*

It is **not** the final document snapshot. The worker/builder must reload the document before building and validate the revision when writing.

### Why batch selection?

Suppose we have 15,600 eligible documents and a batch size of 100.

```text
Batch 1:  100 candidates → index → continue
Batch 2:  100 candidates → index → continue
...
Batch 156: remaining candidates → index
```

Real batches may be smaller because some documents were already up to date.

We use **keyset pagination**, not `OFFSET`. For example:

```python
candidates = await select_index_candidates(
    session,
    config=config,
    after_document_id=0,
)

# After the selected candidates have been handed off:
next_cursor = candidates[-1].document_id if candidates else 0
```

The worker manages this cursor. When a scan reaches the end, start a fresh scan at `0` so newly changed older documents aren't permanently ignored. An empty batch doesn't mean the system will never have work again.

---

## Function 05: `select_removal_candidates()`

Here's a different scenario.

Imagine Python documentation page `document.id = 88` used to exist. The crawler later discovers it is gone (for example, an HTTP 404) and marks:

```text
Document.id            = 88
Document.is_available  = False
SearchIndex.document_id = 88  (still exists)
```

If we leave the search index untouched, Developer's Eye may keep showing a dead page in search results.

So we select IDs of **unavailable documents that still have a search index**:

```python
statement = (
    select(Document.id)
    .join(SearchIndex, SearchIndex.document_id == Document.id)
    .where(
        Document.id > after_document_id,
        Document.is_available.is_(False),
    )
    .order_by(Document.id.asc())
    .limit(config.batch_size)
)

return list((await session.scalars(statement)).all())
```

Notice two differences from the main selector:

- Here we use an **inner join** because we only want unavailable documents **that still have an index row**.
- We use `session.scalars(...)` because we only need the document IDs, not full rows.

Example result:

```python
[88, 105, 140]
```

The **writer**, not this selector, must later delete these indexes safely. If a document is physically deleted, the existing `ON DELETE CASCADE` foreign key can remove its index row automatically.

---

## Full scenario: one document's journey

Let's take `document.id = 42`.

| Event | Document `updated_at` | Index `indexed_at` | Version | Selector |
| --- | --- | --- | --- | --- |
| New document saved | Oct 20 | No index | None | Select |
| Index successfully written | Oct 20 | Oct 20 | `v1:` | Skip |
| Crawler revisits unchanged page | Oct 20 | Oct 20 | `v1:` | Skip |
| Page content changes | Oct 24 | Oct 20 | `v1:` | Select |
| Fresh index written | Oct 24 | Oct 25 | `v1:` | Skip |
| We deploy indexer version 2 | Oct 24 | Oct 25 | `v1:` | Select |
| Version 2 index written | Oct 24 | Oct 26 | `v2:` | Skip |
| Page becomes unavailable | Oct 24 | Oct 26 | `v2:` | Removal candidate |

The main goal is **incremental indexing**: process new or changed documents instead of rebuilding the entire collection repeatedly.

---

## Important production limitations

This selector is intentionally **read-only**. It is a necessary part of a production indexer, but it does **not** make the whole indexing pipeline concurrency-safe by itself.

### 1. Two workers can select the same document

```text
Worker A: selects document 42
Worker B: selects document 42
Both: start processing it
```

No row is claimed or leased here. Before running a distributed indexer, we'll need a worker-claim strategy (such as persistent leases and retry state) to avoid duplicated work and support recovery.

### 2. The source can change while we're building

```text
10:00  Worker reads document version A
10:01  Crawler updates document to version B
10:02  Worker finishes index for version A
```

If the worker writes a new `indexed_at` at 10:02 without checking the source revision, our timestamp-based selector might incorrectly consider this old index current.

**Fix in the future writer:** recheck the source revision under appropriate transaction locking or optimistic concurrency control, and commit only if the indexed snapshot is still valid. A source-revision fingerprint can strengthen this guarantee.

### 3. Metadata changes must update `updated_at`

If `title`, `tags`, `body`, or another search-relevant field changes but `updated_at` does not, this selector may skip necessary reindexing.

Our crawler/persistence layer must maintain that timestamp consistently. `server_default=func.now()` sets the initial timestamp on insert; it does **not** automatically update it on every subsequent SQL `UPDATE`.

### 4. Permanently failing documents need retry policy

A malformed document may repeatedly appear as a candidate. The worker will eventually need attempt counts, backoff, and visibility into indexing failures. Those don't belong in this selector alone.

### 5. The selector doesn't compare the two hashes directly

`Document.content_hash` and `SearchIndex.indexed_hash` are computed from different data. The actual content/version hashing belongs to the builder and writer. This selector currently relies on timestamps and the index-version prefix.

---

## What this file does *not* do

- It does **not** fetch websites. That's the crawler.
- It does **not** analyze text or generate a `TSVECTOR`. That's the analyzer/builder and PostgreSQL.
- It does **not** calculate a new `indexed_hash`. That's part of index construction.
- It does **not** save or delete indexes. That's the writer/repository layer.
- It does **not** assign jobs exclusively to workers. That requires claiming/lease logic.

**Selector = which documents need work.**  
**Builder = what searchable representation should be built.**  
**Writer = persist it safely.**  
**Worker = coordinate the pipeline.**

---

## My understanding / takeaway

The crawler stores the actual document. The indexer doesn't need to reprocess everything every time. So before indexing we run a selector that joins `document` and `search_index`, compares the timestamps and index version, and picks a small batch of documents that are missing an index or have become stale.

The selector returns `IndexCandidate` objects, not completed indexes. It also finds unavailable documents whose old index rows should be removed.

**Next stage:** `builder.py` and the source-revision checks in the eventual writer.
