# Classifier Model

> **Developer's Eye — Content Processing Pipeline**  
> **File:** `crawler/src/crawler/processing/classify.py`  
> **Input:** `NormalizedDocument` → **Output:** `ClassificationResult`

---

# Step by step

The classifier identifies **what kind of document** we fetched and **what developer technologies** it talks about.

It doesn't fetch URLs, write to the database, or decide whether a URL is safe to crawl. We already have separate modules for those things.

## 1. Patterns

So our patterns type is **`(name, pattern)`**.

```python
("python", r"\bpython\b")
("fastapi", r"\bfastapi\b")
("docker", r"\bdocker\b")
```

- `\b` means **word boundary**.
- `\bpython\b` means the word should be exactly `python`, not part of another word such as `pythons`.
- `re.IGNORECASE` means `python`, `Python`, and `PYTHON` will match.
- `re.compile()` compiles the regex once so we can reuse it for many documents.

```python
_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("python", r"\bpython\b"),
        ("javascript", r"\bjavascript\b"),
        ("typescript", r"\btypescript\b"),
        ("fastapi", r"\bfastapi\b"),
        ("docker", r"\bdocker\b"),
    )
)
```

The real file has more patterns, including C++, C#, React, Next.js, PostgreSQL, Kubernetes, AWS, and Redis.

For all pattern information, check [pattern.md](./pattern.md).

### Why we needed this?

Crawler fetched:

```text
Title: Building REST APIs with Python and FastAPI

Description: Use PostgreSQL and Docker to build and deploy APIs.

Body:
FastAPI is a Python framework for building APIs.
You can use PostgreSQL as your database and
Docker to deploy your application.
```

Classifier identifies:

```python
topics = ["python", "fastapi", "postgresql", "docker"]
```

This is helpful for indexing later.

Without topic classification, you might store:

```python
{
    "title": "Building APIs with FastAPI",
    "body": "Learn to build APIs using Python...",
}
```

With classification, you can enrich the document:

```python
{
    "title": "Building APIs with FastAPI",
    "body": "Learn to build APIs using Python...",
    "topics": ["python", "fastapi"],
}
```

**One important detail:** Our current `_topic_tags()` checks the **title, description, keywords, and URL path**, not the whole body. In the first example, PostgreSQL and Docker are found because I included them in the **description**. If they appeared only in the body, this version wouldn't tag them.

---

## 2. Title patterns

```python
_TUTORIAL_TITLE = re.compile(
    r"\b(?:tutorial|how[ -]to|step[ -]by[ -]step|getting started|walkthrough)\b",
    re.IGNORECASE,
)
```

Recognizes if the title has:

- Getting Started with FastAPI
- Python Tutorial
- How-to Guide for Docker
- Step-by-step Kubernetes Setup

Then:

```python
_DOCUMENTATION_TITLE = re.compile(
    r"\b(?:documentation|api reference|developer reference|technical reference)\b",
    re.IGNORECASE,
)
```

Recognizes document titles like:

- Python Documentation
- FastAPI API Reference
- Rust Developer Reference
- Kubernetes Technical Reference

### Why separate them?

Because documentation and tutorials are different kinds of developer content.

Documentation usually serves as a reference. Tutorials generally explain how to accomplish a task step by step.

Later, the classifier will use these expressions only when stronger evidence, such as the URL, hasn't already determined a category.

---

## 3. Utility functions

### `_on_domain(host, domain) -> bool` — safe domain matching

This helper checks whether a hostname belongs to a particular domain or one of its subdomains.

```python
def _on_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)
```

| Term | Example | Meaning |
|---|---|---|
| Domain | `python.org` | Name in the DNS system |
| Subdomain | `docs.python.org` | Name under `python.org` |
| Hostname | `docs.python.org` | DNS name used to identify a network host |
| Host | `docs.python.org` | URL host; can also be an IP address |
| Origin | `https://docs.python.org` | Scheme + host + port (when relevant) |

#### Host vs domain

They can be the same string, but they aren't exactly the same concept.

Domain is a name in the DNS system. A registered domain is one you buy or register from a domain registrar.

Hostname is a name used to identify a host on a network. It's not necessarily the physical server where your website is hosted.

Suppose you made a website named **DevManiac**.

