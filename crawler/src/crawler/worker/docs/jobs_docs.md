# Worker Jobs — Developer's Eye

> **Developer's Eye — Crawler Worker**  
> **Based on:** the shared worker job/helper and `_finalize()` code  
> **Input:** claimed crawl target + its lease, with fetch/parse/process results  
> **Output:** `JobResult`, updated crawl target/attempt, saved documents, and enqueued links (when applicable)

---

# Step by step

So we have already made our source registry, URL Frontier, scheduler, Policy Coordinator, HTTPX fetcher, HTML parser and content processor.

We tested the main pipeline on 5 real Python documentation pages. It fetched 5 pages, processed 5 documents and **discovered 440 links**. But it didn't actually crawl those 440 links, and it didn't write the documents into PostgreSQL.

Now comes the **Worker Job**.

Why do we need it? Because having 10 separate modules is not enough. Somebody has to take a *claimed target*, run the crawler pipeline, decide what happened, and safely tell PostgreSQL the result.

```text
Source Registry / Seed Discovery
             |
             v
       URL Frontier
             |
             v
 Scheduler: claim_targets()
             |
       leased target
             |
             v
          Worker
             |
      PolicyCoordinator
             |
         HTTPX Fetcher
             |
       FetchResult
             |
       HTML Parser
             |
        ParseResult
             |
     Content Processor
             |
      ProcessingResult
             |
    Worker helper functions
      /              \
 robots/index rules   discovered link candidates
      \              /
             |
         _finalize()
             |
    Check lease ownership
             |
   PostgreSQL transaction
     /       |        \
 Target   Document    Crawl attempt
 update   upsert      finish
             |
      enqueue links
             |
          JobResult
```

**Important:** The shared code includes helper functions and `_finalize()`. The actual caller that claims a target, calls `coordinator.fetch()`, invokes `parse()`/`process()`, starts an attempt, and then calls `_finalize()` was **not included** in the excerpt. The diagram shows the intended overall lifecycle, not proof that the whole runner is implemented.

Also, unlike our earlier live dry run, **`_finalize()` performs real database writes and its `session.begin()` block commits on success.** Don't call it while expecting zero database changes.

---

# 1. Why a Worker Job?

Imagine our scheduler claimed 3 URLs:

```text
Target #10  docs.python.org/3/tutorial/
Target #11  docs.python.org/3/library/
Target #12  docs.python.org/3/reference/
```

The scheduler's job is to say: **these URLs are ready and leased to a worker**.

It is *not* saying the pages have been crawled.

Our Worker has to figure out:

- Was the URL permitted by host, DNS, robots and redirect policies?
- Did the server return HTML or an error?
- Did parsing work?
- Did the processor accept or skip the document?
- Which discovered links are eligible for our Frontier?
- Does the Worker still own the target's lease?
- Do we complete, retry, block or disable the target?
- Which results can we safely save?

This is why the Worker Job is an **orchestrator**, not another parser or fetcher.

---

# 2. Files and components we're connecting

The shared excerpt imports these components:

| Component | What it does |
|---|---|
| `CrawlTarget` | A scheduled URL in PostgreSQL |
| `Source` | The registered source that owns a target |
| `Document` | A processed page stored for search |
| `CrawlTargetCreate` | Schema for a new discovered target |
| `PolicyCoordinator` | Enforces host, DNS, robots, redirect and politeness rules |
| `HTTPXHopFetcher` | Safely downloads one HTTP response hop |
| `parse()` | Turns HTML bytes into `ParseResult` |
| `process()` | Normalizes, classifies and fingerprints documents |
| `enqueue_targets()` | Inserts eligible URLs into the Frontier |
| `complete_target()` | Transitions a successfully processed target |
| `fail_target()` | Schedules failed/deferred work for retry |
| `finish_attempt()` | Closes one crawl-attempt record |
| `upsert_document()` | Inserts or updates a processed document |
| `_finalize()` | Makes sure all database changes belong to a valid lease |

