# Redirect Policy: What if a website sends our crawler somewhere else?
---
![alt text](image-5.png)
---

We have already built **Host Policy**, **DNS/IP Safety**, **Robots Policy**, and **Politeness Control** for Developer's Eye.

Now imagine our crawler wants to fetch:

```text
https://docs.example.com/old-guide
```

We checked the hostname, verified that the destination IP is safe, checked `robots.txt`, and waited for our polite request slot. Everything looks good.

But after the request, the server responds:

```http
HTTP/1.1 301 Moved Permanently
Location: /new-guide
```

The server is basically saying: **"The page moved. Go to `/new-guide` instead."**

Should we blindly follow that new URL? **No.** That new destination could be malformed, outside our allowed hosts, unsafe, or part of an endless redirect loop.

This is why we made **Redirect Policy**.

---

## 1. First, what is a redirect?

A redirect is an HTTP response telling the client that the requested resource can be found at another URL.

In our GET-only crawler, we recognize these redirect status codes:

| Status | Meaning |
| --- | --- |
| `301` | Permanently moved |
| `302` | Temporarily moved |
| `303` | See another URL |
| `307` | Temporary redirect (normally preserves HTTP method) |
| `308` | Permanent redirect (normally preserves HTTP method) |

The new destination is usually supplied in the **`Location` response header**.

**Important:** `Location` can be a full URL, a relative path, or a scheme-relative URL. We have to resolve it correctly before checking it.

## 2. Where does Redirect Policy fit in our architecture?

```mermaid
flowchart TD
    A[URL Frontier] --> B[Host Allowlist Check]
    B --> C[DNS/IP Safety Check]
    C --> D[Robots Policy]
    D --> E[Politeness Manager]
    E --> F[Safe HTTP Fetcher: GET with redirects disabled]
    F --> G{Response is 301, 302, 303, 307, or 308?}
    G -- No --> H[Handle normal response]
    G -- Yes --> I[RedirectTracker.next_url]
    I --> J{Redirect candidate valid?}
    J -- No --> K[Stop chain and record redirect error]
    J -- Yes --> L[Candidate URL returned to coordinator]
    L --> B
```

**Notice the loop:** every redirect goes through **Host → DNS/IP → Robots → Politeness** again. Passing the first round of checks does not give the next URL permission to be fetched.

The coordinator must use the **IP-pinned safe transport** for each approved destination, rather than relying on an ordinary auto-following client to make security decisions.

---

## 3. What this file is responsible for

Our redirect module only:

1. Recognizes supported redirect status codes.
2. Checks whether URL strings are valid and well formed.
3. Resolves the `Location` header into an absolute URL.
4. Rejects HTTPS-to-HTTP downgrades by default.
5. Detects URLs that have already appeared in the same redirect chain.
6. Limits how many redirects one original request can follow.
7. Tracks the current URL and the chain's history.

**It does not fetch websites, resolve DNS, check robots.txt, approve hostnames, or grant network access.** That remains the coordinator's job.

---

## 4. Our configuration

```python
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
DEFAULT_MAX_REDIRECTS = 5
```

`frozenset` is simply a set that cannot be changed. We use it to keep the allowed redirect status codes fixed.

`DEFAULT_MAX_REDIRECTS = 5` means that, by default, we permit **five redirect hops**, not five total page requests.

Example:

```text
A → B  (hop 1)
B → C  (hop 2)
C → D  (hop 3)
D → E  (hop 4)
E → F  (hop 5)
F → G  (hop 6: rejected)
```

---

## 5. Why all these custom exceptions?

```python
class RedirectPolicyError(ValueError):
    """Base error for a rejected redirect or redirect chain."""

class InvalidRedirectError(RedirectPolicyError):
    """A Location header or destination URL is missing or malformed."""

class RedirectLoopError(RedirectPolicyError):
    """A redirect targets a URL that has already been visited."""

class RedirectLimitError(RedirectPolicyError):
    """A redirect would exceed the configured maximum number of hops."""

class RedirectDowngradeError(RedirectPolicyError):
    """An HTTPS URL redirects to an insecure HTTP URL."""
```

These are **our own exception classes**. They do not do the checking themselves. Other functions detect a problem and `raise` the relevant exception.

| Exception | Scenario |
| --- | --- |
| `RedirectPolicyError` | We called `next_url()` for a non-redirect status such as `200`. |
| `InvalidRedirectError` | The server sent no `Location`, or sent a malformed destination. |
| `RedirectLoopError` | `A → B → A`; we are about to revisit an earlier URL. |
| `RedirectLimitError` | The chain attempts a sixth hop when the maximum is five. |
| `RedirectDowngradeError` | A page at `https://` redirects to `http://`. |

Because they all inherit from `RedirectPolicyError`, we can catch all redirect failures in one place when needed:

```python
try:
    next_destination = tracker.next_url(302, "/new-guide")
except RedirectPolicyError as exc:
    print(f"Redirect rejected: {exc}")
```

---

## 6. Every function and what it does

### 6.1 `is_redirect(status_code)`

```python
def is_redirect(status_code: int) -> bool:
    return status_code in REDIRECT_STATUS_CODES
```