When hosted on Vercel, it will be `devmaniac.vercel.app`. This is a hostname under Vercel's domain.

Now you went to Hostinger and bought `devmaniac.com`. This is your registered domain. As you didn't connect it to your deployment yet, it won't automatically serve your website.

Then when you connect the domain to your hosting, `devmaniac.com` can become the hostname visitors use to access DevManiac.

One more real-world example.

Suppose you're using Gmail.

Google owns `google.com`. But to access your mail you go to `mail.google.com`.

| Website | Hostname | Parent domain |
|---|---|---|
| Google Search | `www.google.com` | `google.com` |
| Gmail | `mail.google.com` | `google.com` |
| Google Maps | `maps.google.com` | `google.com` |
| Google Drive | `drive.google.com` | `google.com` |

A domain name doesn't have to be individually registered. `mail.google.com` is both a domain name and a hostname.

Our function `_on_domain(host, domain)` checks:

1. If `host == domain` → `True`.
2. Otherwise, if `host.endswith("." + domain)` → `True`.
3. Otherwise → `False`.

Suppose `domain = "python.org"`:

```python
_on_domain("python.org", "python.org")       # True
_on_domain("api.python.org", "python.org")   # True
_on_domain("fakepython.org", "python.org")    # False
```

The dot before the domain matters. Without it, `fakepython.org` would also match an ordinary `endswith("python.org")` check.

> **Important:** This is safe *string matching* for classification. It is **not** the crawler's Host Policy or DNS Policy and does not authorize fetching.

### `_metadata_string(metadata, *keys)` — read metadata

What's `*keys`?

It lets your function accept multiple keys.

Example:

```python
metadata = {
    "og:type": "article",
    "author": "John Doe",
}

result = _metadata_string(
    metadata,
    "og:type",
    "og_type",
)
```

The function checks the first key: `metadata.get("og:type")`.

If it finds `"article"`, then it returns it. If not, it tries the other key `"og_type"`.

```python
def _metadata_string(metadata: dict, *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
```

If none of the keys has a nonempty string, it returns `""`.

### `_topic_tags()` — extract technology tags

Now we get to an important function.

```python
def _topic_tags(document: NormalizedDocument) -> tuple[str, ...]:
    ...
```

This function receives a normalized document and returns recognized technologies.

Imagine your normalized document contains:

```python
title = "Build REST APIs using Python and FastAPI"
description = "Using PostgreSQL as our database"
metadata = {"keywords": ["python", "backend", "fastapi"]}
```

We want:

```python
("python", "fastapi", "postgresql")
```

#### Step A: Retrieve metadata

```python
metadata = (
    document.metadata
    if isinstance(document.metadata, dict)
    else {}
)
```

This is a conditional expression.

It means: if `document.metadata` is a dictionary, use it. Otherwise, use an empty dictionary.

Why? Because the next operations expect dictionary methods such as `.get()`.

#### Step B: Extract keywords

```python
keywords = metadata.get("keywords", "")
```

If the key exists, retrieve its value. Otherwise, use `""`.

Next:

```python
if isinstance(keywords, (tuple, list)):
    keywords_text = " ".join(
        str(item)
        for item in keywords
        if isinstance(item, str)
    )
elif isinstance(keywords, str):
    keywords_text = keywords
else:
    keywords_text = ""
```

Suppose:

```python
keywords = ["python", "fastapi", "backend"]
```

`" ".join()` combines them:

```text
python fastapi backend
```

If keywords is already a string, the next branch uses it directly.

#### Step C: Combine searchable text

```python
searchable = " ".join(
    (
        document.title or "",
        document.description or "",
        keywords_text,
    )
)
```

Suppose:

```python
document.title = "Learn FastAPI"
document.description = "Python backend tutorial"
keywords_text = "postgresql docker"
```

The result:

```text
Learn FastAPI Python backend tutorial postgresql docker
```

Next:

```python
searchable += " " + urlsplit(
    document.canonical_url
).path.replace("-", " ").replace("_", " ")
```

If the URL path is `/python-fastapi-tutorial`, it becomes `/python fastapi tutorial`.

This makes technology names separated by hyphens or underscores easier to recognize.

#### Step D: Match predefined technologies

```python
return tuple(
    name
    for name, pattern in _TOPIC_PATTERNS
    if pattern.search(searchable)
)[:8]
```