**Import check:** Some lines in the pasted code use `crawler.src.crawler.worker...`. With our `src` layout, imports should start with `crawler.worker...`, but the exact remaining path depends on your actual `jobs.py`/`jobs/` layout. And the imported `crawler.writer.*` files must exist before this code can run.

---

# 3. `_header()` — read HTTP headers correctly

```python
def _header(headers: dict[str, str], name: str) -> str | None:
    return next(
        (value for key, value in headers.items()
         if key.casefold() == name.casefold()),
        None,
    )
```

HTTP headers are case-insensitive. Python dictionary keys aren't.

```python
headers = {"X-Robots-Tag": "noindex"}

headers.get("x-robots-tag")             # None
_header(headers, "x-robots-tag")        # "noindex"
```

- `.items()` gives each `(key, value)` pair.
- `.casefold()` compares without case differences.
- `next(..., None)` returns the first matching value or `None`.
- `str | None` means the function may return a string or `None`.

**Why we needed this?** Because the same server can send `X-Robots-Tag`, `x-robots-tag`, or `X-ROBOTS-TAG`. We shouldn't change behavior based on capitalization.

---

# 4. `_x_robots_directives()` — do they allow us to index?

This checks **HTTP `X-Robots-Tag`**, which is different from the site's `robots.txt`.

```http
X-Robots-Tag: noindex, nofollow
```

The supported directives in this MVP helper are:

| Directive | Meaning for our crawler |
|---|---|
| `noindex` | Do not keep this page in the search index |
| `nofollow` | Do not enqueue links discovered on this page |
| `none` | Treat as both `noindex` and `nofollow` |

The function starts with:

```python
raw = _header(headers, "x-robots-tag")
if not raw:
    return ()
```

Then it works out the crawler's name:

```python
own_bot = USER_AGENT.split("/", 1)[0].casefold()
```

If `USER_AGENT = "DevelopersEyeBot/1.0"`, `own_bot` becomes `"developseyebot"`.

### Why do we check the agent name?

Imagine a server responds:

```http
X-Robots-Tag: Googlebot: noindex
```

That directive is scoped to Googlebot. We shouldn't automatically treat it as an instruction for Developer's Eye.

But:

```http
X-Robots-Tag: DevelopersEyeBot: noindex, nofollow
```

is intended for our crawler.

The main loop:

```python
scope = None
found = []

for clause in raw.split(","):
    clause = clause.strip().casefold()
    if not clause:
        continue

    match = _AGENT_SCOPE.fullmatch(clause)
    if match:
        scope, clause = match.groups()

    if scope not in (None, own_bot, "*"):
        continue

    for directive in _DIRECTIVE_SPLIT.split(clause):
        if directive in {"noindex", "nofollow", "none"}:
            found.append(directive)

return tuple(dict.fromkeys(found))
```

Here:

- `_AGENT_SCOPE` is a compiled regex for `bot-name: directives`.
- `.fullmatch()` checks the whole clause.
- `.groups()` returns the captured bot name and directive text.
- `_DIRECTIVE_SPLIT` splits comma/semicolon/whitespace-separated tokens.
- `continue` skips clauses scoped to another bot.
- `dict.fromkeys(found)` removes repeated directives while preserving their order.
- `tuple(...)` creates an immutable output sequence.

**Limitation:** This is an MVP parser. Scope carry-over, repeated HTTP headers and all possible header syntax need more tests before production use. In particular, splitting on commas before interpreting every scope may not perfectly represent the server's intent.

---

# 5. `_add_x_robots()` — combine HTTP and HTML robots directives

A page can provide robots instructions in two places:

```html
<meta name="robots" content="nofollow">
```

and:

```http
X-Robots-Tag: noindex
```

The parser already extracts the HTML meta directives. This helper adds the applicable HTTP directives to each parsed document.

```python
directives = _x_robots_directives(headers)
if not directives:
    return parsed
```

Then, for each document:

```python
metadata = dict(document.metadata)
existing = metadata.get("robots_directives", ())
```

