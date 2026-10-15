# Robots Policy. Third step of our crawler safety checks

---
![Robot Policy Overview](intro_robot.png)

---

We already made **Host Policy** and **DNS Policy**. Now we are making **Robots Policy**.

Imagine our crawler finds this URL:

`https://example.com/private/account`

Host Policy says the domain is on our approved list. DNS Policy says its IP address is safe. **But does the website actually allow a crawler to visit this page?**

That's what Robots Policy checks.

The website can publish crawling instructions at:

`https://example.com/robots.txt`

For example:

```text
User-agent: DevelopersEyeBot
Allow: /docs/
Disallow: /private/
Disallow: /admin/
```

Here, our bot can crawl `/docs/python`, but it should not crawl `/private/account` or `/admin/dashboard`.

**Important:** `robots.txt` is a crawling instruction, **not** a security or authentication system. An allowed URL can still require authentication, and a disallowed URL does not become accessible just because someone ignores the file.

---

## 1. What are we building?

We made `robots_policy.py` to answer one question:

> **Should Developer's Eye crawl this URL right now?**

We return **three** possible decisions, not just `True` or `False`:

| Decision | Meaning | What our crawler should do |
| --- | --- | --- |
| `ALLOW` | Robots rules permit the requested URL, or our policy treats the robots file as unavailable | Continue to the next checks / page fetch |
| `DENY` | The URL is disallowed, or our conservative policy blocks the robots endpoint | Do not crawl this URL |
| `DEFER` | We could not safely make a decision right now | Retry later through the scheduler |

### Overall flow

```text
URL FRONTIER
    |
    v
HOST POLICY
Is this host approved?
    |
    v
ROBOTS POLICY
    |
    +--> Extract origin: https://example.com
    |
    +--> Look in PostgreSQL robots_cache
    |        |
    |        +--> Fresh cache? Use it.
    |        |
    |        +--> No cache / expired?
    |                  |
    |                  v
    |            Safely fetch /robots.txt
    |            (DNS/IP checks happen in the injected fetcher)
    |                  |
    |                  v
    |            Cache qualifying responses
    |
    v
Evaluate status + robots rules
    |
    +--> ALLOW --> Crawler may proceed to a safely validated page fetch
    |
    +--> DENY  --> Skip the URL
    |
    +--> DEFER --> Schedule a retry
```

**One important detail:** This module does **not** fetch the page or open network connections itself. The DNS protections have to be enforced by the safe fetcher passed into the module, and they still apply to the actual page fetch.

---

## 2. Constants: the configuration

```python
USER_AGENT = "DevelopersEyeBot"
DEFAULT_CACHE_TTL_SECONDS = 86_400
MISSING_CACHE_TTL_SECONDS = 3_600
DEFAULT_DEFER_SECONDS = 300
MAX_ROBOTS_BYTES = 512_000
```

| Constant | Why we need it |
| --- | --- |
| `USER_AGENT` | The name our crawler uses while checking robots rules |
| `DEFAULT_CACHE_TTL_SECONDS` | Keep a successful `robots.txt` response in the database for **24 hours** |
| `MISSING_CACHE_TTL_SECONDS` | Keep selected missing/rejected robots responses for **1 hour** |
| `DEFAULT_DEFER_SECONDS` | Suggest trying again after **5 minutes** |
| `MAX_ROBOTS_BYTES` | Reject a downloaded robots body larger than **500 KiB** |

**Scenario:** We have 20,000 URLs from `example.com`. We don't want 20,000 requests to `/robots.txt`. We fetch it, save it, and reuse the same rules until the cache expires.

---

## 3. The three dataclasses / types

### `RobotsDecision`

```python
class RobotsDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"
```

`StrEnum` gives us a fixed set of readable string decisions. It prevents random results such as `"maybe"` from becoming part of our policy.

### `RobotsPolicyResult`

```python
@dataclass(frozen=True, slots=True)
class RobotsPolicyResult:
    decision: RobotsDecision
    reason: str
    origin: str
    retry_after_seconds: int | None = None
```

This is what our policy returns to the scheduler or crawler.

Example:

```python
RobotsPolicyResult(
    decision=RobotsDecision.DENY,
    reason="Robots rules disallow URL",
    origin="https://example.com",
    retry_after_seconds=None,
)
```

- `decision`: Allow, deny, or defer.
- `reason`: Why we made that decision.
- `origin`: Which website/origin the rule came from.
- `retry_after_seconds`: A suggested delay, mainly for `DEFER`.

`frozen=True` means we cannot accidentally modify the result later. `slots=True` makes instances more memory-efficient.

### `RobotsFetchResponse` and `RobotsFetcher`

```python
@dataclass(frozen=True, slots=True)
class RobotsFetchResponse:
    status_code: int
    body: str = ""
    retry_after_seconds: int | None = None

RobotsFetcher = Callable[[str], Awaitable[RobotsFetchResponse]]
```

This defines the **interface** of the fetcher our module expects: give it a robots URL, and it asynchronously returns an HTTP status, body, and optional retry delay.

It does **not** implement a safe HTTP fetcher for us. We still need to wire one in.