The simplest function in this module. It answers: **"Is this response one of the redirects our GET-only crawler follows?"**

```python
is_redirect(301)  # True
is_redirect(308)  # True
is_redirect(200)  # False
is_redirect(404)  # False
```

### 6.2 `_check_chars(value, name)`

Before we parse a URL or a `Location` header, we check whether the string contains characters we refuse to accept.

It rejects empty values, non-strings, whitespace, backslashes, and control characters such as newline and tab.

Imagine a server returned a header value containing an unexpected newline. We do **not** want a URL parser silently removing it and interpreting a different destination.

```text
"https://example.com/good"       → valid characters
"https://example.com/a b"        → rejected (space)
"https://example.com/a\nb"       → rejected (newline)
""                               → rejected (empty)
```

The leading `_` in `_check_chars` is just Python's convention for an **internal helper**, not a special keyword.

### 6.3 `_check_absolute_http_url(url)`

This checks the **structure** of an absolute URL.

```text
https://docs.example.com:443/guide
  │            │       │     │
Scheme       Host     Port   Path
```

It uses `urlsplit()` to inspect the scheme, hostname, port, and optional username/password.

Examples of rejected inputs:

```text
ftp://example.com/file           Unsupported scheme
example.com/guide                Not an absolute HTTP(S) URL
https://user:pass@example.com    Credentials embedded in URL
https://example.com:abc          Invalid port
https://example.com:0            Port zero
```

This is **syntax validation, not a DNS/IP safety check**. A URL can be syntactically valid while pointing at an internal or forbidden destination.

### 6.4 `validate_redirect_url(url)`

This is our main URL validation function. It brings several helpers together:

```mermaid
flowchart TD
    A[validate_redirect_url: input URL] --> B[_check_chars]
    B --> C[_check_absolute_http_url]
    C --> D[normalize_url]
    D --> E[_check_chars on normalized URL]
    E --> F[_check_absolute_http_url again]
    F --> G[urldefrag: remove fragment]
    G --> H[Return canonical URL]
    B & C & D & E & F -->|Invalid| X[Raise InvalidRedirectError]
```

Example using our URL normalizer:

```python
validate_redirect_url("HTTPS://EXAMPLE.COM:443/docs#setup")
# "https://example.com/docs"
```

Why remove `#setup`? Fragments are used by the browser or client and are not sent in the HTTP request target. They should not fool our redirect-loop detection into thinking the same page is new.

### 6.5 `resolve_redirect(current_url, location)`

The server's `Location` header is not always a complete URL.

Imagine we're currently at:

```text
https://docs.example.com/guides/old
```

Different responses might say:

| `Location` value | Resolved destination |
| --- | --- |
| `/guides/new` | `https://docs.example.com/guides/new` |
| `new` | `https://docs.example.com/guides/new` |
| `https://other.example/docs` | `https://other.example/docs` |
| `//other.example/docs` | `https://other.example/docs` |

The function first validates the current URL and the `Location` string. It rejects unsupported or malformed schemes. Then it uses:

```python
urljoin(current, location)
```

to form a complete URL, and passes that result through `validate_redirect_url()`.

**Result:** a validated **candidate**. Not an approved fetch destination.

### 6.6 `RedirectTracker.__post_init__()`

We use `@dataclass(slots=True)` to generate the ordinary object initialization code for us. `__post_init__()` runs right after the generated `__init__()`.

When we create:

```python
tracker = RedirectTracker(
    start_url="https://docs.example.com/a",
    max_redirects=5,
)
```

`__post_init__()` checks that `max_redirects` is a non-negative integer and that `allow_https_downgrade` is a boolean. It validates the starting URL and prepares the state:

```text
current_url      = "https://docs.example.com/a"
redirect_count   = 0
_visited         = {"https://docs.example.com/a"}
```

Think of `_visited` as a notebook listing every URL this one redirect chain has already reached.

**Create one `RedirectTracker` per original request**, not one global tracker for your entire crawler.

### 6.7 `RedirectTracker.next_url(status_code, location)`

This is our main redirect decision function.

It checks, in order:

1. **Supported status?** Otherwise raise `RedirectPolicyError`.
2. **Already at the hop limit?** Raise `RedirectLimitError`.
3. **Can we resolve and validate the `Location`?** Otherwise raise `InvalidRedirectError`.
4. **HTTPS → HTTP downgrade?** Raise `RedirectDowngradeError`, unless explicitly allowed.
5. **Candidate previously visited?** Raise `RedirectLoopError`.

If everything passes, it performs:

```python
self.redirect_count += 1
self.current_url = candidate
self._visited.add(candidate)
return candidate
```

Notice that `next_url()` **updates the tracker and returns the candidate**, but it still does not fetch anything.

---

## 7. Full execution flowchart