`dict(...)` gives us a new metadata dictionary. We aren't directly replacing the original parsed document's metadata.

If `existing` is a single string, the code converts it to a tuple. If it's an unsupported type, it ignores it.

Then:

```python
metadata["robots_directives"] = [
    *[value for value in existing if isinstance(value, str)],
    *directives,
]

updated.append(replace(document, metadata=metadata))
return replace(parsed, documents=tuple(updated))
```

The `*` unpacks items from an iterable.

**Scenario:** HTML says `nofollow`, HTTP says `noindex`.

```text
Before: ["nofollow"]
After:  ["nofollow", "noindex"]
```

Now the downstream processor knows **don't index**, and our link-discovery helper knows **don't follow**.

`dataclasses.replace()` creates a new dataclass instance rather than mutating the original `ParsedDocument`/`ParseResult` directly.

---

# 6. `_page_nofollow()` — should we follow this page's links?

```python
def _page_nofollow(parsed: ParseResult) -> bool:
```

This checks the document's combined `robots_directives` metadata.

The main part is a set comprehension:

```python
tokens = {
    directive
    for value in raw if isinstance(value, str)
    for directive in _DIRECTIVE_SPLIT.split(value.casefold())
}

if tokens & {"nofollow", "none"}:
    return True
```

`&` means **set intersection**.

```python
{"noindex", "nofollow"} & {"nofollow", "none"}
# {"nofollow"}
```

Because the intersection isn't empty, the result is `True`.

### Three different cases

**Case A: `noindex` only.** Don't index this page, but eligible links may still be followed.

**Case B: `nofollow` only.** The page itself may be indexed, but we don't enqueue its links.

**Case C: `none`.** Don't index the page and don't enqueue its links.

This helper handles **page-wide** instructions. The next function also checks `rel="nofollow"` on individual links.

---

# 7. `_create_discovered_targets()` — from discovered links to Frontier candidates

This is the bridge between our **HTML Parser** and the **URL Frontier**.

Remember our test: 5 pages produced 440 **discovered links**, not 440 fetched pages.

Now we want to decide which of those links can become future crawl targets.

```python
def _create_discovered_targets(
    parsed: ParseResult,
    *,
    target_id: int,
    source_id: int,
    allowed_hosts: tuple[str, ...],
    max_links: int,
) -> list[CrawlTargetCreate]:
```

The standalone `*` forces subsequent arguments to be passed by keyword. This makes calls easier to read and prevents mixing up `source_id`, `target_id`, and the link budget.

### The actual checks

```text
DiscoveredLink
      |
      v
Page-wide nofollow? ---- yes ---> stop, return []
      |
      no
      v
Individual link nofollow? -- yes --> skip link
      |
      no
      v
normalize_url()
      |
      v
Invalid URL? -------------- yes --> skip link
      |
      no
      v
Already seen? ------------- yes --> skip link
      |
      no
      v
Host allowed? ------------- no ---> skip link
      |
      yes
      v
Create CrawlTargetCreate
      |
      v
Reached max_links? ------- yes --> stop
```

```python
output: list[CrawlTargetCreate] = []
seen: set[str] = set()
```

`output` holds our candidates. `seen` avoids duplicate normalized URLs **within this one batch**.

```python
for link in parsed.discovered_links:
    if link.nofollow:
        continue
```

For instance:

```html
<a href="/tutorial/" rel="nofollow">Tutorial</a>
```

That link is skipped.

```python
try:
    normalized = normalize_url(link.url)
except (ValueError, TypeError):
    continue
```

Malformed URLs don't crash the whole job.

```python
if normalized in seen or not is_allowed_host(
    normalized, list(allowed_hosts)
):
    continue
```

If the source only allows `docs.python.org`, a GitHub URL found on the page is **not** automatically added under the Python docs source.

Finally:

```python
seen.add(normalized)
output.append(CrawlTargetCreate(
    source_id=source_id,
    fetch_url=normalized,
    normalized_url=normalized,
    kind="page",
    discovered_from_id=target_id,
))

if len(output) >= max_links:
    break
```

