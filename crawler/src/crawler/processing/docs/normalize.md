# Normalizer Model

> **Developer's Eye — Content Processing Pipeline**  
> **File:** `crawler/src/crawler/processing/normalize.py`  
> **Input:** `ParsedDocument` → **Output:** `NormalizedDocument`

---

# Step by step

So we already built our HTML parser. It extracts the title, description, body, headings, code blocks, metadata, and canonical URL hint from a webpage.

But what if two websites have the same content with different spacing? What if the HTML uses Windows-style newlines? What if a page gives us a canonical URL different from the URL we fetched?

We don't want to send all of that directly to our classifier or fingerprint module.

That's why we need **normalization**.

The normalizer takes the already-parsed document, cleans and standardizes its fields, and returns a new `NormalizedDocument`. It **doesn't change the original `ParsedDocument`**.

```text
Policy Coordinator -> Fetcher -> Worker -> HTML Parser
                                             |
                                      ParsedDocument
                                             |
                                        normalize.py
                                             |
                                      NormalizedDocument
                                             |
                                Classifier + Fingerprint
                                             |
                                         Processor
                                             |
                                       Database Writer
```

**One important thing:** normalizing a URL is not the same as checking whether it is safe to crawl. Our Host Policy, DNS Policy, Robots Policy, and Coordinator already handle crawling permissions. This file never makes a network request.

---

## 1. Why we needed normalization

Suppose the crawler fetched this documentation page and our parser extracted:

```python
ParsedDocument(
    url="https://docs.example.com/python#introduction",
    title="  Python     Documentation  ",
    description="Learn   Python\tprogramming.",
    body="Python   is a language.\n\n\n\nIt is easy to learn.",
    headings=("  Introduction  ",),
    canonical_url_hint="/python",
    metadata={"keywords": ["python", "programming"]},
)
```

There are a few problems:

- The title has unnecessary spaces.
- The description has multiple spaces and a tab.
- The body has too many blank lines.
- The fetched URL has a fragment, `#introduction`.
- The canonical URL is relative, `/python`.

After normalization we want information like:

```python
NormalizedDocument(
    url="https://docs.example.com/python",
    canonical_url="https://docs.example.com/python",
    title="Python Documentation",
    description="Learn Python programming.",
    body="Python is a language.\n\nIt is easy to learn.",
    headings=("Introduction",),
    code_blocks=(),
    metadata={"keywords": ["python", "programming"]},
)
```

The other optional fields, such as `author` and `published_at`, remain in the result too.

This matters for classification, indexing, search-result snippets, and generating consistent content hashes later.

---

## 2. Imports

```python
from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from crawler.frontier.urls import normalize_url
from crawler.parser.schemas import ParsedDocument
from crawler.processing.schemas import NormalizedDocument
```

| Import | Why we need it |
|---|---|
| `annotations` | Allows type annotations to be evaluated later. |
| `deepcopy` | Copies metadata so modifying the output won't modify the parser's original metadata. |
| `re` | Finds extra spaces, newlines, and control characters using regex. |
| `unicodedata` | Normalizes different Unicode representations of the same text. |
| `urlsplit` | Separates a URL into scheme, host, path, etc. |
| `urljoin` | Resolves a relative canonical URL against the fetched URL. |
| `normalize_url` | Reuses our existing Frontier URL-normalization rules. |
| `ParsedDocument` | The schema returned by the parser. |
| `NormalizedDocument` | The schema returned by this normalizer. |

Notice that we **reuse the Frontier's `normalize_url()`** instead of writing another URL normalizer. That way, the parser-processing side and the Frontier can apply consistent URL-format rules.

---

# Patterns

## 3. Whitespace and control-character patterns

```python
_WHITESPACE = re.compile(r"\s+")
_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
```

Our patterns are compiled once when Python imports the file. We'll reuse them on every document.

### `_WHITESPACE`

```python
r"\s+"
```

- `\s` means whitespace, including spaces, tabs, and newlines.
- `+` means one or more occurrences.

Example:

```python
_WHITESPACE.sub(" ", "Learn   Python\tprogramming")
# "Learn Python programming"
```

We use this for **short text fields** such as titles, descriptions, authors, and headings. A title generally doesn't need multiple spaces or paragraph breaks.

### `_HORIZONTAL_WHITESPACE`

```python
r"[^\S\n]+"
```

Looks confusing, but here is the idea:

- `\S` means a non-whitespace character.
- `[^\S\n]` means a character that is whitespace **but not a newline**.
- `+` means one or more.

