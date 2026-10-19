# Processor Model

> **Developer's Eye — Content Processing Pipeline**  
> **File:** `crawler/src/crawler/processing/processor.py`  
> **Input:** `ParseResult` → **Output:** `ProcessingResult`

---

# Step by step

So we already made 3 modules for content processing.

- `normalize.py` cleans the parsed document.
- `classify.py` identifies what kind of document it is and its technology tags.
- `fingerprint.py` generates a SHA-256 hash of the selected normalized content.

But who is going to connect all of them? And what if a website says **don't index this page**? Or the parser extracted an empty webpage?

That's why we made **`processor.py`**.

Think of it like our Policy Coordinator, but for content processing. It doesn't do the actual normalization, classification, or fingerprinting. It calls those modules in the correct order, checks whether a document should be skipped, and assembles the final schema.

```text
Fetcher -> Policy Coordinator -> Worker -> HTML Parser
                                             |
                                         ParseResult
                                             |
                                        processor.py
                                             |
                                For each ParsedDocument
                                             |
                                     normalize_document()
                                             |
                                    NormalizedDocument
                                             |
                                   noindex / empty check
                                       /         \
                                    skip         allow
                                     |             |
                              SkippedDocument  classify_document()
                                                   |
                                           fingerprint_document()
                                                   |
                                           ProcessedDocument
                                       \         /
                                       ProcessingResult
                                             |
                                            Worker
                                             |
                                 Database Writer / Indexer
```

**One important thing:** the processor never fetches a URL, checks DNS, inserts anything into the database, or puts links into the frontier. It only processes content the parser already extracted.

---

# 1. Why do we need the processor?

Suppose our crawler fetched 3 pages.

**Page 1: Normal documentation**

```text
URL: https://docs.example.com/python
Title: Python Documentation
Body: Python is a programming language.
```

We want to clean it, classify it as documentation, generate a content hash, and return a `ProcessedDocument`.

**Page 2: Website doesn't want the page indexed**

```html
<meta name="robots" content="noindex">
```

Even if the fetch was allowed, we should not add the page to our searchable index. Return a `SkippedDocument` with reason `NOINDEX`.

**Page 3: Empty webpage**

```html
<html><body></body></html>
```

If the parser couldn't find any meaningful body or code content, skip indexing it with reason `EMPTY_CONTENT`.

The processor makes these decisions in one place, rather than putting them inside the normalizer, classifier, or fingerprint module.

---

# 2. First understand the robots stuff

This is the part that can get confusing because we already created a Robots Policy for the crawler.

**Robots Policy and indexing directives are not exactly the same thing.**

There are 3 mechanisms to know.

| Mechanism | Where it lives | Main purpose | When we check it |
|---|---|---|---|
| `robots.txt` | A file at a site's origin, like `https://example.com/robots.txt` | Tell crawlers which URL paths they may fetch | **Before fetching** the page, in our Robots Policy / Policy Coordinator |
| HTML robots meta tag | Inside a fetched HTML document's `<head>` | Tell search engines whether to index that page or follow its links | **After fetching**, when we parse/process the HTML and handle discovered links |
| HTTP `X-Robots-Tag` | In the HTTP response headers | Similar indexing directives, including for non-HTML files | **After receiving response headers**, before indexing |

## Case 1: `robots.txt` — can we fetch the page?

Suppose `https://example.com/robots.txt` contains:

```text
User-agent: *
Disallow: /private/
Allow: /docs/
```

Here:

- `User-agent: *` means these rules target crawlers generally.
- `Disallow: /private/` means compliant crawlers shouldn't request URLs under `/private/`.
- `Allow: /docs/` explicitly allows that path, subject to rule precedence.

Now our crawler discovers:

```text
https://example.com/private/account
```

**Policy Coordinator → Robots Policy → DENY.**

We don't fetch that page. Therefore there is no HTML for `processor.py` to process.

Now it discovers:

```text
https://example.com/docs/python
```

Robots might allow fetching it, so our coordinator can continue checking the other policies and fetch it.

**Remember:** `robots.txt` controls fetching/crawling behavior. It does not automatically say whether content is allowed to appear in search results. Also, a disallowed page can't be fetched to read any HTML `noindex` directive it may contain.

## Case 2: HTML robots meta — can we index the fetched page?

Suppose fetching this page was allowed:

```text
https://example.com/internal-guide
```

But inside its HTML we find:

```html
<head>
    <meta name="robots" content="noindex, nofollow">
</head>
```

