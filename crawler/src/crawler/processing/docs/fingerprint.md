# Fingerprint Model

> **Developer's Eye — Content Processing Pipeline**  
> **File:** `crawler/src/crawler/processing/fingerprint.py`  
> **Input:** `NormalizedDocument` → **Output:** SHA-256 hash (`str`)

---

# Step by step

So we already made `normalize.py` to clean the document and `classify.py` to identify what kind of document it is.

Now what if our crawler fetches the same webpage tomorrow? How will we know if the actual content changed or not?

We could compare the whole old body with the new body every time. But instead we can generate a **fingerprint** of the document and compare that fingerprint with the previously stored one.

We use **SHA-256** for this. Same selected content → same hash. Changed selected content → almost certainly a different hash.

```text
HTML Parser -> ParsedDocument
                      |
                 normalize.py
                      |
               NormalizedDocument
                      |
                 fingerprint.py
                      |
                SHA-256 hash
                      |
                 processor.py
                      |
              Database Writer
                      |
           Compare with stored hash
```

**Important:** `fingerprint.py` only generates the hash. It doesn't check PostgreSQL or decide if a document is a duplicate. That comes later in our Database Writer.

---

# 1. Why we needed this?

Suppose Developer's Eye fetched:

```text
URL: https://docs.example.com/python
Title: Python Tutorial
Body: Python is a programming language.
```

We generate a SHA-256 hash of its selected content.

Tomorrow the scheduler recrawls the same URL.

**Case 1: Nothing changed.**

```text
First crawl  -> hash ABC...
Second crawl -> hash ABC...
```

Both hashes match. The database writer can update `last_seen_at` and avoid unnecessary reindexing, assuming other index-relevant data hasn't changed.

**Case 2: Website updated its content.**

```text
Old body: Python is a programming language.
New body: Python is a powerful programming language.

Old hash != New hash
```

Now the database writer knows that the selected content has changed and can update the document and search index.

The examples above use shortened placeholder hashes, not actual SHA-256 outputs.

---

# 2. Imports

```python
import hashlib
import json

from crawler.processing.schemas import NormalizedDocument
```

| Import | Why we need it |
|---|---|
| `hashlib` | Python's built-in hashing library. We use `sha256()`. |
| `json` | Converts selected document fields into a consistent serialized format. |
| `NormalizedDocument` | The schema our normalizer returns. |

SHA-256 accepts **bytes**, not a regular Python string. That's why we serialize the fields and then encode the result as UTF-8.

---

# 3. Fingerprint prefix

```python
_FINGERPRINT_PREFIX = b"developers-eye:content:v1\x00"
```

- `b` means this value is **bytes**.
- `developers-eye:content` tells us what this hash convention is for.
- `v1` means version 1 of our fingerprint format.
- `\x00` is a null byte separating the prefix from the serialized content.

Why the version?

Suppose later we change our hashing rules and decide to include additional document fields. Then we could use `v2` so hashes created under the new convention are distinct from the old ones.

But remember: **changing the version changes every generated hash**. We would need to plan how stored hashes are migrated or recomputed.

---

# 4. `_document_payload()` — prepare the data

```python
def _document_payload(document: NormalizedDocument) -> bytes:
```

This helper doesn't create the hash yet. It selects document fields and converts them into stable bytes.

## Step A: Validate input

```python
if not isinstance(document, NormalizedDocument):
    raise TypeError("document must be a NormalizedDocument")
```

We only accept our normalized document schema, not a random string or raw HTML.

Then:

```python
for name in ("title", "description"):
    value = getattr(document, name)
    if value is not None and not isinstance(value, str):
        raise TypeError(...)
```

`getattr(document, "title")` is the same as `document.title`. The loop checks both title and description without repeating the same code. They can be strings or `None`.

We also check that `body` is a string and `headings` / `code_blocks` are tuples containing only strings.

## Step B: Choose what we want to hash

```python
payload = {
    "title": document.title or "",
    "description": document.description or "",
    "body": document.body,
    "headings": document.headings,
    "code_blocks": document.code_blocks,
}
```

We only include the **selected searchable content**.

| Included | Not included |
|---|---|
| Title | URL and canonical URL |
| Description | Author |
| Body | Published date |
| Headings | Crawl timestamp |
| Code blocks | Other metadata, classification and tags |