**Why `discovered_from_id`?** If Target #10 discovers Target #23, the new target can record where it came from. That's useful for tracing crawling paths.

**Important:** Creating `CrawlTargetCreate` objects does not save anything. `_finalize()` later calls `enqueue_targets(session, targets)` to write eligible candidates.

**Limitations:** `max_links` should be validated as a positive integer; currently zero can still allow one candidate. `seen` is not database-wide deduplication. Host approval here doesn't replace the Policy Coordinator's per-request safety checks.

---

# 8. `_noindex_urls()` — what if a page changes its mind?

Imagine yesterday we indexed:

```text
https://example.com/tutorial
```

Today the webpage returns:

```html
<meta name="robots" content="noindex">
```

It isn't enough to skip saving the new content. We may also need to remove the **old searchable copy**.

The function starts with:

```python
rejected = {
    s.url for s in processed.skipped
    if s.reason == SkipReason.NOINDEX
}
```

So it only selects documents that the content processor rejected specifically because of `noindex`.

Then:

```python
for document in parsed.documents:
    if document.url not in rejected:
        continue

    normalized = normalize_document(document)
    urls.update({normalized.url, normalized.canonical_url})
```

It collects the fetched URL and its accepted canonical identity.

Why two URLs?

```text
Fetched URL:   https://example.com/tutorial?ref=nav
Canonical URL: https://example.com/tutorial
```

An existing database record might be stored under the canonical identity.

Later the finalizer deletes matching `Document` rows.

**Important correctness concern:** The comparison uses the raw `document.url` but the skipped URL may already be normalized. Those two strings can differ. Also, a canonical hint should not be allowed to delete an unrelated document without verifying ownership/identity. This cleanup needs tests before using it against important data.

---

# 9. `_finalize()` — the real heart of this code

So we have downloaded the page, parsed it, processed it, and prepared some new link candidates.

Are we allowed to save them immediately?

**No. The Worker may have lost its lease while fetching.**

That's exactly why we need `_finalize()`.

```python
async def _finalize(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    target_id: int,
    source_id: int,
    expected_lease_until: datetime,
    attempt_id: int,
    action: TargetAction,
    outcome: JobOutcome,
    message: str,
    http_status: int | None,
    body_bytes: int,
    retry_after_seconds: float | None,
    interval_seconds: int,
    parsed: ParseResult | None,
    processed: ProcessingResult | None,
    targets: list[CrawlTargetCreate],
    elapsed: float,
) -> JobResult:
```

### What all these inputs mean

| Argument | Meaning |
|---|---|
| `session_factory` | Opens a new async database session |
| `target_id` | Which Frontier target finished |
| `source_id` | Which Source owns the target |
| `expected_lease_until` | The **actual lease timestamp from the claim**, not a newly calculated one |
| `attempt_id` | ID of this exact crawl attempt |
| `action` | What should happen to the target: complete/retry/block/disable |
| `outcome` | What happened during this crawl attempt |
| `message` | Reason for the outcome |
| `http_status` | HTTP response code, if available |
| `body_bytes` | Number of downloaded bytes |
| `retry_after_seconds` | Suggested delay before retrying |
| `interval_seconds` | Normal recrawl interval after success |
| `parsed` | Parser's documents and discovered links |
| `processed` | Accepted and skipped processed documents |
| `targets` | In-scope discovered link candidates |
| `elapsed` | Duration to report |

### Why does it accept both `action` and `outcome`?

Because they aren't the same thing.

Example:

```text
HTTP 503
Outcome: failed
Action: retry
```

Or:

```text
robots.txt disallows URL
Outcome: blocked
Action: block
```

The outcome describes what happened; the action says how the Frontier should change.

---

# 10. Open a new transaction

```python
async with session_factory() as session:
    async with session.begin():
```

We don't want to keep a PostgreSQL transaction open during slow network fetching. Fetch and processing should happen **before** entering this function.

But once we have the results, all related database changes should succeed together.