So this matches spaces and tabs while preserving `\n` as a line separator.

Example:

```text
Before:
Python    is a language.
It    supports asyncio.

After:
Python is a language.
It supports asyncio.
```

Why not use ordinary `\s+` here? Because that would also collapse newlines and could turn multiple paragraphs into one line.

### `_EXCESS_NEWLINES`

```python
r"\n{3,}"
```

Matches **three or more consecutive newlines**.

```python
_EXCESS_NEWLINES.sub("\n\n", "First paragraph\n\n\n\nSecond paragraph")
# "First paragraph\n\nSecond paragraph"
```

We keep up to two newlines so there can still be a blank line between paragraphs.

### `_CONTROL_CHARACTERS`

```python
r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
```

This matches a specified set of non-text control characters, such as the null character `\x00`.

It intentionally **doesn't include `\n` (newline) or `\t` (tab)** because those can be meaningful in text and code.

It doesn't remove every possible Unicode control or formatting character, just the characters listed in the pattern.

---

# Utility functions

## 4. `_normalize_unicode(value)` — standardize Unicode and newlines

```python
def _normalize_unicode(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARACTERS.sub(" ", value)
```

This utility does three things.

**Step 1: Unicode NFC normalization.**

Sometimes the same visible character can be represented by different Unicode sequences.

For example, `é` can be stored as one character or as `e` followed by a combining accent. **NFC** normalizes them into a consistent representation when possible.

Why? Because two strings that look identical can otherwise have different underlying bytes. Consistent text helps with later comparison and fingerprinting.

**Step 2: Normalize newlines.**

```python
value.replace("\r\n", "\n").replace("\r", "\n")
```

Different systems can produce different line endings:

| Newline | Common name |
|---|---|
| `\n` | LF |
| `\r\n` | CRLF |
| `\r` | CR |

We convert all of them to `\n`.

**Step 3: Replace specified control characters with spaces.**

```python
_CONTROL_CHARACTERS.sub(" ", value)
```

It replaces each matching control character with one space instead of leaving unwanted characters in our text.

This is only a **text normalization utility**. It doesn't parse HTML or clean URLs.

---

## 5. `_clean_short_text(value)` — title, description, author

```python
def _clean_short_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("text fields must contain str or None")

    cleaned = _WHITESPACE.sub(" ", _normalize_unicode(value)).strip()
    return cleaned or None
```

Suppose metadata extraction gives us:

```python
title = "  Getting   Started\nwith    FastAPI  "
```

First `_normalize_unicode()` standardizes the text. Then `_WHITESPACE.sub(" ", ...)` collapses spaces and newlines. Finally `.strip()` removes whitespace from both ends.

Output:

```python
"Getting Started with FastAPI"
```

### Why `return cleaned or None`?

Suppose the original title contains only spaces:

```python
title = "    "
```

After cleaning:

```python
cleaned = ""
```

Instead of storing an empty title, we return `None`.

If the input is already `None`, it stays `None`. If the input is something unexpected, such as an integer, the function raises `TypeError`.

We reuse this function for **title, description, author, and each heading**.

---

## 6. `_clean_code(value)` — preserve code indentation

```python
def _clean_code(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("code blocks must contain strings")
    return _normalize_unicode(value).strip("\n")
```

Why do we need a separate code cleaner?

Imagine the parser extracts:

```python
if True:
    print("Hello")
```

Those four spaces before `print()` are meaningful. If we ran the ordinary short-text cleaner, we'd get something like:

```text
if True: print("Hello")
```

We'd lose the code formatting.

So `_clean_code()` **does not collapse spaces or tabs**. It only runs the common Unicode/newline normalization and removes leading and trailing **newline characters**.

Important difference:

```python
.strip("\n")
```

isn't the same as:

```python
.strip()
```

The first removes `\n` from the beginning and end. The second also removes surrounding spaces and tabs, which we may need to preserve inside code.

---

## 7. `_clean_prose_fragment(value)` — clean paragraphs

```python
def _clean_prose_fragment(value: str) -> str:
    lines = (
        _HORIZONTAL_WHITESPACE.sub(" ", line).strip()
        for line in value.split("\n")
    )
    return _EXCESS_NEWLINES.sub("\n\n", "\n".join(lines))
```

This one works line by line.

Suppose our body has:

```text
Python     is a language.



It   supports   async programming.
```

**Step 1: `value.split("\n")`** separates the body into lines.