```mermaid
flowchart TD
    A([Create RedirectTracker with start_url]) --> B[__post_init__]
    B --> C{Tracker configuration valid?}
    C -- No --> ERR1[ValueError]
    C -- Yes --> D[validate_redirect_url on start_url]
    D --> E[Set current_url and visited set; count = 0]
    E --> F[Coordinator makes safe GET request]
    F --> G{Response is supported redirect?}
    G -- No --> DONE([Handle normal response])
    G -- Yes --> H[next_url with status and Location]
    H --> I[is_redirect]
    I --> J{Supported status?}
    J -- No --> ERR2[RedirectPolicyError]
    J -- Yes --> K{Redirect count at maximum?}
    K -- Yes --> ERR3[RedirectLimitError]
    K -- No --> L[resolve_redirect]
    L --> M[validate current URL]
    M --> N[_check_chars on Location]
    N --> O[urlsplit Location and validate scheme]
    O --> P{Location well formed?}
    P -- No --> ERR4[InvalidRedirectError]
    P -- Yes --> Q[urljoin current URL with Location]
    Q --> R[validate_redirect_url on candidate]
    R --> S{HTTPS to HTTP forbidden?}
    S -- Yes --> ERR5[RedirectDowngradeError]
    S -- No --> T{Candidate already visited?}
    T -- Yes --> ERR6[RedirectLoopError]
    T -- No --> U[Increment count; update current URL; add to visited]
    U --> V[Return candidate to coordinator]
    V --> W[Recheck allowlist, DNS/IP, robots, politeness]
    W --> X{Approved by all policies?}
    X -- No --> STOP([Stop redirect chain])
    X -- Yes --> F
```

`validate_redirect_url()` itself runs `_check_chars`, `_check_absolute_http_url`, `normalize_url`, the two checks again, and finally `urldefrag`. That internal flow is shown in section 6.4.

---

## 8. Real scenarios

### Scenario A: Normal redirect

```python
tracker = RedirectTracker("https://docs.example.com/old")

print(tracker.next_url(301, "/new"))
# https://docs.example.com/new
```

The redirect passes. The tracker now knows `/old` and `/new`. The coordinator must still check whether `/new` is safe to fetch.

### Scenario B: Redirect loop

```python
tracker = RedirectTracker("https://docs.example.com/a")
tracker.next_url(302, "/b")
tracker.next_url(302, "/a")  # Raises RedirectLoopError
```

We've already visited `/a`, so following it again would repeat the chain.

### Scenario C: Too many hops

```python
tracker = RedirectTracker(
    "https://docs.example.com/a",
    max_redirects=2,
)

tracker.next_url(301, "/b")  # Hop 1
tracker.next_url(302, "/c")  # Hop 2
tracker.next_url(302, "/d")  # Raises RedirectLimitError
```

### Scenario D: HTTPS downgrade

```python
tracker = RedirectTracker("https://docs.example.com/a")
tracker.next_url(302, "http://docs.example.com/b")
# Raises RedirectDowngradeError
```

HTTPS means our connection is encrypted using TLS. This policy rejects a redirect that attempts to downgrade to unencrypted HTTP unless explicitly configured otherwise.

### Scenario E: A syntactically valid but dangerous destination

```http
HTTP/1.1 302 Found
Location: https://127.0.0.1:8443/admin
```

This URL may pass **redirect syntax validation**, but it must **not** automatically be fetched. `127.0.0.1` is a loopback address. Our separate DNS/IP safety policy and IP-pinned transport must prevent unauthorized connections to internal destinations. This is part of defending against **SSRF (Server-Side Request Forgery)**.

---

## 9. How the fetcher should use the tracker

The coordinator follows this sequence for **each** attempted URL:

```text
1. Check host allowlist
2. Check DNS/IP safety
3. Check robots.txt for this host and path
4. Acquire the host's polite request slot
5. Fetch with automatic redirects disabled and safe IP-pinned transport
6. Inspect HTTP response status and Location
7. If redirected, call RedirectTracker.next_url()
8. Take returned candidate back to step 1
9. Otherwise, handle the final response
```

Do not turn on automatic HTTP redirects to make this easier. That would bypass the opportunity to recheck each destination.

Another implementation detail: `next_url()` records a candidate **before** the coordinator approves that candidate. For this design, if the coordinator rejects the candidate, we should **stop the redirect chain**, not reuse the same tracker as if the rejected hop never happened.

---

## 10. What we learned

| Concept | Meaning in Developer's Eye |
| --- | --- |
| HTTP redirect | Server asks the crawler to try a different URL |
| `Location` header | Supplies that new destination |
| `urljoin()` | Combines a relative destination with the current URL |
| URL normalization | Makes equivalent URL strings more consistent |
| `_visited` set | Helps detect loops in one chain |
| Redirect hop limit | Prevents endless chains |
| HTTPS downgrade | Moving from an encrypted HTTPS connection to HTTP |
| SSRF safety | Prevents redirects from becoming unauthorized access to internal services |

**Redirect Policy is a URL validator and redirect-chain tracker, not a fetcher or a safety approval service.**

The flow is:

```text
Response → Recognize redirect → Resolve Location → Validate candidate
         → Check limit / downgrade / loop → Update tracker
         → Return candidate → Re-run all crawler safety policies → Fetch
```

That completes our redirect-policy component. The next integration task is making the fetch coordinator enforce every safety policy on **every hop**, not just the first URL.