`session.begin()` commits on a normal exit and rolls back when an exception escapes the block. An early `return` without an exception still exits normally and can commit changes already made in the transaction.

---

# 11. `SELECT ... FOR UPDATE` — lock the target

```python
row = await session.scalar(
    select(CrawlTarget)
    .where(CrawlTarget.id == target_id)
    .with_for_update()
)
```

Conceptually:

```sql
SELECT *
FROM crawl_target
WHERE id = 42
FOR UPDATE;
```

Why the lock?

Imagine Worker A is finishing Target #42 while Worker B is trying to update that same database row.

`FOR UPDATE` locks the selected row for this transaction, so conflicting row updates can't proceed at the same time.

This is **row-level locking**. We're not locking the entire table.

---

# 12. Compare the lease against database time

```python
database_now = await session.scalar(
    select(func.clock_timestamp())
)
```

`clock_timestamp()` gets the database server's actual current time. That's preferable to trusting a Worker VM's local clock for lease expiration checks.

Then:

```python
active = (
    row is not None
    and row.source_id == source_id
    and row.state == "leased"
    and row.lease_until == expected_lease_until
    and row.lease_until is not None
    and row.lease_until > database_now
)
```

Everything must be true:

1. The target exists.
2. It belongs to our source.
3. Its state is currently `leased`.
4. Its lease timestamp matches the one we originally claimed.
5. It has a lease timestamp.
6. That lease hasn't expired.

### Scenario: Two workers, one URL

```text
12:00 — Worker A claims Target #42; lease ends 12:05
12:01 — Worker A starts slow HTTP request
12:05 — Lease expires
12:06 — Scheduler reclaims Target #42 for Worker B
12:07 — Worker A finishes its HTTP request
12:07 — Worker A tries to save its result
```

Worker A's `expected_lease_until` is `12:05`. PostgreSQL now records Worker B's lease. The equality check fails.

**Worker A must discard its stale result.** Otherwise an old Worker could overwrite the newer one.

This is one of the most important distributed-crawler safety rules.

A dedicated unique lease token or generation number would be even stronger than timestamp equality in a future version.

---

# 13. What if the source was disabled while crawling?

```python
if active:
    enabled = await session.scalar(
        select(Source.is_enabled)
        .where(Source.id == source_id)
    )

    if not enabled:
        action = "disable"
        outcome = "disabled"
        message = "Source was disabled while job was running"
        parsed = None
        processed = None
        targets = []
```

Imagine we turned off the Python docs Source in our admin dashboard while a Worker was fetching a page.

The HTTP request may have finished, but the source is no longer enabled.

This code switches to a disable action and clears the content/link outputs so the finalizer won't write documents for it.

---

# 14. What happens if the lease is stale?

```python
if not active:
    await finish_attempt(
        session,
        attempt_id,
        "failed",
        http_status=http_status,
        bytes_received=body_bytes,
        error_message="Lease lost or expired; discarded stale crawl result",
    )
    return JobResult(
        target_id=target_id,
        attempt_id=attempt_id,
        outcome="stale",
        http_status=http_status,
        message="Lease expired or was reassigned",
        duration_seconds=elapsed,
    )
```

Notice that we do **not** upsert the document and we do **not** enqueue new links here.

But we still try to close the old attempt record so history can say what happened.

**Check before production:** `finish_attempt()` should prove this attempt belongs to the correct target/worker. The early-return branch also doesn't check its result in the pasted code.

---

# 15. Four target actions

## Case A: `complete`

```python
transitioned = await complete_target(
    session, target_id,
    expected_lease_until, interval_seconds,
)
```

The job succeeded. The repository transitions its schedule so it can be recrawled later according to `interval_seconds`.

`86400` seconds = one day.

## Case B: `retry`

```python
transitioned = await fail_target(
    session, target_id, expected_lease_until,
)
```

The job didn't finish successfully but may work later. The scheduler's retry policy determines the next eligible time.

Examples: timeout, temporary DNS issue, HTTP 503, or HTTP 429.