Now the website is giving two instructions:

- **`noindex`**: don't include this page in the search index.
- **`nofollow`**: don't follow links on this page.

So our parser extracts the metadata, and `processor.py` should skip the document for indexing.

But page-wide `nofollow` is **not implemented in `processor.py`**. The Worker must consider it when deciding whether to enqueue the `ParseResult.discovered_links`.

## Case 3: `X-Robots-Tag` — instructions in response headers

HTML pages can have indexing instructions in their HTTP headers too.

For example:

```http
HTTP/1.1 200 OK
Content-Type: text/html
X-Robots-Tag: noindex
```

Or a PDF response could have:

```http
Content-Type: application/pdf
X-Robots-Tag: noindex
```

The header means that resource should not be indexed by crawlers that honor the directive.

**Our current processor does not check this header.** Its input is `ParsedDocument`, not the original HTTP response headers. When building the Worker, we need to check the header before indexing or deliberately pass parsed header directives into the document's metadata.

Don't confuse it with `robots.txt`: the header is only available *after* an HTTP response is received.

---

# 3. What do `noindex`, `nofollow`, `none`, and other directives mean?

| Directive | Meaning | Our current implementation |
|---|---|---|
| `index` | Indexing is allowed (subject to other restrictions) | No special action |
| `noindex` | Don't put the page in search results / searchable index | `processor.py` skips it |
| `follow` | Following links is allowed (subject to crawling policy) | No special action |
| `nofollow` | Don't follow links discovered on this page | **Not enforced here**; Worker must handle |
| `none` | Equivalent to `noindex, nofollow` | Processor skips indexing; Worker still must handle links |
| `noarchive` | Don't show a cached copy in search results | Not implemented |
| `nosnippet` | Don't show a search-result text snippet | Not implemented |

Now imagine these cases:

**Case A:**

```html
<meta name="robots" content="noindex">
```

Skip the page for indexing. `noindex` by itself does **not** forbid following its links.

**Case B:**

```html
<meta name="robots" content="nofollow">
```

`nofollow` alone does **not** mean don't index the current page. Our processor may accept it, but the Worker should avoid enqueuing links from the page when respecting this directive.

**Case C:**

```html
<meta name="robots" content="none">
```

Equivalent to `noindex, nofollow`. Skip indexing and don't follow its links.

**Case D: link-specific nofollow**

```html
<a href="https://example.com/another-page" rel="nofollow">Another page</a>
```

This is different from the **page-wide** meta tag. It applies to that particular link. Our `links.py` records `nofollow=True` on the corresponding `DiscoveredLink`; the Worker/Frontier should use that when deciding whether to enqueue it.

**Important:** these rules are crawler instructions, not access control or a security mechanism. `noindex` doesn't make a page private, and `robots.txt` doesn't protect sensitive data.

---

# 4. Where does `robots_directives` come from?

Our `metadata.py` already extracts this HTML:

```html
<meta name="robots" content="noindex, nofollow">
```

into data shaped like:

```python
metadata = {
    "robots_directives": ["noindex", "nofollow"]
}
```

Then the parser puts that metadata into `ParsedDocument`.

After normalization, the metadata is still available in `NormalizedDocument.metadata`.

So inside the processor, we can call:

```python
_has_noindex(normalized.metadata)
```

We don't need to parse HTML again. We already did that in `metadata.py`.

**Current limitation:** this implementation is designed around a general `<meta name="robots">` value. It doesn't fully implement crawler-specific tags such as `<meta name="googlebot" ...>` or `X-Robots-Tag: googlebot: noindex`. We should handle agent-scoped rules explicitly if we add them later; don't simply apply all bot-specific instructions to every crawler.

---

# 5. `_ROBOTS_SEPARATOR` and `_NO_INDEX`

```python
_ROBOTS_SEPARATOR = re.compile(r"[,;\s]+")
_NO_INDEX = frozenset({"noindex", "none"})
```

### Why `_ROBOTS_SEPARATOR`?

Suppose we get:

```text
"noindex, nofollow"
```

We need to split it into individual instructions.

`[,;\s]+` matches one or more separators:

- `,` — comma
- `;` — semicolon
- `\s` — whitespace, such as spaces or tabs
- `+` — one or more of the above

Example:

```python
_ROBOTS_SEPARATOR.split("noindex, nofollow")
```

Returns:

```python
["noindex", "nofollow"]
```

### Why `frozenset`?

```python
_NO_INDEX = frozenset({"noindex", "none"})
```