Why not URL?

Suppose two URLs have exactly the same selected content:

```text
https://example.com/python
https://mirror.example.com/python
```

We want them to have the same **content fingerprint**. If we included URLs, the hashes would be different even though the content is identical.

Why not crawl timestamp? Because the crawler visiting a page again doesn't mean its content changed.

**One thing:** This hash won't detect changes to excluded fields like author or published date. The database writer should update those separately when needed.

---

# 5. Convert payload into bytes

```python
return json.dumps(
    payload,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

Here we use `json.dumps()` to convert our Python dictionary into JSON text.

- `ensure_ascii=False`: Keep Unicode characters like বাংলা in the text instead of escaping them.
- `sort_keys=True`: Always serialize dictionary keys in the same order.
- `separators=(",", ":")`: Don't add extra formatting spaces between JSON fields.
- `.encode("utf-8")`: Convert the JSON text to bytes for SHA-256.

Why do this instead of joining strings randomly?

Because separate fields should have clear boundaries. JSON gives us a consistent representation of title, description, body, headings, and code blocks.

---

# 6. `fingerprint_document()` — generate the hash

```python
def fingerprint_document(document: NormalizedDocument) -> str:
    serialized = _document_payload(document)
    return hashlib.sha256(
        _FINGERPRINT_PREFIX + serialized
    ).hexdigest()
```

Only two steps here.

**Step 1:** `_document_payload(document)` prepares the selected content as bytes.

**Step 2:** `hashlib.sha256()` hashes the prefix + serialized bytes. `.hexdigest()` turns the result into a **64-character hexadecimal string**.

Why 64 characters?

SHA-256 generates 256 bits. Each hexadecimal character represents 4 bits.

```text
256 / 4 = 64 hexadecimal characters
```

And SHA-256 is deterministic: the same input bytes always produce the same hash.

---

# 7. Why SHA-256 and not Argon2?

Both are hashing technologies but they have different jobs.

| SHA-256 | Argon2 |
|---|---|
| Fast | Intentionally expensive |
| Low memory overhead | Configurable memory cost |
| Good for document fingerprinting | Designed for password hashing |
| Same bytes → same hash | Password-hashing APIs normally use random salts |

Argon2 makes password guessing expensive on purpose. We don't need that for comparing crawler documents.

Our crawler may process thousands of pages, so **SHA-256 is a better fit**. It's deterministic, fast, and already available in Python's standard library.

---

# 8. Test it

```python
from dataclasses import replace

from crawler.processing.fingerprint import fingerprint_document
from crawler.processing.schemas import NormalizedDocument

first = NormalizedDocument(
    url="https://example.com/python",
    canonical_url="https://example.com/python",
    title="Python Tutorial",
    body="Python is a programming language.",
)

# Same content, different URL.
second = replace(
    first,
    url="https://mirror.example.com/python",
    canonical_url="https://mirror.example.com/python",
)

# Same URL, different content.
third = replace(
    first,
    body="Python is a powerful programming language.",
)

hash1 = fingerprint_document(first)
hash2 = fingerprint_document(second)
hash3 = fingerprint_document(third)

print(hash1 == hash2)  # True
print(hash1 == hash3)  # False
print(len(hash1))     # 64
```

So same selected content under different URLs produces the same fingerprint. Changing the body produces a different fingerprint.

This is **exact-content fingerprinting**. It isn't a near-duplicate detector. Even a small change in selected text can change the hash.

---

# 9. Final flow

```text
NormalizedDocument
       |
       v
_document_payload()
       |
       +-- Validate fields
       +-- Select title, description, body, headings, code
       +-- json.dumps() with stable options
       +-- UTF-8 bytes
       |
       v
fingerprint_document()
       |
       +-- Add v1 prefix
       +-- SHA-256
       +-- hexdigest()
       |
       v
64-character content hash
       |
       v
ProcessedDocument.content_hash
       |
       v
Database Writer -> compare with stored content_hash
```

So that's our fingerprint module. Nothing too complicated.

**Normalizer cleans the content. Classifier identifies the content. Fingerprint generates a stable hash of the selected content.**

Later, `processor.py` will connect all three. The Database Writer will decide whether to insert, update, or skip reindexing a document.