## Case C: `block`

The code conditionally updates the target to:

```python
state="blocked"
lease_until=None
```

Example: disallowed by crawl policy.

## Case D: `disable`

Same conditional-update pattern, but:

```python
state="disabled"
lease_until=None
```

Example: its Source was disabled while the job was running.

The block/disable path also requires the target to be leased to the expected lease and not already expired.

**Small risk:** In the shown `else` branch, any unknown `action` would fall through to `disabled`. Explicitly validating allowed action values would be safer.

---

# 16. `Retry-After` — don't attack a struggling server

Sometimes a server responds:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 120
```

That means the crawler should not retry immediately.

Your code does:

```python
wait = max(
    0,
    min(int(retry_after_seconds), _RETRY_AFTER_CAP_SECONDS),
)
```

If the cap is `86400`, the computed value is limited to 24 hours.

Then:

```python
next_fetch_at = func.greatest(
    CrawlTarget.next_fetch_at,
    func.clock_timestamp() + func.make_interval(
        0, 0, 0, 0, 0, 0, wait
    ),
)
```

- `func.make_interval(...)` creates a PostgreSQL time interval (the last positional argument is seconds).
- `clock_timestamp() + interval` calculates the requested retry time.
- `greatest(existing_time, requested_time)` uses the later of the two times.

So the new restriction doesn't accidentally shorten an already later scheduled retry.

**Review:** If a server asks us to wait *longer than 24 hours*, capping the wait to 24 hours can cause us to retry too early. For a respectful crawler, preserve longer server-requested restrictions or explicitly suspend the source.

---

# 17. Conditional updates and `RETURNING`

The block/disable branch uses SQLAlchemy roughly like this:

```python
transitioned = await session.scalar(
    update(CrawlTarget)
    .where(
        CrawlTarget.id == target_id,
        CrawlTarget.state == "leased",
        CrawlTarget.lease_until == expected_lease_until,
        CrawlTarget.lease_until > func.clock_timestamp(),
    )
    .values(
        state="blocked" if action == "block" else "disabled",
        lease_until=None,
    )
    .returning(CrawlTarget.id)
) is not None
```

`.where(...)` makes the update conditional. If another worker owns the row, the update should affect zero rows.

`.returning(CrawlTarget.id)` asks PostgreSQL to return the ID of the row it actually changed.

`is not None` turns that result into `True` or `False`.

The code checks `transitioned` before persisting the crawl output. Failed transition = stale result, not permission to save anyway.

---

# 18. Successful finish: delete noindex, upsert docs, enqueue URLs

This section only runs when:

```python
if action == "complete" and parsed is not None and processed is not None:
```

### Step A: Remove records newly marked noindex

```python
noindex = _noindex_urls(parsed, processed)

if noindex:
    await session.execute(
        delete(Document).where(
            Document.canonical_url.in_(noindex)
        )
    )
```

`.in_(noindex)` is SQL's `IN (...)` check.

This can remove an older indexed copy of a page that now asks not to be indexed. But review identity/ownership checks before deploying this deletion logic.

### Step B: Save accepted documents

```python
for document in processed.documents:
    await upsert_document(
        session, document,
        source_id=source_id,
        crawl_target_id=target_id,
    )
    documents_saved += 1
```

An **upsert** inserts or updates a record according to the writer's conflict-handling rules.

`documents_saved` counts successful calls here. It does **not necessarily** mean that number of *new* database rows were inserted; a row might have been updated or left unchanged.

### Step C: Enqueue discovered links

```python
if targets:
    links_enqueued = await enqueue_targets(session, targets)
```

So the eligible discovered links can become future jobs in the Frontier.

Remember:

```text
440 discovered links != 440 enqueued links != 440 crawled pages
```

Host restrictions, nofollow, max-links, duplicates and DB constraints reduce the number enqueued, and the scheduler later decides which get fetched.

---

# 19. Finish the crawl attempt

```python
done = await finish_attempt(
    session,
    attempt_id,
    outcome if outcome in {
        "success", "failed", "blocked", "not_modified"
    } else "blocked",
    http_status=http_status,
    bytes_received=body_bytes,
    error_message=(
        message if outcome not in {"success", "not_modified"}
        else None
    ),
)