This loops through every technology pattern. For each matching pattern, it adds the technology name.

The result might be:

```python
("python", "fastapi", "postgresql", "docker")
```

**Why `[:8]`?** To keep at most eight tags.

It is a simple limit, not a relevance-ranking system. The first eight matching patterns in your predefined vocabulary win.

---

# Main function: `classify_document()`

Everything above was preparation. The actual classification happens here.

## 4. Validation and preparation

First we did some validation and got `host`, `path`, `segments`, `title`, `metadata`, and `tags`.

```python
if not isinstance(document, NormalizedDocument):
    raise TypeError("document must be a NormalizedDocument")

parsed_url = urlsplit(document.canonical_url)
host = (parsed_url.hostname or "").lower().removeprefix("www.")

if parsed_url.scheme.lower() not in {"http", "https"} or not host:
    raise ValueError("document.canonical_url must be an absolute HTTP(S) URL")

path = parsed_url.path.lower()
segments = tuple(segment for segment in path.split("/") if segment)
title = document.title or ""
metadata = document.metadata if isinstance(document.metadata, dict) else {}
tags = _topic_tags(document)
```

Example:

```text
URL:      https://github.com/fastapi/fastapi/issues/123
Host:     github.com
Path:     /fastapi/fastapi/issues/123
Segments: ("fastapi", "fastapi", "issues", "123")
Title:    whatever title the document has
Metadata: whatever metadata the document has
Tags:     extracted by our _topic_tags() utility
```

Why `segments`? Because each position in the URL path can tell us what type of page it is.

`urlsplit()` can raise `ValueError` for some malformed URLs; our full classifier handles that when reading the hostname.

## 5. `found()` — return the result

`found()` returns the classification respecting the `ClassificationResult` schema.

```python
def found(kind: DocumentType, score: float, rule: str) -> ClassificationResult:
    return ClassificationResult(
        document_type=kind,
        confidence=score,
        tags=tags,
        method=f"rules:{rule}",
    )
```

Instead of rebuilding the same result object in every case, we just write:

```python
return found(DocumentType.ISSUE, 0.99, "github_issue")
```

Which means:

```python
ClassificationResult(
    document_type=DocumentType.ISSUE,
    confidence=0.99,
    tags=tags,
    method="rules:github_issue",
)
```

`confidence` is a **manually chosen score**, not a real 99% probability.

---

# Classification cases

## Case 1: GitHub

```python
if _on_domain(host, "github.com"):
    if (len(segments) >= 4 and segments[2] == "issues"
            and segments[3].isdigit()):
        return found(DocumentType.ISSUE, 0.99, "github_issue")

    if (len(segments) >= 4 and segments[2] == "discussions"
            and segments[3].isdigit()):
        return found(DocumentType.DISCUSSION, 0.99, "github_discussion")

    reserved = {
        "about", "apps", "collections", "enterprise", "explore",
        "features", "issues", "login", "marketplace", "notifications",
        "orgs", "pricing", "pulls", "search", "security", "settings",
        "signup", "site", "sponsors", "topics", "trending", "users",
    }

    if len(segments) == 2 and segments[0] not in reserved:
        return found(DocumentType.REPOSITORY, 0.97, "github_repository")
```

### Type 1: Issue

```python
if (len(segments) >= 4 and segments[2] == "issues"
        and segments[3].isdigit()):
```

If there are **4 or more segments** and the third one is `issues`, most probably it's a GitHub issue.

A typical GitHub issue:

```text
https://github.com/illionillion/tokyo-event-calendar/issues/32
```

Path:

```text
/illionillion/tokyo-event-calendar/issues/32
```

It has 4 segments and the third one is `issues`.

**Confidence: `0.99`**.

### Type 2: Discussion

If there are 4 or more segments and the third one is `discussions`, and the fourth one is a number, it's probably a GitHub discussion.

```text
https://github.com/owner/repo/discussions/42
```

**Confidence: `0.99`**.

### Type 3: Repo

If only 2 segments, it usually means:

```text
https://github.com/username/repo
```

Those `reserved` words are GitHub functionality, such as `topics`, `settings`, or `search`. If the first segment isn't one of those reserved words, we treat the two-segment path as a repository candidate.

**Confidence: `0.97`**.