**Step 2: The generator expression** processes each line:

```python
_HORIZONTAL_WHITESPACE.sub(" ", line).strip()
```

It collapses extra spaces and tabs and removes whitespace around that individual line.

**Step 3: `"\n".join(lines)`** puts the lines back together.

**Step 4: `_EXCESS_NEWLINES.sub("\n\n", ...)`** reduces long runs of empty lines to a single blank line.

Result:

```text
Python is a language.

It supports async programming.
```

Why not apply this function directly to an entire body that contains code? Because it would remove code indentation. That's why the next function exists.

---

## 8. `_clean_body(value, code_blocks)` — protect code while cleaning body

```python
def _clean_body(value: str, code_blocks: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise TypeError("document.body must be a string")

    body = _normalize_unicode(value)
    chunks: list[str] = []
    cursor = 0

    for block in code_blocks:
        if not block:
            continue
        position = body.find(block, cursor)
        if position < 0:
            continue

        chunks.append(_clean_prose_fragment(body[cursor:position]))
        chunks.append(block)
        cursor = position + len(block)

    chunks.append(_clean_prose_fragment(body[cursor:]))
    cleaned = "".join(chunks).strip("\n")
    return cleaned if cleaned.strip() else ""
```

This is probably the most important text function in this file.

Our HTML extractor gives us both:

1. `body`: the readable page text, sometimes including code.
2. `code_blocks`: the code extracted from `<pre>` elements.

Suppose:

```python
body = '''Learn   Python.

if True:
    print("Hello")

Now   continue reading.'''

code_blocks = ('if True:\n    print("Hello")',)
```

We want to clean ordinary prose while keeping the four spaces before `print()`.

### Step A: Standardize the body

```python
body = _normalize_unicode(value)
```

### Step B: Keep an output list and cursor

```python
chunks = []
cursor = 0
```

`chunks` stores each cleaned piece. `cursor` records how much of the original body we have already processed.

### Step C: Find a known code block

```python
position = body.find(block, cursor)
```

`find()` returns the starting index of the matching code block, or `-1` if it wasn't found.

Why start searching at `cursor`? So after processing one block, we continue from where we left off.

### Step D: Clean the prose *before* the code

```python
chunks.append(_clean_prose_fragment(body[cursor:position]))
```

Then append the code **unchanged**:

```python
chunks.append(block)
```

And move the cursor to the end of that block:

```python
cursor = position + len(block)
```

If the body contains more known code blocks, the loop does the same thing for each one.

### Step E: Clean the remaining prose and join the pieces

```python
chunks.append(_clean_prose_fragment(body[cursor:]))
cleaned = "".join(chunks).strip("\n")
```

If the resulting text only contains whitespace, return `""`.

### An important limitation

This relies on **finding each code block's exact text inside the body**. If `extractor.py` formats the body differently from `code_blocks`, `body.find()` may fail. Then that code span won't be protected and the ordinary prose cleaner may collapse its indentation.

Also, the current function joins the pieces exactly as collected. It doesn't invent separators when a code block and adjacent prose lack them. We should add integration tests for these cases before the crawler handles real documentation pages.

---

# URL normalization

## 9. `_validate_source_url(value)` — validate the fetched URL

```python
def _validate_source_url(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("document.url must be a nonempty HTTP(S) URL")

    if any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
        for char in value
    ):
        raise ValueError("document.url contains invalid characters")

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValueError("document.url is malformed") from exc

    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.netloc
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.netloc.endswith(":")
        or port == 0
    ):
        raise ValueError("document.url must be an absolute HTTP(S) URL")

    return normalize_url(value)
```

This works on the URL we **already fetched**. It does not authorize another fetch.

### Step A: Check the input type

We expect a nonempty string, not `None` or a random object.

### Step B: Reject problematic characters

The loop checks for whitespace, specified ASCII control characters, and the backslash character.

For example, a URL containing a literal space gets rejected rather than silently reinterpreted.

### Step C: Split and validate the URL structure

```python
parts = urlsplit(value)
port = parts.port
```

Suppose:

```text
https://docs.python.org:443/3/tutorial/#intro
```

Its components include:

```text
scheme:   https
hostname: docs.python.org
port:     443
path:     /3/tutorial/
fragment: intro
```

Then we check:

- Scheme must be `http` or `https`.
- Hostname and network location must exist.
- Username/password inside the URL are rejected.
- Invalid empty/zero ports are rejected.

### Step D: Reuse Frontier `normalize_url()`

