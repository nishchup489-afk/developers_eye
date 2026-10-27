# Developer's Eye — Indexer: Builder

**Stage 02: Turning a stored document into indexing input**  
**File:** `crawler/src/indexer/builder.py`

---

## What is the builder?

Our crawler already fetched thousands of developer pages and stored them in PostgreSQL's **`document`** table. In Stage 01, the **selector** found which documents need indexing.

But the selector gives us only a small reference:

```python
IndexCandidate(document_id=42, source_updated_at=...)
```

We cannot build a useful search index from an ID alone. We need the title, body, headings, code blocks, tags, and other searchable fields. We also need to make sure the crawler hasn't changed the document after selection.

**The builder's job is to reload one selected document, validate its data, and create a consistent `IndexDocument` snapshot.** It can also calculate the `indexed_hash` for those index inputs.

```text
Crawler ────────> PostgreSQL: document
                            |
Selector ──> IndexCandidate  |
                |           |
                v           v
               BUILDER (this file)
                  |          |
                  |          +--> Checks revision + availability
                  |          +--> Extracts metadata arrays
                  |          +--> Normalizes / validates
                  |          +--> Enforces size limits
                  v
              IndexDocument
                  |
                  +--> calculate_index_hash() --> "v1:<sha256>"
                  |
                  v
        Analyzer / Vector / Repository
                  |
                  v
          PostgreSQL: search_index
```

The builder **does not insert into `search_index`**, create PostgreSQL `TSVECTOR`s, classify documents, or reserve jobs for workers.

---

## A real scenario

Imagine we crawled this Python documentation page:

```text
Document table:
  id              = 42
  source_id       = 2
  canonical_url   = https://docs.python.org/3/tutorial/datastructures.html
  document_type   = documentation
  title           = Data Structures
  description     = Lists, tuples, and other built-in structures
  body            = Python lists support append(), pop(), and more.
  is_available    = True
  content_hash    = <64 hexadecimal characters>
  updated_at      = Oct 26, 10:00 UTC
  metadata        = {
      "headings": ["More on Lists", "Using Lists as Stacks"],
      "code_blocks": ["items = [1, 2]\nitems.append(3)"],
      "tags": ["python", "lists", "Python"]
  }
```

### Step 1: Selector chooses the document

```python
candidate = IndexCandidate(
    document_id=42,
    source_updated_at=document_updated_at,
)
```

The `source_updated_at` value is the timestamp captured **when the selector queried PostgreSQL**.

### Step 2: Builder loads the current row

```python
statement = select(Document).where(Document.id == candidate.document_id)
document = await session.scalar(statement)
```

Unlike the selector's lightweight query, this loads the complete `Document` ORM object.

### Step 3: Builder checks whether the source is still valid

- Does document 42 still exist?
- Is it still available?
- Is its `updated_at` *exactly the same* as the timestamp recorded by the selector?

If the crawler changed the document between selection and loading, the builder rejects this candidate with `StaleIndexSourceError`. The worker should select the current revision again.

### Step 4: Builder prepares the indexing data

The metadata arrays become immutable tuples. Empty entries are skipped. Duplicate tags are removed case-insensitively, keeping the first spelling.

```python
IndexDocument(
    document_id=42,
    source_id=2,
    canonical_url="https://docs.python.org/3/tutorial/datastructures.html",
    document_type="documentation",
    title="Data Structures",
    description="Lists, tuples, and other built-in structures",
    body="Python lists support append(), pop(), and more.",
    headings=("More on Lists", "Using Lists as Stacks"),
    code_blocks=("items = [1, 2]\nitems.append(3)",),
    tags=("python", "lists"),
    content_hash="<64-character lowercase SHA-256>",
    source_updated_at=document_updated_at,
)
```

The example uses placeholder values for the hash and timestamp; the real `IndexDocument` validates those values.

### Step 5: Builder calculates an index hash

```text
index_version = 1
indexed_hash  = v1:<64-character SHA-256 digest>
```

That hash identifies the **specific index inputs and indexer configuration**, not merely the crawler's raw content. The repository will later store it as `search_index.indexed_hash` after successfully creating the index.

---

## Function 01: `_normalize_prose()`

```python
def _normalize_prose(value: str | None, *, name: str, document_id: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IndexDocumentError(...)
    return unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    ).strip()
```

We need reasonably consistent text before indexing and hashing.

**What it actually does:**

1. Converts missing optional text (`None`) into an empty string.
2. Rejects non-string input.
3. Normalizes Windows-style (`\r\n`) and older (`\r`) line endings to `\n`.
4. Uses Unicode **NFC** to make canonically equivalent characters consistent.
5. Removes leading and trailing whitespace with `.strip()`.

**It does *not* collapse every internal space, lowercase the body, tokenize words, or stem them.** That later search analysis belongs to `analyzer.py` / PostgreSQL.

Example:

```python
_normalize_prose("  Python\r\nLists  ", name="title", document_id=42)
# "Python\nLists"
```