A `frozenset` is an immutable set. We aren't going to change these two directive names while running the function.

We only need fast membership tests: **did the page specify `noindex` or `none`?**

---

# 6. `_has_noindex()` — check HTML indexing directives

```python
def _has_noindex(metadata: dict) -> bool:
    raw = metadata.get("robots_directives", ())

    if isinstance(raw, str):
        values = (raw,)
    elif isinstance(raw, (list, tuple, set, frozenset)):
        values = raw
    else:
        return False

    for value in values:
        if not isinstance(value, str):
            continue
        directives = {
            item.casefold()
            for item in _ROBOTS_SEPARATOR.split(value.strip())
            if item
        }
        if directives & _NO_INDEX:
            return True

    return False
```

Let's go through it.

## Step A: Get directives

```python
raw = metadata.get("robots_directives", ())
```

If the metadata has the key, get its value. If it doesn't exist, use an empty tuple.

## Step B: Make values iterable

```python
if isinstance(raw, str):
    values = (raw,)
```

If `raw` is a single string such as `"noindex, nofollow"`, turn it into a one-item tuple.

Notice the comma:

```python
("noindex, nofollow",)
```

Without the comma, parentheses alone wouldn't create a one-item tuple.

If the value is already a list, tuple, or set, use it directly.

Other unexpected types return `False`.

## Step C: Loop through values

```python
for value in values:
    if not isinstance(value, str):
        continue
```

Ignore any non-string entry instead of crashing.

## Step D: Split and lowercase

```python
directives = {
    item.casefold()
    for item in _ROBOTS_SEPARATOR.split(value.strip())
    if item
}
```

Suppose the input is:

```python
"NOINDEX, NoFollow"
```

We get:

```python
{"noindex", "nofollow"}
```

We use `casefold()` for case-insensitive matching.

The `{...}` here is a **set comprehension**. It collects unique directive tokens.

## Step E: Check set intersection

```python
if directives & _NO_INDEX:
    return True
```

The `&` means **set intersection**: values that exist in both sets.

Example:

```python
directives = {"noindex", "nofollow"}
_NO_INDEX = frozenset({"noindex", "none"})

print(directives & _NO_INDEX)
# {'noindex'}
```

The intersection is not empty, so return `True`.

If the directives only contain `nofollow`, the intersection is empty and `_has_noindex()` returns `False`.

This helper detects HTML noindex instructions. It doesn't know about `robots.txt` or response headers.

---

# 7. `process_document()` — process one parsed document

```python
def process_document(
    document: ParsedDocument,
) -> ProcessedDocument | SkippedDocument:
```

Input is one `ParsedDocument`.

Output is **either**:

- `ProcessedDocument` — accepted and ready for a later database writer.
- `SkippedDocument` — not suitable for indexing, with a reason.

The `|` in the return annotation means either type is allowed.

## Step 1: Validate the input

```python
if not isinstance(document, ParsedDocument):
    raise TypeError("document must be a ParsedDocument")
```

We expect a parser schema, not raw HTML or a random dictionary.

## Step 2: Normalize

```python
try:
    normalized = normalize_document(document)
except ValueError as exc:
    return SkippedDocument(
        url=document.url,
        reason=SkipReason.INVALID_URL,
        details=str(exc),
    )
except (TypeError, UnicodeError) as exc:
    return SkippedDocument(
        url=document.url,
        reason=SkipReason.PROCESSING_ERROR,
        details=f"Normalization failed: {exc}",
    )
```

First, we call the normalizer.

If normalization raises one of these expected exceptions, we return a skipped result instead of stopping the entire processing pipeline.

`str(exc)` stores the error description for debugging.

**Small limitation:** the current code assumes any `ValueError` from normalization is an invalid URL. If a future normalizer raises `ValueError` for another reason, `INVALID_URL` could be misleading. We can introduce more specific error types later.

## Step 3: Noindex check

```python
if _has_noindex(normalized.metadata):
    return SkippedDocument(
        url=normalized.url,
        reason=SkipReason.NOINDEX,
        details="Page contains a robots noindex directive",
    )
```

Suppose:

```python
normalized.metadata = {
    "robots_directives": ["noindex", "nofollow"]
}
```

`_has_noindex()` returns `True`.

We immediately return `SkippedDocument`, so **classification and fingerprinting never run for this page**.

This is an indexing decision, not a retroactive fetching decision. The fetch already happened.

## Step 4: Check empty content