> This is still a heuristic, not proof that the repository exists. Our classifier doesn't make an API request to check it.

---

## Case 2: GitLab

```python
if _on_domain(host, "gitlab.com"):
    if (len(segments) >= 5 and segments[-3] == "-"
            and segments[-2] == "issues" and segments[-1].isdigit()):
        return found(DocumentType.ISSUE, 0.98, "gitlab_issue")
```

Example:

```text
https://gitlab.com/group/project/-/issues/123
```

If there are **5 segments or more**, the third from the last is `-`, the second last segment is `issues`, and the last segment is a number, that's probably a GitLab issue.

Why the negative indexes?

```python
segments[-3]  # "-"
segments[-2]  # "issues"
segments[-1]  # "123"
```

GitLab projects can be inside nested groups, so checking from the end is easier.

**Confidence: `0.98`**.

---

## Case 3: Q&A hosts

```python
qa_host = (
    _on_domain(host, "stackoverflow.com")
    or _on_domain(host, "stackexchange.com")
    or _on_domain(host, "serverfault.com")
    or _on_domain(host, "superuser.com")
    or _on_domain(host, "askubuntu.com")
)

if qa_host and len(segments) >= 2 and segments[0] in {"q", "questions"} and segments[1].isdigit():
    return found(DocumentType.QUESTION, 0.99, "qa_question")
```

So first we check if the host is one of the recognized Q&A websites.

`qa_host` is a boolean. If any of these domain checks returns `True`, then `qa_host` becomes `True`.

But not every page on Stack Overflow is a question.

Example:

```text
https://stackoverflow.com/questions/12345/why-python-is-slow
```

Segments:

```python
("questions", "12345", "why-python-is-slow")
```

- First segment is `questions` or `q`.
- Second segment is a number (`.isdigit()`).
- So we classify it as `QUESTION`.

Compare with:

```text
https://stackoverflow.com/help
```

This is not a question page, so it doesn't match.

**Confidence: `0.99`**.

**Note:** Use `"stackoverflow.com"`, not `"stackoverflow\\.com"`. `_on_domain()` compares plain strings, not regex patterns.

---

## Case 4: Reddit discussion

```python
if _on_domain(host, "reddit.com") and (
    len(segments) >= 4
    and segments[0] == "r"
    and segments[2] == "comments"
):
    return found(DocumentType.DISCUSSION, 0.98, "reddit_discussion")
```

Example:

```text
https://www.reddit.com/r/Python/comments/abc123/my_post/
```

Segments:

```python
("r", "python", "comments", "abc123", "my_post")
```

- First segment `r` means subreddit.
- Third segment `comments` indicates the Reddit post/comment thread path.
- So the classifier returns `DISCUSSION`.

We already removed `www.` from the hostname earlier, so `www.reddit.com` is treated as `reddit.com`.

**Confidence: `0.98`**.

---

## Case 5: Tutorial URL

```python
if any(part in {"tutorial", "tutorials"} for part in segments):
    return found(DocumentType.TUTORIAL, 0.93, "tutorial_path")
```

`any()` means if **at least one** segment matches, return `True`.

Example:

```text
https://docs.python.org/3/tutorial/
```

Segments:

```python
("3", "tutorial")
```

Even though this URL starts with `docs.`, we classify it as `TUTORIAL` because the tutorial rule happens **before** the documentation rule.

**Confidence: `0.93`**.

---

## Case 6: Documentation

```python
documentation_host = (
    host.startswith("docs.")
    or _on_domain(host, "readthedocs.io")
    or _on_domain(host, "developer.mozilla.org")
    or _on_domain(host, "learn.microsoft.com")
    or _on_domain(host, "docs.rs")
)

if documentation_host:
    return found(DocumentType.DOCUMENTATION, 0.95, "documentation_host")

if any(part in {"docs", "documentation", "reference", "api-reference"} for part in segments):
    return found(DocumentType.DOCUMENTATION, 0.88, "documentation_path")
```

Two ways to recognize documentation:

**Type 1: Host-based**

```text
https://docs.python.org/3/library/
https://developer.mozilla.org/en-US/docs/Web/JavaScript
https://learn.microsoft.com/en-us/dotnet/
```

If a known documentation hostname matches, we return `DOCUMENTATION`.

**Confidence: `0.95`**.