Why NFC? A visually identical word can be represented with different Unicode code-point sequences. Normalizing reduces accidental hash differences.

---

## Function 02: `_metadata_items()`

Our crawler writer stores structured content inside PostgreSQL `Document.metadata_` (the database column is called `metadata`, with JSONB type).

```json
{
  "headings": ["Introduction", "Quickstart"],
  "code_blocks": ["def hello():\n    print('hi')"],
  "tags": ["Python", "python", "FastAPI"]
}
```

The builder expects each of these keys to hold a **list (or tuple) of strings**.

```python
_STRUCTURED_FIELDS = ("headings", "code_blocks", "tags")

extracted = {
    name: _metadata_items(metadata, name, document_id=document_id)
    for name in _STRUCTURED_FIELDS
}
```

### Why separate code blocks from prose?

Code whitespace can be meaningful:

```python
def greet():
    print("hello")
```

If you collapse indentation, the stored code representation changes. Therefore code blocks retain leading indentation and internal spacing, while their line endings are standardized.

### Why special handling for tags?

```python
["Python", "python", "FastAPI"]
```

Becomes:

```python
("Python", "FastAPI")
```

It uses `.casefold()` to identify duplicates but preserves the first tag's original capitalization. It also removes blank entries from all three metadata arrays.

### What if metadata is malformed?

```python
{"tags": "python"}       # Invalid: string instead of array
{"headings": [42]}        # Invalid: number instead of string
```

The builder raises `IndexDocumentError` rather than silently manufacturing content. Missing keys are allowed and become empty tuples.

---

## Function 03: `prepare_index_document()`

This is the **pure preparation function**. It accepts an already loaded `Document` ORM object and returns a validated `IndexDocument` dataclass. It does **not** query PostgreSQL.

```python
def prepare_index_document(
    document: Document,
    *,
    config: IndexerConfig,
) -> IndexDocument:
    ...
```

Its steps are:

1. **Validate arguments**: `Document` and `IndexerConfig` must be correct types.
2. **Check identity**: `document.id` must be a positive integer.
3. **Check availability**: unavailable documents cannot be indexed.
4. **Read `metadata_`**: it must be a JSON object represented by `dict`.
5. **Extract arrays**: headings, code blocks, and tags.
6. **Build `IndexDocument`**: copy and normalize the searchable fields.
7. **Validate through the schema**: URL, nonempty title, body/code presence, hash format, timezone-aware timestamp, etc.
8. **Enforce configured size limit**: raise if the indexable text exceeds the maximum.

### Character limit

```python
if result.total_text_chars > config.max_document_chars:
    raise IndexDocumentTooLargeError(...)
```

With the default configuration:

```text
max_document_chars = 1,000,000
```

`total_text_chars` sums the lengths of the URL, document type, title, description, body, headings, code blocks, and tags. It's a **character budget**, not the number of UTF-8 bytes or PostgreSQL tokens.

**Why reject rather than silently truncate?** Truncation can make content misleading and make hash/index behavior harder to reason about. A rejection can be recorded by the indexing worker and investigated explicitly.

---

## Function 04: `build_index_document()`

This is the **async database-entry function** the indexer worker calls for a selected document.

```python
async def build_index_document(
    session: AsyncSession,
    candidate: IndexCandidate,
    *,
    config: IndexerConfig,
) -> IndexDocument:
    ...
```

### The actual SQLAlchemy query

```python
statement = select(Document).where(
    Document.id == candidate.document_id
)
document = await session.scalar(statement)
```

Conceptually equivalent to:

```sql
SELECT *
FROM document
WHERE id = 42;
```

- `select(Document)` requests the ORM document row.
- `.where(...)` filters by the selected ID.
- `session.scalar(statement)` executes the SQL asynchronously and returns the ORM object, or `None`.
- The builder does not commit or update any database row.

### The stale-revision check

```python
if document.updated_at != candidate.source_updated_at:
    raise StaleIndexSourceError(...)
```

Scenario:

```text
10:00:00  Selector sees Document 42, updated_at = 10:00:00
10:00:02  Crawler updates Document 42, updated_at = 10:00:02
10:00:03  Builder loads Document 42
10:00:03  Builder detects mismatch -> STALE -> do not build old candidate
```

This prevents proceeding with a candidate **already known to be outdated at load time**.

But this check is **not enough for concurrency safety**. The crawler may update the document *after* this check. The eventual writer must recheck the source revision before committing the vector.

### What does it return?

On success it calls:

```python
return prepare_index_document(document, config=config)
```

So the worker receives an immutable, validated `IndexDocument`, not a live ORM object tied to a session.

---

## Function 05: `calculate_index_hash()`

The crawler already has `Document.content_hash`. Why another hash?

- `content_hash` tracks the crawler's normalized content fingerprint.
- `indexed_hash` tracks the **exact inputs used for search indexing** and the indexer configuration/version.

The builder assembles a payload including:

```python
payload = {
    "format": 1,
    "index_version": config.index_version,
    "text_search_config": config.text_search_config,
    "code_search_config": config.code_search_config,
    "document_id": document.document_id,
    "source_id": document.source_id,
    "canonical_url": document.canonical_url,
    "document_type": document.document_type,
    "title": document.title,
    "description": document.description,
    "body": document.body,
    "headings": document.headings,
    "code_blocks": document.code_blocks,
    "tags": document.tags,
    "content_hash": document.content_hash,
}
```

Then serializes it deterministically:

```python
serialized = json.dumps(
    payload,
    ensure_ascii=True,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

Why JSON rather than simply joining all the strings together? Because JSON preserves **field boundaries**, array order, and data types. Sorting keys makes the encoding independent of dictionary insertion order.

The digest:

```python
_HASH_DOMAIN = b"developers-eye:index-input:v1\x00"
digest = hashlib.sha256(_HASH_DOMAIN + serialized).hexdigest()
return f"{config.index_hash_prefix}{digest}"
```

`_HASH_DOMAIN` distinguishes this hashing convention from other SHA-256 hashes in the project. The final prefix comes from `IndexerConfig`, for example `v1:`.

### Hash examples

| Scenario | `content_hash` | `indexed_hash` |
| --- | --- | --- |
| Same content and same indexing settings | Same | Same |
| Tags change, raw page text unchanged | May stay same | Changes |
| Indexer version increases from 1 to 2 | Same | Changes (and prefix becomes `v2:`) |
| Page observed again, nothing changed | Same | Same |
| Source timestamp changes without changing hashed fields | Same | Same |

**Do not compare `content_hash` directly with `indexed_hash`.** They are different hashing contracts.

Also, a hash only tracks what the payload includes. If the analyzer or vector weighting algorithm changes, **increment `index_version`** to force reindexing; otherwise the hash may still match even though the indexing rules changed.

---

## Exceptions: what can go wrong?

| Exception | Example | What the worker should do |
| --- | --- | --- |
| `TypeError` | Wrong function argument type | Treat as a programming/caller error |
| `IndexDocumentError` | Invalid URL, malformed tags, blank title, invalid hash | Record invalid document and avoid an uncontrolled retry loop |
| `IndexDocumentTooLargeError` | Indexable content over character limit | Record/review; do not silently truncate |
| `StaleIndexSourceError` | Document changed, became unavailable, or was deleted | Reselect or route to removal handling |
| SQLAlchemy/database exception | DB connection or query fails | Let the worker retry according to database policy |

The builder **does not** swallow errors with `except Exception`. It lets the orchestration layer decide whether to retry, skip, or alert.

---

## How the files work together

```python
# Pseudocode in the worker/service layer.
candidates = await select_index_candidates(session, config=config)

for candidate in candidates:
    index_doc = await build_index_document(
        session, candidate, config=config
    )
    indexed_hash = calculate_index_hash(index_doc, config=config)

    # Next stages, implemented separately:
    # analyzer.py -> prepare field-specific searchable text
    # vector.py   -> define weighted PostgreSQL TSVECTOR expressions
    # repository.py -> write vector + indexed_hash safely
```

The comments about the later files are architecture notes, not implementations that already exist.

**Keep these responsibilities separate:**

| File | Responsibility |
| --- | --- |
| `selector.py` | Find document IDs needing indexing/removal |
| `builder.py` | Reload, validate, extract and hash an indexing snapshot |
| `analyzer.py` | Prepare searchable text and field-level analysis |
| `vector.py` | Construct weighted full-text search vector expressions |
| `repository.py` | Persist the vector and hash; validate freshness at write time |
| `worker/runner.py` | Run batches, capture outcomes, retry failures |

---

## Production considerations

**1. No locks here.** Two workers may build the same document. The worker/repository layer needs a safe claiming or idempotent write mechanism.

**2. The writer must revalidate.** Checking `updated_at` during the builder read is not a guarantee that the source remains unchanged at commit time. Check inside the writer's transaction and use an appropriate row-locking or compare-and-swap strategy.

**3. Metadata changes must update `Document.updated_at`.** The existing crawler upsert compares metadata and refreshes `updated_at` when it changes. Any future editing path must preserve that rule.

**4. Correct hash, correct vector.** `calculate_index_hash()` uses the builder's inputs plus configuration. The repository must store the hash corresponding to the **same** vector it commits. When analyzer/vector behavior changes, bump `index_version`.

**5. No full-text tokenization here.** Builder Unicode normalization is not PostgreSQL linguistic processing or ranking. Those come next.

---

## Quick mental model

**Selector:** *Which document needs indexing?*  
**Builder:** *What exactly should we index, and is this candidate still valid?*  
**Analyzer / Vector:** *How should that data become searchable?*  
**Repository:** *Can we safely persist the result?*

**One-line explanation:** `builder.py` turns a selected PostgreSQL document into a validated, immutable indexing snapshot and produces a reproducible, versioned index-input hash, without writing anything to the database.