```python
if not normalized.body.strip() and not any(
    block.strip() for block in normalized.code_blocks
):
    return SkippedDocument(
        url=normalized.url,
        reason=SkipReason.EMPTY_CONTENT,
        details="No readable body or code content to index",
    )
```

There are two conditions:

1. Body contains no non-whitespace text.
2. **Every** code block is empty too.

Both must be true to skip.

### Case 1: Empty body, no code

```python
body = "   "
code_blocks = ()
```

Skip the document.

### Case 2: Empty body, but code exists

```python
body = ""
code_blocks = ("print('Hello World')",)
```

**Don't skip it.** A code-only page can still be useful for developers.

### Why `any()`?

`any(block.strip() for block in normalized.code_blocks)` returns `True` if at least one code block has actual content.

The `not ... and not ...` condition only skips when there is neither readable prose nor code.

## Step 5: Classify and fingerprint

```python
try:
    classification = classify_document(normalized)
    content_hash = fingerprint_document(normalized)
except (TypeError, ValueError, UnicodeError) as exc:
    return SkippedDocument(
        url=normalized.url,
        reason=SkipReason.PROCESSING_ERROR,
        details=f"Classification/fingerprinting failed: {exc}",
    )
```

We call the modules we already wrote.

`classify_document()` returns `ClassificationResult`, containing document type, tags, confidence, and method.

`fingerprint_document()` returns the 64-character SHA-256 string.

If an expected data-related error happens, we return a `SkippedDocument` with `PROCESSING_ERROR` instead of discarding the whole batch.

## Step 6: Copy metadata and store classification details

```python
metadata = dict(normalized.metadata)

metadata["classification"] = {
    "confidence": classification.confidence,
    "method": classification.method,
}
```

Why `dict()`? We don't want to modify the original metadata dictionary when adding classification diagnostics.

Example:

```python
{
    "keywords": ["python"],
    "classification": {
        "confidence": 0.93,
        "method": "rules:tutorial_path",
    },
}
```

This is a **shallow copy**. It creates a new outer dictionary; nested values are not deep-copied here. The normalizer already deep-copied the parser metadata earlier.

## Step 7: Build the final `ProcessedDocument`

```python
return ProcessedDocument(
    url=normalized.url,
    canonical_url=normalized.canonical_url,
    document_type=classification.document_type,
    title=normalized.title,
    description=normalized.description,
    body=normalized.body,
    author=normalized.author,
    content_hash=content_hash,
    published_at=normalized.published_at,
    headings=normalized.headings,
    code_blocks=normalized.code_blocks,
    tags=classification.tags,
    metadata=metadata,
)
```

We combine the normalized content, classification, and fingerprint into one data object.

This is **database-ready data**, not a database insert. The Worker/Database Writer will handle persistence.

---

# 8. `process()` — process the complete parser result

```python
def process(parse_result: ParseResult) -> ProcessingResult:
    if not isinstance(parse_result, ParseResult):
        raise TypeError("parse_result must be a ParseResult")

    accepted: list[ProcessedDocument] = []
    skipped: list[SkippedDocument] = []

    for document in parse_result.documents:
        result = process_document(document)

        if isinstance(result, ProcessedDocument):
            accepted.append(result)
        else:
            skipped.append(result)

    return ProcessingResult(
        source_url=parse_result.source_url,
        documents=tuple(accepted),
        skipped=tuple(skipped),
    )
```

Our HTML parser usually returns one `ParsedDocument` per webpage.

But later when we add RSS/Atom or JSON APIs, one `ParseResult` might contain **multiple documents**.

So we loop through every document and process them independently.

- Accepted documents go into `accepted`.
- Skipped documents go into `skipped`.

Finally, we convert both lists into tuples and return `ProcessingResult`.

### Why return skipped documents at all?

Because we want observability.

Imagine the Worker reports:

```text
Parsed:    100
Accepted:   82
Noindex:    10
Empty:       6
Errors:      2
```

Now the crawler's admin dashboard can explain why some pages didn't get indexed. These values are illustrative, not measured.

---

# 9. Complete real-world scenario

Suppose the crawler successfully fetched 3 HTML pages.

### Page 1 — regular Python tutorial

```python
ParsedDocument(
    url="https://docs.python.org/3/tutorial/",
    title="Python Tutorial",
    body="Python is a programming language.",
    metadata={},
)
```

Flow:

```text
Normalize -> noindex? No -> empty? No
    -> Classify as TUTORIAL
    -> Generate SHA-256 hash
    -> ProcessedDocument
```