```python
return normalize_url(value)
```

For our Frontier normalizer, this is where URL formatting is standardized, including fragment removal and any default-port normalization that function implements.

```text
Input:  https://DOCS.PYTHON.ORG:443/3/tutorial/#intro
Output: https://docs.python.org/3/tutorial/
```

This is a formatting example assuming the Frontier's documented normalization behavior.

**Don't confuse this with Host/DNS Policy:** a URL can have a valid structure but still point to a forbidden or unsafe destination.

---

## 10. `_canonical_url(fetched_url, hint)` — choose the document identity

```python
def _canonical_url(fetched_url: str, hint: str | None) -> str:
    if not isinstance(hint, str) or not hint.strip():
        return fetched_url

    hint = hint.strip()
    if any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
        for char in hint
    ):
        return fetched_url

    try:
        reference = urlsplit(hint)
        if reference.scheme and (
            reference.scheme.lower() not in {"http", "https"}
            or not reference.netloc
        ):
            return fetched_url

        candidate = _validate_source_url(urljoin(fetched_url, hint))
        current = urlsplit(fetched_url)
        proposed = urlsplit(candidate)
    except (TypeError, ValueError):
        return fetched_url

    if proposed.hostname != current.hostname:
        return fetched_url
    if current.scheme.lower() == "https" and proposed.scheme.lower() != "https":
        return fetched_url

    return candidate
```

### What is a canonical URL?

Suppose the same article is accessible at:

```text
https://example.com/posts/python?utm_source=reddit
https://example.com/posts/python?utm_source=twitter
https://example.com/posts/python
```

The website may declare:

```html
<link rel="canonical" href="https://example.com/posts/python">
```

The canonical URL is the page owner's **hint** about the preferred identity of that content.

Why do we care? Because our database writer and indexer should avoid treating every tracking-parameter version as a completely different article when we can reliably identify them as the same document.

### Step A: Check whether a hint exists

```python
if not isinstance(hint, str) or not hint.strip():
    return fetched_url
```

No hint? Keep the fetched URL.

### Step B: Reject obviously malformed hints

No whitespace, listed control characters, or backslashes.

### Step C: Resolve relative URLs

```python
urljoin(fetched_url, hint)
```

Example:

```python
fetched_url = "https://docs.example.com/tutorial/intro"
hint = "/tutorial"

urljoin(fetched_url, hint)
# "https://docs.example.com/tutorial"
```

A relative canonical URL is valid HTML. We just need to resolve it against the fetched page URL.

### Step D: Validate and normalize the candidate

```python
candidate = _validate_source_url(...)
```

This applies the same structural checks as the fetched URL.

### Step E: Compare the hostnames

```python
if proposed.hostname != current.hostname:
    return fetched_url
```

Suppose we fetched:

```text
https://docs.example.com/python
```

But the page declares:

```text
https://unrelated.example.net/python
```

Our MVP rejects that canonical hint and keeps the fetched URL.

Why? Because an HTML page shouldn't get to arbitrarily change our stored document identity to another hostname.

**Technical detail:** the current check compares **hostnames**, not full origins. It doesn't separately require the same scheme or port, except for the HTTPS-downgrade rule below.

### Step F: Reject HTTPS → HTTP downgrade

```python
if current.scheme.lower() == "https" and proposed.scheme.lower() != "https":
    return fetched_url
```

Fetched:

```text
https://docs.example.com/python
```

Hint:

```text
http://docs.example.com/python
```

Rejected. We keep HTTPS.

### Results

| Fetched URL | Canonical hint | Chosen canonical URL |
|---|---|---|
| `https://example.com/a` | `/b` | `https://example.com/b` |
| `https://example.com/a` | `https://example.com/b` | `https://example.com/b` |
| `https://example.com/a` | `https://evil.example.net/b` | `https://example.com/a` |
| `https://example.com/a` | `http://example.com/b` | `https://example.com/a` |
| `https://example.com/a` | Missing hint | `https://example.com/a` |

**Important:** Choosing a canonical URL doesn't mean we're going to fetch it. It's a *storage identity hint*, not crawl permission.

---

# Main function: `normalize_document()`

## 11. Step 1 — Validate the schema

```python
def normalize_document(document: ParsedDocument) -> NormalizedDocument:
    if not isinstance(document, ParsedDocument):
        raise TypeError("document must be a ParsedDocument")
```

Our parser must supply a `ParsedDocument` object, not a random dict or HTML string.