**Type 2: Path-based**

```text
https://example.com/docs/api/
https://example.com/reference/functions/
```

Even if the hostname isn't known, a segment like `docs` or `reference` can indicate documentation.

**Confidence: `0.88`**.

> Host-based matches are broad. A blog post living on `docs.example.com` could still be labeled documentation. We can refine these rules later using real crawl results.

---

## Case 7: Events and hackathons

```python
event_host = (
    _on_domain(host, "eventbrite.com")
    or _on_domain(host, "meetup.com")
)

if event_host and any(part in {"events", "event"} for part in segments):
    return found(DocumentType.EVENT, 0.93, "events_platform")

if _on_domain(host, "devpost.com") and "hackathons" in segments:
    return found(DocumentType.EVENT, 0.95, "devpost_hackathon")

if any(part in {"hackathon", "hackathons", "events"} for part in segments):
    return found(DocumentType.EVENT, 0.83, "event_path")
```

First, known event platforms.

Example:

```text
https://www.meetup.com/python-developers/events/123456/
```

This matches the event host plus `events` path.

**Confidence: `0.93`**.

Then Devpost:

```text
https://devpost.com/hackathons
```

If a Devpost path contains `hackathons`, we classify it as an event-related page.

**Confidence: `0.95`**.

Finally, a general event path:

```text
https://example.com/events/developer-meetup
```

Unknown host, but the URL contains `events`.

**Confidence: `0.83`**.

We don't classify every Devpost project submission as an event. Also, `luma.com` isn't included in this specific implementation yet; we can add its actual event URL patterns later.

---

## Case 8: Blogs and articles

```python
if any(part in {"blog", "blogs", "posts", "articles"} for part in segments):
    return found(DocumentType.BLOG, 0.89, "blog_path")

if host.startswith("blog.") or _on_domain(host, "dev.to") or _on_domain(host, "medium.com"):
    return found(DocumentType.BLOG, 0.86, "blog_platform")
```

Two ways again.

**Type 1: Path**

```text
https://example.com/blog/building-a-crawler
```

Path contains `blog`.

**Confidence: `0.89`**.

**Type 2: Host**

```text
https://dev.to/author/python-tips
https://medium.com/@author/some-article
https://blog.example.com/post
```

Known blog platform or `blog.` subdomain.

**Confidence: `0.86`**.

---

## Case 9: Guides / how-to pages

```python
if any(part in {"guide", "guides", "how-to"} for part in segments):
    return found(DocumentType.TUTORIAL, 0.77, "guide_path")
```

Example:

```text
https://example.com/guides/build-a-search-engine
```

If URL has `guide`, `guides`, or `how-to`, it's likely tutorial-style content.

But this evidence is weaker than an explicit `tutorial` path, so the confidence score is lower.

**Confidence: `0.77`**.

---

## Case 10: Title hints

```python
if _TUTORIAL_TITLE.search(title):
    return found(DocumentType.TUTORIAL, 0.72, "tutorial_title")

if _DOCUMENTATION_TITLE.search(title):
    return found(DocumentType.DOCUMENTATION, 0.68, "documentation_title")
```

Suppose URL doesn't help:

```text
https://example.com/post/123
```

But its title is:

```text
Getting Started with FastAPI
```

The `_TUTORIAL_TITLE` regex finds `Getting Started`, so classifier returns `TUTORIAL`.

**Confidence: `0.72`**.

Or title:

```text
Python API Reference
```

Then `_DOCUMENTATION_TITLE` matches and returns `DOCUMENTATION`.

**Confidence: `0.68`**.

We only reach these rules if the previous stronger URL rules didn't match.

---

## Case 11: Article metadata

```python
og_type = _metadata_string(metadata, "og:type", "og_type")

if og_type.casefold() == "article" or _metadata_string(
    metadata, "article:published_time", "published_time"
):
    return found(DocumentType.BLOG, 0.64, "article_metadata")
```

Our `metadata.py` might extract:

```html
<meta property="og:type" content="article">
```

Or article publication metadata:

```html
<meta property="article:published_time" content="2026-10-18T12:00:00Z">
```

`_metadata_string()` checks those recognized keys.

If `og:type` is `article` or the publication time is available as a nonempty metadata string, classifier returns `BLOG`.

**Confidence: `0.64`**.