`RobotsFetchError` is the specific exception the injected fetcher should raise when a network retrieval fails.

---

## 4. `get_robots_origin()` and `get_robots_url()`

### `get_robots_origin(url)`

We only want the URL's **origin**: scheme + hostname + optional port.

```python
origin = get_robots_origin(
    "https://EXAMPLE.com/docs/python?lang=en#intro"
)
print(origin)
# https://example.com
```

The function first calls `normalize_url()`, then uses `urlsplit()` and `urlunsplit()` to remove the page path, query, and fragment.

**Why?** `/robots.txt` belongs at the origin root, not inside every page's folder. Also, `http://example.com` and `https://example.com` are different origins.

### `get_robots_url(url)`

```python
print(get_robots_url("https://example.com/docs/python"))
# https://example.com/robots.txt
```

All pages on the **same origin** use the same robots URL.

---

## 5. `parse_robots()` and `is_crawl_allowed()`

This is where we actually read the rules.

### `parse_robots(raw_content)`

```python
def parse_robots(raw_content: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse(raw_content.splitlines())
    return parser
```

Python already gives us `RobotFileParser`, so we don't have to write a basic robots parser from scratch.

We pass in the **text** of a robots file; this function does not download it.

### `is_crawl_allowed(raw_content, url, user_agent)`

```python
rules = """
User-agent: DevelopersEyeBot
Disallow: /private/
Allow: /docs/
"""

print(is_crawl_allowed(rules, "https://example.com/docs/python"))
# True

print(is_crawl_allowed(rules, "https://example.com/private/account"))
# False
```

Behind the scenes, we normalize the page URL and call:

```python
parser.can_fetch(user_agent, normalized_url)
```

So the `DevelopersEyeBot` rules are checked against the URL we want to crawl.

**Limitation:** `RobotFileParser` is a convenient standard-library parser, not a guarantee of complete RFC 9309 behavior for every unusual rule. We should test any edge cases that matter to our crawler.

---

## 6. Why did we make a `robots_cache` database table?

Imagine our source registry contains MDN and Python docs, and the crawler discovers thousands of links from each source.

Without cache:

```text
Page 1 --> fetch robots.txt
Page 2 --> fetch robots.txt
Page 3 --> fetch robots.txt
... repeated requests
```

With cache:

```text
Page 1 --> fetch robots.txt --> save in PostgreSQL
Page 2 --> read cached rules
Page 3 --> read cached rules
... reuse until expiration
```

Our `RobotsCache` model stores the origin, downloaded content (when applicable), HTTP status, fetch time, and expiration time.

### `get_cached_robots(session, origin)`

This uses SQLAlchemy `select()` to find a row only if:

```python
RobotsCache.origin == origin
RobotsCache.expires_at > datetime.now(timezone.utc)
```

If we have a fresh row, return it. Otherwise return `None`.

The `populate_existing=True` query option requests fresh values from the database instead of relying on potentially stale ORM attributes already loaded into the session.

### `save_robots_cache(...)`

We use PostgreSQL **UPSERT**:

```python
stmt = pg_insert(RobotsCache).values(**values)
stmt = stmt.on_conflict_do_update(
    index_elements=[RobotsCache.origin],
    set_={...},
)
```

- No row for that origin? **INSERT** a new one.
- Row already exists? **UPDATE** it.

This prevents duplicate rows under the origin's unique/primary-key constraint.

**Important:** `await session.execute(stmt)` does not commit. The caller must commit or roll back the transaction.

### What gets cached?

| Response | Cached? | TTL |
| --- | --- | --- |
| `200` with a valid body within size limit | Yes | 24 hours by default |
| `401`, `403`, `404`, `410`, `204`, and other 4xx except `408`/`429` | Yes | 1 hour |
| `408` / `429` | No | Retry instead |
| `500–599` | No | Retry instead |
| Unhandled `3xx` / other responses | No | Defer |
| Fetch error or oversized/invalid `200` body | No | Defer |

The cache contains the **HTTP response state/rules**, not a permanent ALLOW/DENY for every individual page. Every page URL is checked against the applicable cached rules.

---

## 7. `_decision_for_status()`: what do we do with HTTP responses?

A successful robots download is only one possibility. Servers can respond with errors, missing files, or rate limits.

| HTTP response | Our decision | Explanation |
| --- | --- | --- |
| `200 OK` | `ALLOW` or `DENY` | Check `RobotFileParser.can_fetch()` |
| `401 Unauthorized` / `403 Forbidden` | `DENY` | Our deliberately conservative policy |
| `404 Not Found` / `410 Gone` | `ALLOW` | No robots restrictions under our policy |
| Other `4xx` except `408` / `429` | `ALLOW` | Treat robots file as unavailable |
| `204 No Content` | `ALLOW` | Explicitly treated as no restrictions |
| `408 Request Timeout` | `DEFER` | Temporary problem |
| `429 Too Many Requests` | `DEFER` | Rate limited |
| `500–599` | `DEFER` | Server failure |
| Unhandled `2xx` / `3xx` | `DEFER` | We can't safely interpret that response |