## 12. Step 2 — Prepare both URLs

```python
fetched_url = _validate_source_url(document.url)
canonical_url = _canonical_url(fetched_url, document.canonical_url_hint)
```

Here we store **two pieces of information**:

- `url`: where our crawler actually fetched the page.
- `canonical_url`: which normalized URL we currently treat as the preferred document identity.

They can be identical, but they don't have to be.

## 13. Step 3 — Validate complex fields

```python
if not isinstance(document.headings, (tuple, list)):
    raise TypeError("document.headings must be a tuple or list")
if not isinstance(document.code_blocks, (tuple, list)):
    raise TypeError("document.code_blocks must be a tuple or list")
if not isinstance(document.metadata, dict):
    raise TypeError("document.metadata must be a dictionary")
```

Why validate these?

Because the next steps loop over headings and code blocks and copy metadata. We need those fields to have the structure our schema expects.

## 14. Step 4 — Clean code blocks and headings

```python
code_blocks = tuple(
    cleaned
    for code in document.code_blocks
    if (cleaned := _clean_code(code)).strip()
)

headings = tuple(
    cleaned
    for heading in document.headings
    if (cleaned := _clean_short_text(heading)) is not None
)
```

This uses the **walrus operator**: `:=`.

### What's `:=`?

Normally we'd write:

```python
cleaned = _clean_code(code)
if cleaned.strip():
    result.append(cleaned)
```

The walrus operator lets us **assign a value while evaluating an expression**.

In the comprehension:

```python
(cleaned := _clean_code(code))
```

means “clean this code block and save the result to `cleaned`.”

Then:

```python
if (...).strip()
```

keeps only nonempty code blocks.

Likewise, headings that become `None` after cleaning are discarded.

Example:

```python
headings = (
    "  Introduction  ",
    "     ",
    " API    Reference ",
)
```

becomes:

```python
("Introduction", "API Reference")
```

For code blocks, we preserve their internal indentation instead of using the short-text cleaner.

## 15. Step 5 — Construct `NormalizedDocument`

```python
return NormalizedDocument(
    url=fetched_url,
    canonical_url=canonical_url,
    title=_clean_short_text(document.title),
    description=_clean_short_text(document.description),
    body=_clean_body(document.body, code_blocks),
    author=_clean_short_text(document.author),
    published_at=document.published_at,
    headings=headings,
    code_blocks=code_blocks,
    metadata=deepcopy(document.metadata),
)
```

This assembles the final output and returns it to `processor.py`.

| Field | What happens to it? |
|---|---|
| `url` | Structurally validated and normalized |
| `canonical_url` | Same-host canonical hint selected if valid; otherwise fetched URL |
| `title` | Unicode normalized and whitespace collapsed |
| `description` | Same as title |
| `body` | Prose cleaned, known code blocks protected when they can be matched |
| `author` | Same as title |
| `published_at` | Passed through unchanged |
| `headings` | Each heading cleaned, empty headings removed |
| `code_blocks` | Newlines normalized, indentation preserved |
| `metadata` | Deep-copied, not otherwise normalized |

### Why `deepcopy()`?

Suppose:

```python
document.metadata = {"keywords": ["python", "fastapi"]}
```

Without copying, the normalized document might share the same nested list with the original parser result.

After a deep copy, changing the nested `keywords` list in the normalized result won't modify the original parser result's list.

This is useful because our processing pipeline has multiple stages. We don't want one stage silently changing data that another stage still uses.

### What about `published_at`?

The code passes it through unchanged. It **does not** parse dates or convert them to UTC here. Date extraction/parsing belongs to the parser, unless we explicitly add date normalization later.

---

# Real example: HTML → Parser → Normalizer

## 16. Complete execution walkthrough

Suppose our fetcher downloaded this HTML:

```html
<html>
  <head>
    <title>  Python   AsyncIO Tutorial </title>
    <meta name="description" content="  Learn  asynchronous Python.  ">
    <link rel="canonical" href="/tutorial/asyncio">
  </head>
  <body>
    <main>
      <h1>  Getting Started  </h1>
      <p>AsyncIO    lets Python run concurrent tasks.</p>
      <pre><code>async def main():
    await work()</code></pre>
    </main>
  </body>
</html>
```

Imagine it was fetched from:

```text
https://docs.example.com/tutorial/asyncio?ref=home
```

The HTML parser creates a `ParsedDocument` containing the content and the relative canonical URL hint. Then our normalizer receives that object:

```python
from crawler.parser.schemas import ParsedDocument
from crawler.processing.normalize import normalize_document

parsed = ParsedDocument(
    url="https://docs.example.com/tutorial/asyncio?ref=home",
    title="  Python   AsyncIO Tutorial ",
    description="  Learn  asynchronous Python.  ",
    body="AsyncIO    lets Python run concurrent tasks.\n\nasync def main():\n    await work()",
    headings=("  Getting Started  ",),
    code_blocks=("async def main():\n    await work()",),
    canonical_url_hint="/tutorial/asyncio",
    metadata={"keywords": ["python", "asyncio"]},
)

normalized = normalize_document(parsed)

print(normalized.url)
print(normalized.canonical_url)
print(normalized.title)
print(normalized.description)
print(normalized.headings)
print(normalized.code_blocks)
```

Expected fields, assuming our existing Frontier normalizer preserves the query string:

```text
https://docs.example.com/tutorial/asyncio?ref=home
https://docs.example.com/tutorial/asyncio
Python AsyncIO Tutorial
Learn asynchronous Python.
('Getting Started',)
('async def main():\n    await work()',)
```

What happened?

1. The fetched URL was validated and normalized.
2. The canonical hint `/tutorial/asyncio` was resolved using `urljoin()`.
3. The canonical hint was accepted because it stayed on the same hostname and didn't downgrade HTTPS.
4. The title and description were cleaned.
5. The body prose was cleaned while the matched code block retained its indentation.
6. Headings were cleaned.
7. Metadata was copied, not modified.
8. A new `NormalizedDocument` was returned.

Now `classify.py` can inspect the canonical URL and metadata, and `fingerprint.py` can generate a consistent content fingerprint.

---

## 17. What normalization doesn't do

| Task | Responsible module |
|---|---|
| Fetching a webpage | `fetcher/` |
| Checking robots, hosts, DNS, redirects, request rates | `policy/` and Coordinator |
| Parsing HTML into readable content | `parser/` |
| Cleaning document fields | **`normalize.py`** |
| Deciding documentation/tutorial/blog/issue | `classify.py` |
| Generating a SHA-256 hash | `fingerprint.py` |
| Enforcing `noindex` or empty-document skipping | `processor.py` |
| Checking existing database documents / deduplicating | Database Writer |
| Building PostgreSQL full-text vectors | Indexer |

A normalized document is **ready for classification and fingerprinting**. It isn't automatically approved for indexing, and it hasn't been stored in the database.

---

## 18. Things to test before connecting the Worker

Here are the main cases that can reveal problems:

| Test scenario | Expected behavior |
|---|---|
| Title with repeated spaces | Collapse to one space |
| Title containing only spaces | Return `None` |
| Windows `\r\n` newlines | Convert to `\n` |
| Body with too many blank lines | Reduce excess newlines |
| Code block with indentation | Keep spaces and line breaks |
| Code block not found inside body | Check for formatting loss; this is an existing limitation |
| Relative canonical URL | Resolve against fetched URL |
| Different-host canonical hint | Ignore hint |
| HTTPS page suggesting HTTP canonical | Ignore hint |
| Invalid fetched URL | Raise `ValueError` |
| Nested metadata changed after normalization | Original metadata should remain unchanged |
| Empty body | Return empty body; processor decides to skip |

The tricky test is **code-block preservation**. A webpage can have slightly different representations of code in `body` and `code_blocks`, so we shouldn't assume the exact substring match will always succeed.

---

# Final flow

```text
Fetched HTML response
        |
        v
     parser.py
        |
        v
  ParsedDocument
        |
        v
normalize_document()
        |
        +-- _validate_source_url() -> normalized fetched URL
        |
        +-- _canonical_url() ------> selected canonical identity
        |
        +-- _clean_short_text() ---> title, description, author
        |
        +-- _clean_code() ---------> preserved code indentation
        |
        +-- _clean_body() ---------> clean prose + protected code
        |
        +-- deepcopy() ------------> independent metadata copy
        |
        v
  NormalizedDocument
        |
        +------> classify.py -----> ClassificationResult
        |
        +------> fingerprint.py --> Content hash
        |
        v
      processor.py
        |
        v
   ProcessedDocument
```

**So basically:** the parser extracts *what the page contains*. The normalizer makes that extracted information *consistent*. The classifier decides *what kind of page it is*. The fingerprint module computes *a stable content hash*. The processor connects those results.

And none of these modules need to fetch the URL again.