if not done:
    raise RuntimeError(
        f"Attempt {attempt_id} missing or already finished"
    )
```

A **crawl target** is the URL and its scheduling state. A **crawl attempt** is one specific try.

```text
Target #42
   |
   +-- Attempt #100: timeout
   +-- Attempt #101: HTTP 503
   +-- Attempt #102: HTTP 200, successful
```

If `finish_attempt()` fails, the code raises an exception. Since it is inside `session.begin()`, the other database changes in this transaction roll back too.

One detail to review: outcomes not in the four supported attempt strings are currently recorded as `blocked`, even when the job's actual outcome was `disabled` or another state. That loses some reporting detail.

---

# 20. Why everything is inside ONE short database transaction

Imagine a job just produced:

```text
1 accepted document
35 new Frontier candidates
1 crawl attempt to close
1 target scheduling transition
```

We don't want this result:

```text
Document saved: YES
New targets enqueued: YES
Attempt closed: NO
```

The purpose of `_finalize()` is to update all of those pieces together.

```python
async with session_factory() as session:
    async with session.begin():
        # lock and verify lease
        # change target state
        # save/delete documents
        # enqueue candidates
        # finish attempt
```

If an exception occurs and escapes the block, PostgreSQL rolls back this transaction. Earlier database changes made by the same transaction do not stay committed.

**But don't keep this transaction open while fetching a website.** A network request might take seconds or time out. Claim in a short transaction, do the HTTP work outside it, and finalize in another short transaction.

---

# 21. Return the result for logs and a future dashboard

```python
return JobResult(
    target_id=target_id,
    attempt_id=attempt_id,
    outcome=outcome,
    http_status=http_status,
    documents_saved=documents_saved,
    documents_skipped=skipped,
    links_discovered=discovered,
    links_enqueued=links_enqueued,
    message=message,
    duration_seconds=elapsed,
)
```

This does not fetch or persist anything by itself. It returns a structured report to the caller.

Example (illustrative):

```text
Target: 42
Attempt: 102
Outcome: success
HTTP: 200
Documents saved: 1
Documents skipped: 0
Links discovered: 88
Links enqueued: 35
Duration: 1.4 seconds
```

The future `runner` can aggregate these reports into a 10-minute crawler summary or live dashboard.

---

# 22. Real scenarios to understand the whole job

## Scenario 1: Everything goes right

```text
Target #42 is claimed with a 5-minute lease
        |
PolicyCoordinator ALLOW, HTTP 200
        |
Parser returns 1 document and 88 links
        |
Processor accepts 1 document
        |
Link helper creates 35 in-scope candidates
        |
_finalize() verifies the original lease
        |
complete_target() succeeds
        |
upsert_document() runs
        |
enqueue_targets() runs
        |
finish_attempt() succeeds
        |
Transaction COMMIT
```

Now the target has been finalized and its discovered links can later be scheduled. It doesn't mean the 35 links were fetched during this job.

## Scenario 2: Server is temporarily unavailable

```text
Target claimed
    |
HTTP 503 / DEFER
    |
No successful HTML to parse
    |
Worker chooses retry action
    |
_finalize() checks lease
    |
fail_target() + Retry-After scheduling
    |
finish_attempt()
    |
Transaction COMMIT
```

No document is saved from this failed fetch. We leave it eligible for a later retry according to the scheduler's rules.

## Scenario 3: robots.txt denies the URL

```text
PolicyCoordinator returns DENY
    |