Our `401` and `403` behavior is **stricter** than RFC 9309's general treatment of unavailable 4xx robots files. That is a project decision, not a universal robots requirement.

### Scenario A: robots.txt allows docs

```text
Page: https://example.com/docs/python
HTTP: 200
Robots: Allow: /docs/
Result: ALLOW
```

Now the crawler may continue with its normal page-fetch safety checks.

### Scenario B: robots.txt denies private pages

```text
Page: https://example.com/private/account
HTTP: 200
Robots: Disallow: /private/
Result: DENY
```

We **skip** that URL, even if Host Policy and DNS Policy say it is technically safe to connect.

### Scenario C: no robots.txt

```text
Robots URL: https://example.com/robots.txt
HTTP: 404
Result: ALLOW
```

Under this module's rules, there are no robots restrictions to apply. That does **not** bypass our host allowlist or DNS security.

### Scenario D: website rate-limits our crawler

```text
Robots URL: https://example.com/robots.txt
HTTP: 429
Retry-After: 600
Result: DEFER, retry_after_seconds=600
```

We do not decide the website permanently blocked us. We ask the scheduler to retry later.

### Scenario E: website's robots endpoint is broken

```text
HTTP: 503 Service Unavailable
Result: DEFER, retry_after_seconds=300
```

We don't guess that crawling is allowed when robots rules cannot be retrieved.

---

## 8. `evaluate_robots_policy()`: the main function

This is the function other crawler components will call:

```python
result = await evaluate_robots_policy(
    session=session,
    url="https://example.com/docs/python",
    fetcher=safe_fetcher,
)
```

Here's what it does, in order:

1. **Validate inputs.** Cache TTL must be positive, and the user-agent cannot be empty.
2. **Find the origin.** For example, `https://example.com`.
3. **Check PostgreSQL.** If a fresh cached robots response exists, evaluate it and return. No HTTP request.
4. **Build `/robots.txt`.** For example, `https://example.com/robots.txt`.
5. **Call the injected fetcher.** It must enforce our connection and redirect safety rules.
6. **Handle errors.** A `RobotsFetchError` becomes `DEFER` with a default 300-second retry.
7. **Validate HTTP 200 content.** Require a string body and at most 512,000 UTF-8 bytes.
8. **Save cacheable responses.** Successful and selected unavailable/denied responses go into PostgreSQL.
9. **Choose a decision.** Pass the status and rules to `_decision_for_status()`.
10. **Apply an optional retry delay.** If the result is `DEFER` and the response provides a positive `retry_after_seconds`, use that instead of the default.

At the end, the scheduler or frontier worker receives a `RobotsPolicyResult` object and decides what to do next.

### Tiny test of the parser (no database or network needed)

```python
rules = """
User-agent: DevelopersEyeBot
Disallow: /private/
Allow: /docs/
"""

assert is_crawl_allowed(rules, "https://example.com/docs/python") is True
assert is_crawl_allowed(rules, "https://example.com/private/account") is False
assert get_robots_url("https://example.com/docs/python") == "https://example.com/robots.txt"
```

To test the **complete** `evaluate_robots_policy()` flow, we also need an `AsyncSession` connected to our test database and an injected fetcher (or controlled fake fetcher).

---

## 9. What this file does NOT do

The `robots_policy.py` file is a **policy evaluator**, not an entire crawler.

It does **not**:

- Make HTTP requests by itself. The caller supplies `RobotsFetcher`.
- Guarantee DNS/IP security automatically. The injected fetcher must enforce it, including redirect destinations and IP pinning.
- Fetch the target webpage after `ALLOW`. Our async fetch worker will do that.
- Commit database transactions. The caller owns commit/rollback.
- Schedule `DEFER` retries. The scheduler/frontier must act on `retry_after_seconds`.
- Enforce crawl-delay, per-host request budgets, or concurrency limits. Those belong to scheduler/politeness logic.
- Prevent duplicate simultaneous robots downloads across workers. An UPSERT prevents duplicate **rows**, not duplicate **requests**.

**Two implementation cautions:** The code catches `RobotsFetchError`, not arbitrary `httpx` errors. Our safe fetcher should translate its expected network failures into that exception. And the body-size check in this module happens **after** a body is returned, so the fetcher must also enforce a size limit while downloading.

---

## 10. How it fits Developer's Eye

Our crawler's safety and crawling decision is split across modules:

| Module | Main question |
| --- | --- |
| `host_policy.py` | Is this host approved by our source registry? |
| `dns_policy.py` | Are its resolved connection destinations safe? |
| `robots_policy.py` | Do the website's published crawling rules permit this URL? |
| Scheduler / politeness | When and how frequently should we crawl it? |
| Async fetcher | Can we make the actual HTTP request safely? |

**Example:** A URL can pass Host Policy and DNS Policy but fail Robots Policy. Another URL can pass all three checks but still have to wait because of a per-host rate limit.

So we keep these responsibilities separate instead of putting every rule inside one giant fetching function.

**Final flow:** `Approved host → safe DNS/IP connection for robots → robots cache or safe fetch → ALLOW / DENY / DEFER → scheduler / safely validated page fetch`.