Why lower? Because an `article` isn't always a blog. It could be a news or documentation article too.

---

## Case 12: No match

```python
return found(DocumentType.OTHER, 0.0, "no_match")
```

Suppose:

```text
https://example.com/random-page
```

No known platform, useful path, title pattern, or metadata hint.

Then don't invent a category. Return `OTHER`.

```python
ClassificationResult(
    document_type=DocumentType.OTHER,
    confidence=0.0,
    tags=(),
    method="rules:no_match",
)
```

**OTHER doesn't mean an error.** It means we couldn't classify the page with the rules we currently have.

---

# One full example

Let's say the normalizer gives us:

```python
from crawler.processing.schemas import NormalizedDocument

page = NormalizedDocument(
    url="https://docs.python.org/3/tutorial/",
    canonical_url="https://docs.python.org/3/tutorial/",
    body="Python is an interpreted programming language.",
    title="The Python Tutorial",
    description="An introduction to Python programming.",
)
```

Then:

```python
result = classify_document(page)
```

Execution:

1. Validate `NormalizedDocument` and canonical URL.
2. Get `host = "docs.python.org"`.
3. Get `segments = ("3", "tutorial")`.
4. `_topic_tags()` finds `python`.
5. GitHub / GitLab / QA / Reddit checks don't match.
6. Tutorial path matches → return immediately.

```python
ClassificationResult(
    document_type=DocumentType.TUTORIAL,
    confidence=0.93,
    tags=("python",),
    method="rules:tutorial_path",
)
```

Notice it **doesn't keep checking** the documentation rule. Once we `return`, the function is done.

---

# Quick classification table

| URL / signal | Type | Confidence | Rule |
|---|---|---:|---|
| `github.com/user/repo/issues/32` | ISSUE | 0.99 | `github_issue` |
| `github.com/user/repo/discussions/42` | DISCUSSION | 0.99 | `github_discussion` |
| `github.com/user/repo` | REPOSITORY | 0.97 | `github_repository` |
| `gitlab.com/group/project/-/issues/123` | ISSUE | 0.98 | `gitlab_issue` |
| `stackoverflow.com/questions/12345/...` | QUESTION | 0.99 | `qa_question` |
| `reddit.com/r/Python/comments/abc123/...` | DISCUSSION | 0.98 | `reddit_discussion` |
| `/tutorial/` | TUTORIAL | 0.93 | `tutorial_path` |
| `docs.python.org/...` (without earlier match) | DOCUMENTATION | 0.95 | `documentation_host` |
| `/docs/` | DOCUMENTATION | 0.88 | `documentation_path` |
| `meetup.com/.../events/123` | EVENT | 0.93 | `events_platform` |
| `devpost.com/hackathons` | EVENT | 0.95 | `devpost_hackathon` |
| `/blog/` | BLOG | 0.89 | `blog_path` |
| `/guides/` | TUTORIAL | 0.77 | `guide_path` |
| Title contains `Getting Started` | TUTORIAL | 0.72 | `tutorial_title` |
| Metadata `og:type = article` | BLOG | 0.64 | `article_metadata` |
| Nothing matched | OTHER | 0.00 | `no_match` |

> The table shows which **rule** matches, assuming no earlier rule has already returned. Rule order matters.

---

# Why this matters for Developer's Eye

Without classification, the search engine sees everything as just a webpage.

With classification, later we can filter search results by:

- Documentation
- Tutorials
- GitHub repositories
- GitHub/GitLab issues
- Questions and discussions
- Developer events
- Blog articles

And topic tags let us know if a page is about Python, FastAPI, Docker, PostgreSQL, etc.

The best part: this is all deterministic. We don't need an LLM API call for every page we crawl.

### Things to remember

- **First match wins.** Order matters.
- **Confidence scores are heuristics**, not probabilities.
- **Tags and document type are different:** `BLOG` is a type; `python` is a topic.
- **This is classification, not URL authorization.** Host Policy, DNS Policy, Robots Policy, and the Worker handle crawling decisions.
- **It won't recognize everything.** We can add rules later based on real documents instead of guessing hundreds of patterns now.

**Next in our pipeline:** `fingerprint.py` creates a deterministic content hash. Then `processor.py` combines normalization, classification, and fingerprinting into a `ProcessedDocument`.