### Page 2 — page requests noindex

```python
ParsedDocument(
    url="https://example.com/private-guide",
    title="Private Guide",
    body="A guide that was fetched successfully.",
    metadata={"robots_directives": ["noindex"]},
)
```

Flow:

```text
Normalize -> noindex? Yes -> SkippedDocument(NOINDEX)
```

It is **not indexed**, even though it was already fetched. `noindex` is not the same as a `robots.txt` `Disallow` rule.

### Page 3 — empty content

```python
ParsedDocument(
    url="https://example.com/empty",
    title="Empty page",
    body="   ",
    metadata={},
)
```

Flow:

```text
Normalize -> noindex? No -> empty? Yes
    -> SkippedDocument(EMPTY_CONTENT)
```

If these are all inside one `ParseResult`, the processing output would have **one accepted document and two skipped documents**.

---

# 10. Simple offline test

You can test the processor without a Crawler VM, HTTP request, or database.

```python
from crawler.parser.schemas import ParsedDocument, ParseResult
from crawler.processing.processor import process

url = "https://docs.example.com/tutorial/"

parsed = ParseResult(
    source_url=url,
    content_type="text/html",
    documents=(
        ParsedDocument(
            url=url,
            title="  Python Tutorial  ",
            body="Learn Python and FastAPI.",
        ),
        ParsedDocument(
            url="https://docs.example.com/not-for-search",
            title="Hidden from search",
            body="This page has readable text.",
            metadata={"robots_directives": ["noindex"]},
        ),
        ParsedDocument(
            url="https://docs.example.com/empty",
            title="Empty page",
            body="",
        ),
    ),
)

result = process(parsed)

print("Accepted:", len(result.documents))
print("Skipped:", len(result.skipped))

for doc in result.documents:
    print(doc.canonical_url, doc.document_type, doc.content_hash[:12])

for item in result.skipped:
    print(item.url, item.reason)
```

Expected counts with the current pipeline:

```text
Accepted: 1
Skipped: 2
```

---

# 11. What this processor does NOT do yet

We should keep these responsibilities separate when building the Worker.

| Task | Responsible component |
|---|---|
| Check `robots.txt` before fetching | Robots Policy + Policy Coordinator |
| Check allowed hosts and unsafe IPs | Host / DNS Policy + Policy Coordinator |
| Perform HTTP requests | HTTP Fetcher |
| Extract HTML robots meta directives | `html/metadata.py` |
| Skip indexing an HTML `noindex` page | `processor.py` |
| Respect `X-Robots-Tag: noindex` | **To implement** in Worker/header handling |
| Handle page-wide `nofollow` when enqueuing discovered URLs | **To implement** in Worker |
| Handle individual link `rel="nofollow"` | `links.py` records it; Worker decides whether to enqueue |
| Classify a document | `classify.py` |
| Compute exact-content fingerprint | `fingerprint.py` |
| Deduplicate against stored content | Database Writer |
| Save documents to PostgreSQL | Database Writer |
| Update TSVECTOR / GIN index | Indexer / database layer |

**One more limitation:** the current `_has_noindex()` recognizes the tokens `noindex` and `none` in the extracted general robots metadata. It isn't a full parser for every robot directive, per-crawler rule, or HTTP header format. When we add those, we should test their precedence and scope rather than guessing.

---

# 12. Final summary

So our Content Processing Pipeline is now connected.

```text
ParseResult
   |
   +-- ParsedDocument 1 -> normalize -> checks -> classify -> fingerprint -> accepted
   |
   +-- ParsedDocument 2 -> normalize -> noindex? -> skipped
   |
   +-- ParsedDocument 3 -> normalize -> empty? -> skipped
   |
   v
ProcessingResult
   |
   +-- documents: tuple[ProcessedDocument, ...]
   |
   +-- skipped: tuple[SkippedDocument, ...]
   |
   v
Worker -> Database Writer -> Indexer
```

**Main thing to remember:**

- `robots.txt` asks whether we can **fetch** a URL.
- HTML robots meta and `X-Robots-Tag` ask how the fetched resource can be **indexed / handled**.
- `processor.py` currently checks **HTML noindex** and **empty content**, then connects normalization, classification, and fingerprinting.
- The Worker will handle fetched response headers and discovered links, and the Database Writer will handle persistence and deduplication.

**Next milestone:** connect the Fetcher, Parser, and Processor inside the Crawler Worker, then run a small controlled end-to-end crawl.