Worker chooses block (if that's its policy)
    |
_finalize() checks lease
    |
Target becomes blocked
    |
Attempt finalized
```

No fetch body is parsed and no discovered links are enqueued.

## Scenario 4: Worker A loses the lease

```text
A claims Target #42
A starts a slow fetch
Lease expires
B claims Target #42
A finishes late
A's expected lease != database lease
    |
Finalize marks A's result stale
No document upsert
No new links enqueued
```

The finalizer protects the Frontier and stored results from stale Worker A.

## Scenario 5: Page is now `noindex`

```text
Yesterday: document was indexed
Today:  HTTP X-Robots-Tag says noindex
    |
_add_x_robots() updates metadata
    |
process() skips it with NOINDEX
    |
_noindex_urls() finds candidate identities
    |
_finalize() removes matching stored document rows
```

The code intends this behavior, but its URL matching and deletion scope must be verified before treating it as safe.

## Scenario 6: PostgreSQL fails halfway through

```text
Target transition succeeds in transaction
Document upsert succeeds in transaction
Link enqueue raises an exception
    |
Transaction ROLLBACK
    |
Target/document/link changes from this transaction undone
```

That's why related persistence belongs in one transaction.

---

# 23. Problems / TODOs before calling the Worker production-ready

These are checks based on the **shared excerpt**, not claims that the other unshared modules are broken.

- [ ] Fix `crawler.src.crawler...` import paths to match the actual package.
- [ ] Verify the `crawler.writer.attempts` and `crawler.writer.documents` implementations exist and their signatures match.
- [ ] Confirm the caller actually starts a crawl attempt, fetches, parses, processes and chooses an action; that code is not included here.
- [ ] Test the source-disable and lease-expiration race cases.
- [ ] Validate `max_links > 0` before link creation.
- [ ] Normalize both sides of `_noindex_urls()` URL comparisons.
- [ ] Avoid deleting unrelated documents based on untrusted canonical hints.
- [ ] Test multiple `X-Robots-Tag` headers and mixed bot scopes.
- [ ] Preserve server-requested retry delays longer than 24 hours, or suspend rather than retry too early.
- [ ] Validate `action` explicitly rather than letting unknown values fall through to `disabled`.
- [ ] Verify `finish_attempt()` ownership and result handling, especially in the stale-lease branch.
- [ ] Verify document upsert and Frontier enqueue are idempotent across repeats.
- [ ] Test transaction rollback when document upsert, enqueue or attempt finalization fails.
- [ ] Confirm target state transitions and attempt outcome values agree with the actual database constraints.

---

# 24. What we have vs. what we still need

**Already represented in the shared code:**

- Read HTTP headers case-insensitively.
- Extract supported `X-Robots-Tag` directives.
- Merge them with HTML robots metadata.
- Apply page-level and link-level nofollow for Frontier candidates.
- Normalize, filter and prepare discovered links.
- Identify noindex cleanup candidates.
- Lock the crawl target and check lease ownership.
- Transition the target and record the attempt.
- Upsert documents and enqueue targets atomically (assuming writer/repository functions behave as called).
- Return a `JobResult` summary.

**Not shown in the shared excerpt:**

- The `run_worker()` loop and scheduler claiming logic.
- The job entry point that calls `PolicyCoordinator.fetch()`.
- The decision tree mapping `FetchResult` to complete/retry/block/disable.
- Actual creation of `attempt_id` with `start_attempt()`.
- How the fetched `ParseResult` and `ProcessingResult` are passed to `_finalize()`.
- Deployment, background service lifecycle and production telemetry.

Those should be documented from their actual code when implemented; don't assume the helper/finalizer alone makes a complete working Worker.

---

# Final mental model

The Scheduler says **"Here is a URL you own for a limited time."**

The Policy Coordinator says **"Is it safe and allowed to fetch?"**

The Fetcher says **"Here is the HTTP response."**

The Parser says **"Here is the document and its discovered links."**

The Processor says **"Here is the normalized, classified, fingerprinted content—or a skip reason."**

The Worker helpers say **"Which robots rules and discovered links should we respect?"**

And `_finalize()` says:

> **"Before I save anything, prove you still own the lease. Then update the target, attempt, documents and Frontier together."**

That's the purpose of this entire job finalization stage in Developer's Eye.
