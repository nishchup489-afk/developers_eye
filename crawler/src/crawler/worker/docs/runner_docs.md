# Runner.py — Developer's Eye Crawler Worker

> **Module:** `crawler/src/crawler/worker/runner.py`  
> **Stage:** Offline engine → Worker execution / orchestration  
> **Input:** eligible `crawl_target` rows from PostgreSQL  
> **Output:** claimed targets dispatched to `process_job()`, terminal logs, and a `BatchReport`  
> **This document explains:** the exact `runner.py` provided for Developer's Eye, not a proposed replacement.

---

# Before we start — what are we building here?

So we already built our **Source Registry**, **Seed Discovery**, **URL Frontier**, **Scheduler**, **Host/DNS/Robots/Politeness policies**, **HTTPX fetcher**, **HTML parser** and **Content Processor**.

We even ran a real integration test:

```text
5 URLs fetched
5 HTML pages parsed
5 documents accepted
440 links discovered
0 errors
0 database document commits
```

But the dry-run test was manually given five URLs. It wasn't selecting jobs from the Frontier or running them continuously.

Now imagine we have **10,000 URLs already waiting in PostgreSQL**. Who decides which ones to start, how many should run together, when to run the next batch and what happens after the process crashes?

That's why we need **`runner.py`**.

**Runner = the manager of the worker's execution loop.** It decides **WHEN and WHICH** jobs run. **`jobs.py`** decides **HOW** a claimed URL is crawled and finalized.

**Important:** this runner is **NOT** our old rollback-only dry-run. Calling `claim_batch()` writes and commits leases in PostgreSQL. The `process_job()` implementation may also save documents, attempts and discovered links. Do not run against production data as a harmless preview.

---

# 1. Full architecture — where Runner fits

```text
SOURCE REGISTRY
      |
      v
SEED DISCOVERY
      |
      v
URL FRONTIER (PostgreSQL)
   queued targets
      |
      v
SCHEDULER REPOSITORY
   recover_expired_leases()
   claim_targets()
      |
      v
RUNNER.PY
   claim_batch()       --> commit leases
      |
   run_batch()         --> dispatch claimed targets
      |
   execute_target()    --> semaphore + timeout
      |
      v
JOBS.PY: process_job(target)
   PolicyCoordinator
     -> HTTPXHopFetcher
     -> parse()
     -> process()
     -> _finalize()
      |
      v
POSTGRESQL
   crawl_target + crawl_attempt + document + discovered targets
      |
      v
JOB RESULT
      |
      v
RUNNER: BatchReport + logs
      |
      v
NEXT BATCH (when --forever)
```

There are **two separate database transactions** in the intended architecture:

1. **Claim transaction (Runner)** — lock/lease targets and commit *before* any HTTP request.
2. **Finalize transaction (Job)** — after fetching and processing, verify lease ownership and save the result.

Why separate them? Imagine a site takes 20 seconds to respond. We don't want to keep our `claim_targets()` database transaction open for those 20 seconds.

---

# 2. The file we're explaining

```text
crawler/
└── src/
    └── crawler/
        └── worker/
            ├── runner.py  <-- THIS FILE
            ├── jobs.py    <-- MUST expose process_job()
            └── tests/
                └── test_live_pipeline.py
```

The runner is a **controller**, not a fetcher or parser. You should not copy `PolicyCoordinator.fetch()`, `parse()`, or `process()` logic into this file.

The public contract expected from `jobs.py` is:

```python
async def process_job(target: CrawlTargetRead) -> JobResult:
    ...
```

It must be an async callable, accept the claimed target snapshot, handle its own database sessions and return an object with at least an `outcome` attribute. The rest of the `JobResult` fields improve logging. This **does not mean an empty `...` implementation works**; that is only a placeholder for a real job.

---

# 3. Imports — what are we using?

```python
from __future__ import annotations

import argparse
import asyncio
import logging
import selectors
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from backend.db.session import SessionFactory, engine
from backend.schema.crawler_frontier import CrawlTargetRead
from crawler.schedular.repository import claim_targets, recover_expired_leases
```

| Import | What it does in our Runner |
|---|---|
| `annotations` | Postpones evaluation of annotations, useful for type hints |
| `argparse` | Reads CLI flags like `--once`, `--forever`, `--concurrency` |
| `asyncio` | Runs multiple async jobs and imposes deadlines |
| `logging` | Structured logs (`START`, `DONE`, `CRASH`, `BATCH`) |
| `selectors`, `sys` | Selects a Windows-compatible event loop for Psycopg 3 |
| `time` | Monotonic elapsed-time measurements with `perf_counter()` |
| `Counter` | Counts how many jobs returned each outcome |
| `Awaitable`, `Callable`, `Any` | Describe the async job-handler contract |
| `dataclass`, `field` | Define validated configuration and mutable reports |
| `SessionFactory` | Creates PostgreSQL async sessions |
| `engine` | Disposed when the worker stops |
| `CrawlTargetRead` | Pydantic snapshot of a claimed target |
| `claim_targets()` | Atomically selects and leases eligible targets |
| `recover_expired_leases()` | Requeues previously leased targets whose leases expired |

Notice the Runner does **not** import the HTML parser or content processor. That is intentional: **those are Job responsibilities**.

---

# 4. Logger — why use logging instead of print?

```python
logger = logging.getLogger("crawler.worker.runner")
```

Later:

```python
logger.info("WORKER START ...")
logger.error("TIMEOUT ...")
logger.exception("CRASH ...")
```

`logging` gives a severity level and an identifiable component name. Example output (illustrative):

```text
2026-10-20 01:00:00 INFO crawler.worker.runner: WORKER START ...
2026-10-20 01:00:00 INFO crawler.worker.runner: CLAIM recovered=0 claimed=2 ...
2026-10-20 01:00:01 INFO crawler.worker.runner: START target=42 ...
2026-10-20 01:00:04 INFO crawler.worker.runner: DONE target=42 outcome=success ...
```

When we add telemetry and an admin dashboard, structured job events will be easier to monitor than scattered `print()` calls. The current code only writes ordinary Python logs; it **does not yet send telemetry** to the dashboard.

---

# 5. `JobHandler` — what's this weird typing syntax?

```python
JobHandler = Callable[[CrawlTargetRead], Awaitable[Any]]
```

Break it down:

- `Callable[...]` — something we can call like a function.
- `[CrawlTargetRead]` — it accepts **one target object**.
- `Awaitable[Any]` — calling it returns something we can `await`.
- `Any` — this runner does not statically enforce a specific result class yet.

So the alias means:

> Give the Runner an async job function that accepts a claimed target.

Example:

```python
async def process_job(target: CrawlTargetRead):
    # fetch, parse, process, finalize, and return JobResult
    ...
```

The Runner doesn't need to know how the job works internally; it just invokes:

```python
result = await job_handler(target)
```

This separation also makes tests easier: we can inject a fake job handler into `run_batch()` without fetching real pages. That is **dependency injection**.

---

# 6. `RunnerConfig` — all the rules in one dataclass

```python
@dataclass(frozen=True, slots=True)
class RunnerConfig:
    batch_size: int = 5
    concurrency: int = 2
    lease_seconds: int = 300
    job_timeout_seconds: int = 240
    poll_seconds: float = 10.0
    source_id: int | None = None
    forever: bool = False
```

Instead of hardcoding random numbers all over the Runner, we collect them in one object.

| Setting | Default | Why it's here |
|---|---:|---|
| `batch_size` | 5 | Requested maximum number of targets for a batch |
| `concurrency` | 2 | Maximum number of jobs started together |
| `lease_seconds` | 300 | Scheduler claims each target for 5 minutes |
| `job_timeout_seconds` | 240 | Stop a job that runs longer than 4 minutes |
| `poll_seconds` | 10.0 | Wait before polling again when no targets were claimed |
| `source_id` | `None` | Optional restriction to one registered source |
| `forever` | `False` | One batch by default, continuous loop if True |

`@dataclass` automatically provides an initializer (`__init__`), field representation, etc. `frozen=True` prevents ordinary field reassignment after creation, and `slots=True` reduces per-instance attribute overhead.

Example:

```python
config = RunnerConfig(
    batch_size=10,
    concurrency=3,
    lease_seconds=300,
    job_timeout_seconds=240,
)
```

**Careful:** In *this implementation*, the actual claim count is `min(batch_size, concurrency)`, so this example claims **3**, not 10, targets per batch. We'll explain why in `claim_batch()`.

---

# 7. `__post_init__()` — validating configuration

Inside `RunnerConfig`:

```python
def __post_init__(self) -> None:
    if self.batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if self.concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if self.lease_seconds < 30:
        raise ValueError("lease_seconds must be >= 30")
    if self.job_timeout_seconds <= 0:
        raise ValueError("job_timeout_seconds must be positive")
    if self.job_timeout_seconds > self.lease_seconds - 15:
        raise ValueError(
            "job_timeout_seconds must leave at least 15 seconds "
            "before lease expiration for finalization"
        )
    if self.poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    if self.source_id is not None and self.source_id <= 0:
        raise ValueError("source_id must be positive")
```

`__post_init__()` runs automatically after the dataclass initializer.

Imagine somebody starts the worker with:

```text
--lease-seconds 60 --job-timeout-seconds 120
```

We would allow a job to run for 120 seconds, even though it loses its lease after 60 seconds. That makes no sense: a different worker could reclaim the URL before the first one finishes.

The validation rejects that configuration. With the defaults:

```text
Lease:              300 seconds
Job deadline:       240 seconds
Remaining budget:    60 seconds
```

A timeout is a **runner-level deadline**, not an automatic guarantee the job will be finalized successfully. The real job still needs to validate the lease during finalization. Network delays, scheduler delays, or task cancellation can consume this remaining budget.

**TODO:** The current validation assumes correctly typed, finite values. If configuration starts coming from arbitrary application data rather than `argparse`, validate types and non-finite floats (`NaN`, `Infinity`) too.

---

# 8. `BatchReport` — statistics for one batch

```python
@dataclass(slots=True)
class BatchReport:
    recovered: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    timed_out: int = 0
    outcomes: Counter[str] = field(default_factory=Counter)
    elapsed_seconds: float = 0.0
```

This holds batch-level numbers, not the content of the pages themselves.

Example (illustrative):

```text
recovered: 1
claimed: 2
succeeded: 1
failed: 1
timed_out: 1
outcomes: {'success': 1}
elapsed_seconds: 240.3
```

Why use `field(default_factory=Counter)` rather than `outcomes = Counter()`?

Because a mutable object must **not be shared unintentionally** between different report instances. `default_factory` creates a fresh `Counter` for every new `BatchReport`.

`Counter` works like a dictionary of counts:

```python
outcomes = Counter()
outcomes["success"] += 1
outcomes["success"] += 1
outcomes["blocked"] += 1
# Counter({'success': 2, 'blocked': 1})
```

---

# 9. `claim_batch()` — recover + claim in a short transaction

Full function:

```python
async def claim_batch(
    config: RunnerConfig,
) -> tuple[int, list[CrawlTargetRead]]:
    async with SessionFactory() as session:
        async with session.begin():
            recovered = await recover_expired_leases(session)

            claim_limit = min(config.batch_size, config.concurrency)
            rows = await claim_targets(
                session=session,
                limit=claim_limit,
                lease_seconds=config.lease_seconds,
                source_id=config.source_id,
            )
            targets = [CrawlTargetRead.model_validate(row) for row in rows]

    return recovered, targets
```

## Step 1 — Create an async session

```python
async with SessionFactory() as session:
```

Our backend `SessionFactory` creates an `AsyncSession`. It's responsible for communicating with PostgreSQL. The context manager closes it afterward.

## Step 2 — Begin a transaction

```python
async with session.begin():
```

This starts a transaction. On successful exit, SQLAlchemy commits. If an error escapes, it rolls back.

## Step 3 — Recover expired leases

```python
recovered = await recover_expired_leases(session)
```

Imagine:

```text
Target #25
state = leased
lease_until = 11:30
current database time = 11:35
```

The lease has expired. The old worker might have crashed or been stopped. Your scheduler repository moves expired leased targets back into the eligible queue.

**Important:** This recovery is based on time and target state, not on confirming that the original process is dead. The old worker might still be running. That is why `jobs.py` must check ownership before saving results.

## Step 4 — Calculate claim limit

```python
claim_limit = min(config.batch_size, config.concurrency)
```

Examples:

| Batch size | Concurrency | Actually claimed |
|---:|---:|---:|
| 5 | 2 | 2 |
| 10 | 3 | 3 |
| 5 | 5 | 5 |
| 2 | 10 | 2 |

Why do this?

Suppose you claim 100 targets but can only run two jobs simultaneously. The other 98 URLs start losing their five-minute leases while waiting in memory for their turn.

The current Runner avoids that by **not claiming more URLs than it can dispatch immediately**. It therefore behaves as a series of small waves, not a 100-target batch with only two active workers.

## Step 5 — Claim targets

```python
rows = await claim_targets(
    session=session,
    limit=claim_limit,
    lease_seconds=config.lease_seconds,
    source_id=config.source_id,
)
```

Your scheduler repository already knows how to select eligible targets, prioritize them and issue leases. We call it rather than duplicating its SQL here.

The scheduler uses `FOR UPDATE SKIP LOCKED` in its claim operation. That allows multiple worker processes to avoid claiming the same locked row concurrently.

## Step 6 — Snapshot ORM records into Pydantic objects

```python
targets = [CrawlTargetRead.model_validate(row) for row in rows]
```

What does that do?

- `row` is a `CrawlTarget` SQLAlchemy ORM object tied to the session.
- `model_validate(row)` copies its fields into `CrawlTargetRead` (which has `from_attributes=True`).
- The Pydantic snapshot can then travel safely to the job handler after the claim session closes.

Crucially, this includes the **original `lease_until` timestamp**. Do **not** create a new timestamp in `process_job()` when finalizing the claim.

## Step 7 — Transaction commits, then returns

After leaving both `async with` blocks:

```python
return recovered, targets
```

The claims are committed to PostgreSQL before the Runner begins network work.

**Main lesson:** `claim_batch()` does NOT fetch webpages. It only reserves which URLs we're allowed to work on.

---

# 10. `execute_target()` — run exactly one claimed job

Signature:

```python
async def execute_target(
    target: CrawlTargetRead,
    *,
    job_handler: JobHandler,
    semaphore: asyncio.Semaphore,
    config: RunnerConfig,
    report: BatchReport,
) -> None:
```

Here we finally dispatch a target to `jobs.py`.

This function is **not supposed to mark the target complete itself**. The job handler owns processing and finalization.

## Step 1 — Acquire a semaphore

```python
async with semaphore:
```

A semaphore is a concurrency gate. Imagine our worker has `concurrency=2`.

```text
Job A -> gets a slot -> runs
Job B -> gets a slot -> runs
Job C -> waits until a slot is released
```

With this Runner's current `claim_limit`, we normally don't create more active job tasks than the semaphore permits. Keeping the semaphore is still useful as a guard if dispatching changes later.

The semaphore limits **jobs inside this runner process**, not the entire deployment across multiple virtual machines.

## Step 2 — Measure time and log start

```python
started = time.perf_counter()

logger.info(
    "START target=%s source=%s url=%s lease_until=%s",
    target.id,
    target.source_id,
    target.fetch_url,
    target.lease_until,
)
```

`time.perf_counter()` is suitable for measuring elapsed durations. Don't use it as a timestamp to store in PostgreSQL.

The placeholders `%s` are filled by the logging system. This style allows logging to defer string formatting until needed.

## Step 3 — Apply a deadline

```python
async with asyncio.timeout(config.job_timeout_seconds):
    result = await job_handler(target)
```

`asyncio.timeout(240)` means the job is given a maximum of roughly 240 seconds in this scope. On expiry, Python cancels the task and raises `TimeoutError` to the surrounding handler, assuming the job cooperates with cancellation.

**Don't confuse:**

- `lease_seconds` — ownership duration stored in PostgreSQL.
- `job_timeout_seconds` — local runtime deadline in Python.

The timeout doesn't extend the database lease. And it doesn't automatically call `fail_target()`; that remains the job's or later lease-recovery path's responsibility.

## Step 4 — Validate the result

```python
if result is None or not hasattr(result, "outcome"):
    raise TypeError(
        "process_job must return a JobResult with an 'outcome' field"
    )
```

If `process_job()` accidentally returns `None`, we do not pretend the crawl succeeded.

`hasattr(result, "outcome")` only checks that the field exists. It does **not** verify that the returned object is a proper `JobResult` or that the outcome is a valid enum value.

## Step 5 — Count outcomes

```python
outcome = str(getattr(result.outcome, "value", result.outcome))
report.outcomes[outcome] += 1

if outcome in {"success", "not_modified"}:
    report.succeeded += 1
elif outcome in {"failed", "error"}:
    report.failed += 1
```

`getattr(result.outcome, "value", result.outcome)` supports either an Enum with a `.value` property or a plain string.

Example:

```text
result.outcome = "success"
  -> outcome = "success"
  -> outcomes['success'] += 1
  -> succeeded += 1
```

Note: `"retry"`, `"blocked"`, `"disabled"`, `"deferred"` and `"stale"` are **not counted as `failed` by this implementation**, even though they may represent work that didn't yield a saved document. The `outcomes` counter records their names if returned. Keep that in mind when interpreting the exit code.

## Step 6 — Print job result through logging

```python
logger.info(
    "DONE target=%s outcome=%s status=%s docs=%s links=%s duration=%.2fs",
    target.id,
    outcome,
    getattr(result, "http_status", None),
    getattr(result, "documents_saved", 0),
    getattr(result, "links_enqueued", 0),
    time.perf_counter() - started,
)
```

The `getattr(..., default)` calls let the logger show a value even when optional report fields are absent. They don't mean those documents or links were definitely saved.

---

# 11. Timeout, crash and cancellation — what happens?

At the end of `execute_target()`:

```python
except TimeoutError:
    report.timed_out += 1
    report.failed += 1
    logger.error("TIMEOUT ...")

except Exception:
    report.failed += 1
    logger.exception("CRASH ...")
```

## Scenario A — website hangs / job exceeds deadline

```text
Target #10 claimed at 12:00
Lease ends at 12:05
Job times out about 12:04
Runner records timeout in BatchReport
Target may still be leased
Recovery can requeue it once lease expires
```

The Runner **does not instantly mark the target failed in PostgreSQL** on this path. It leaves that recovery to the lease-expiry mechanism if the job hasn't already finalized.

Why is this useful? We don't want to fake completion of a job after a crash, nor overwrite a new owner.

## Scenario B — job raises a Python error

```python
raise RuntimeError("Unexpected parser wiring error")
```

`logger.exception(...)` prints a traceback, and the Runner increments `failed`. Again, it does not fabricate a database finalization on behalf of the job.

## Scenario C — whole worker shuts down

The file intentionally does **not** catch `asyncio.CancelledError` inside `execute_target()`.

This allows cancellation to propagate. Any claimed target not correctly finalized can be recovered after its lease expires.

**Important production TODO:** Before adding large-scale concurrency, test cancellation with real database sessions and verify job cleanup is cancellation-safe. The timeout is not a substitute for reliable finalization.

---

# 12. `run_batch()` — dispatch a wave of jobs

```python
async def run_batch(
    *,
    config: RunnerConfig,
    job_handler: JobHandler,
) -> BatchReport:
```

What happens in order?

## Step 1 — Create a fresh report

```python
started = time.perf_counter()
report = BatchReport()
```

## Step 2 — Recover and claim

```python
report.recovered, targets = await claim_batch(config)
report.claimed = len(targets)
```

Tuple unpacking here assigns both returned values:

```text
claim_batch() -> (3, [target10, target11])
report.recovered -> 3
report.claimed   -> 2
```

## Step 3 — Create semaphore and execute jobs concurrently

```python
if targets:
    semaphore = asyncio.Semaphore(config.concurrency)
    await asyncio.gather(*(
        execute_target(
            target,
            job_handler=job_handler,
            semaphore=semaphore,
            config=config,
            report=report,
        )
        for target in targets
    ))
```

We should understand `asyncio.gather()`.

It lets multiple async operations make progress together within the same event loop. Example:

```text
Target #1 --> waiting for website response
Target #2 --> performing DNS/robots request
```

When one job awaits network I/O, the event loop can schedule the other.

The `*` before the generator expression unpacks generated coroutine objects into separate arguments to `asyncio.gather()`.

Without `await`, gathering wouldn't wait for the results to complete.

**Difference between concurrency and parallel CPU execution:** These are asyncio tasks, primarily designed for overlapping I/O, not necessarily two CPU cores executing Python bytecode in parallel.

## Step 4 — Calculate batch duration

```python
report.elapsed_seconds = time.perf_counter() - started
```

This includes recovery, claiming, job execution, and reporting overhead.

## Step 5 — Log and return the batch result

The code logs:

```text
BATCH recovered=... claimed=... succeeded=... failed=... timed_out=... outcomes=... duration=...
```

Then returns `BatchReport`.

**Key point:** `run_batch()` runs **one wave** of at most `min(batch_size, concurrency)` claimed targets, not an arbitrary number of waves.

---

# 13. `run_worker()` — the main execution loop

```python
async def run_worker(
    *,
    config: RunnerConfig,
    job_handler: JobHandler,
) -> int:
```

This is the heart of `runner.py`.

It starts counters:

```python
cycles = 0
total_claimed = 0
total_failed = 0
```

Then executes:

```python
while True:
    report = await run_batch(config=config, job_handler=job_handler)
    cycles += 1
    total_claimed += report.claimed
    total_failed += report.failed

    if not config.forever:
        break

    if report.claimed == 0:
        await asyncio.sleep(config.poll_seconds)
```

## If `forever=False`

```text
Start
  -> recover and claim
  -> process that one batch
  -> exit
```

This is `--once`, the default.

## If `forever=True`

```text
Start
  -> claim and run batch
  -> claim and run another batch
  -> ... repeat
```

When **no eligible URLs exist**, it sleeps `poll_seconds` before checking again.

When **URLs were claimed**, it immediately starts another cycle after the current batch completes. This keeps throughput high, but can be too aggressive if the job handler consistently returns immediate results without consuming or rescheduling the queue. Avoid a tight loop in that case.

## Finally block — clean up the database engine

```python
finally:
    logger.info("WORKER STOP ...")
    await engine.dispose()
```

`finally` runs when the coroutine exits normally or because of an exception/cancellation, subject to process-level termination limitations.

`engine.dispose()` closes the pool's idle database connections and discards pool resources. It is appropriate for shutting down this command-line worker, but isn't a replacement for closing every job's own session correctly.

## Exit code

```python
return 1 if total_failed else 0
```

- `0` — No failures *counted by this runner*.
- `1` — At least one failure or timeout counted.

This does **not** mean exit code 0 proves all jobs produced documents; outcomes like `blocked`, `deferred` or `stale` are not counted as failures by the current rules.

---

# 14. `parse_args()` — controlling the worker from PowerShell

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Developer's Eye frontier worker"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="...")
    mode.add_argument("--forever", action="store_true", help="...")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--job-timeout-seconds", type=int, default=240)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--source-id", type=int, default=None)
    parser.add_argument(
        "--log-level", default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser.parse_args()
```

A **CLI argument** is a value you supply when starting a program in a terminal.

`add_mutually_exclusive_group()` prevents `--once` and `--forever` from being supplied together.

The code checks `args.forever` when constructing `RunnerConfig`; the `--once` flag mainly serves as an explicit counterpart to `--forever`, since one batch is already the default.

| Flag | What it controls | Example |
|---|---|---|
| `--once` | Run only one batch | `--once` |
| `--forever` | Continue polling | `--forever` |
| `--batch-size` | Max intended wave size | `--batch-size 5` |
| `--concurrency` | Simultaneous jobs | `--concurrency 2` |
| `--lease-seconds` | Lease duration | `--lease-seconds 300` |
| `--job-timeout-seconds` | Local job deadline | `--job-timeout-seconds 240` |
| `--poll-seconds` | Idle polling delay | `--poll-seconds 10` |
| `--source-id` | Restrict claiming to a source | `--source-id 1` |
| `--log-level` | Logging verbosity | `--log-level DEBUG` |

---

# 15. `load_job_handler()` — importing `process_job()` only when needed

```python
def load_job_handler() -> JobHandler:
    try:
        from crawler.worker.jobs import process_job
    except ImportError as exc:
        raise RuntimeError(
            "Implement and export async process_job(target: CrawlTargetRead) "
            "from crawler.worker.jobs before running the worker. "
            "Your repository's jobs.py currently has no implementation."
        ) from exc

    if not callable(process_job):
        raise TypeError("crawler.worker.jobs.process_job must be callable")
    return process_job
```

Why import inside the function rather than at the top of the file?

It's called a **lazy import**. It allows us to open the Runner's CLI help (`--help`) without requiring the unfinished `jobs.py` to be importable.

If Python cannot import `process_job()`, the Runner raises a clear error before it claims jobs.

But there is an important nuance: `callable(process_job)` only verifies that it's callable. It doesn't prove it is an `async def`, that it accepts a `CrawlTargetRead`, or that it returns the required result. Those errors are caught later when a job actually executes.

**Current integration status:** The repository branch checked while preparing this Runner contained an empty `crawler/src/crawler/worker/jobs.py`. The runner is complete as an orchestrator, but running actual jobs requires you to implement and test that contract first. Your previously shared `_finalize()` helper is only part of that job implementation.

---

# 16. `main()` and the `__main__` block

```python
async def main(config: RunnerConfig) -> int:
    return await run_worker(
        config=config,
        job_handler=load_job_handler(),
    )
```

`main()` wires the actual job handler into the generic `run_worker()` controller.

When this module is executed directly:

```python
if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(...)
    config = RunnerConfig(...)
    ...
```

it parses the command line, initializes logging, builds `RunnerConfig`, then starts the async event loop.

## Why special Windows code?

```python
if sys.platform == "win32":
    exit_code = asyncio.run(
        main(config),
        loop_factory=lambda: asyncio.SelectorEventLoop(
            selectors.SelectSelector()
        ),
    )
else:
    exit_code = asyncio.run(main(config))

raise SystemExit(exit_code)
```

We've encountered this problem before while testing the crawler on Windows:

```text
Psycopg cannot use the ProactorEventLoop in async mode
```

By explicitly using a **SelectorEventLoop on Windows**, this CLI runner avoids that specific Psycopg 3 incompatibility. Linux typically uses the default loop without this change.

`SystemExit(exit_code)` tells the terminal whether the command succeeded according to the Runner's exit-status policy.

---

# 17. PowerShell commands — how to run it

From the repository root, assuming the crawler's Poetry environment is active and PostgreSQL/configuration are available:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .\crawler\src);$(Resolve-Path .\backend\src)"
```

**See available options without running jobs:**

```powershell
python -m crawler.worker.runner --help
```

**Run a single batch:**

```powershell
python -m crawler.worker.runner --once --batch-size 5 --concurrency 2
```

With those options, this implementation claims **up to 2** targets, because it uses `min(5, 2)`.

**Run continuously:**

```powershell
python -m crawler.worker.runner --forever --batch-size 5 --concurrency 2 --poll-seconds 10
```

**Test one specific source:**

```powershell
python -m crawler.worker.runner --once --source-id 1
```

**More logging:**

```powershell
python -m crawler.worker.runner --once --log-level DEBUG
```

**Before running a real job**, your source/Frontier must already contain eligible targets. Your project's bootstrap command may create those records:

```powershell
python -m crawler.main bootstrap
```

That bootstrap command **commits database writes**, and so does the Runner's claim step. The CLI is not a no-write testing tool.

---

# 18. Scenarios — imagine what happens in real life

## Scenario 1 — 10,000 eligible URLs, concurrency 2

```text
PostgreSQL: 10,000 queued targets
Runner config: batch_size=5, concurrency=2

Cycle #1 -> claim 2 -> run 2
Cycle #2 -> claim 2 -> run 2
Cycle #3 -> claim 2 -> run 2
... continuing under --forever
```

Why not claim 5 at once? Because the current code purposely avoids letting claimed targets wait behind other active jobs. It keeps each lease as useful as possible.

## Scenario 2 — worker crashes after claiming

```text
12:00:00 Runner claims target #75
12:00:01 Claim transaction commits
12:00:02 Job starts
12:00:05 Process crashes
12:05:00 Lease expires
Next recovery cycle -> requeues target #75
```

The Runner doesn't magically know the crashed process is gone. The lease expiry enables eventual recovery. When claiming/finalizing, other workers must still protect against stale ownership.

## Scenario 3 — worker A is slow, worker B takes over

```text
Worker A claims #80, lease until 12:05
Worker A takes too long
Lease expires
Worker B recovers + claims #80, new lease until 12:10
Worker A finally produces an HTML document
```

Worker A **must not save it** just because fetching succeeded. `jobs.py` must verify the original lease before writing. That's why the job's `_finalize()` lease guard is so important.

The Runner itself doesn't enforce that finalization guard; it relies on the job implementation to do so.

## Scenario 4 — HTTP 503 with Retry-After

```text
Runner -> process_job(target #81)
Job -> PolicyCoordinator receives HTTP 503
Job -> retry/fail_target according to policy
Runner <- JobResult(outcome=...)
```

The Runner merely records the outcome. It does **not** calculate HTTP backoff or read the `Retry-After` header; those belong to your policy, job, and scheduler logic.

## Scenario 5 — robots.txt denies a URL

```text
Runner claimed #90
Job checks robots before fetching page
RobotsDecision.DENY
Job finalizes as blocked according to policy
Runner logs its reported outcome
```

The Runner shouldn't bypass robots rules or create its own alternative fetch path. A proper `process_job()` uses the Policy Coordinator.

## Scenario 6 — source gets disabled mid-crawl

```text
Runner claims a target from Source #3
Administrator disables Source #3
Job finishes fetching
Job checks source status during finalization
```

It is the job's responsibility to prevent inappropriate persistence and handle that state safely. This Runner does not currently re-check `Source.is_enabled` before dispatch. The scheduler's current `claim_targets()` implementation also filters eligibility by target state/time, **not by a join against enabled sources**. This is a deployment concern to fix before operating at scale.

## Scenario 7 — no eligible targets

```text
Runner: --forever --poll-seconds 10
claim_batch() -> []
Runner logs IDLE
Runner sleeps 10 seconds
Runner checks again
```

No busy retry loop while idle. In one-batch mode, it exits after an empty batch.

## Scenario 8 — two Runner processes

Both can call `claim_targets()` concurrently. PostgreSQL's row locks and `SKIP LOCKED` make it possible for them to claim **different** rows without blocking on one another's selected target locks.

But **each process has its own `concurrency` and `PolitenessManager` state**. Local concurrency and politeness limits do not add up to a global per-host request limit. For multiple VMs, we eventually need shared host budgeting/politeness controls.

---

# 19. Common mistakes — especially ones from our first handwritten runner

### Mistake 1 — marking complete immediately after claim

```python
claimed = await claim_targets(...)
for target in claimed:
    await complete_target(...)
```

This would be wrong because claim only assigns ownership. The page has not yet been fetched or processed.

Correct mental sequence:

```text
Claim -> Commit -> Fetch/Parse/Process -> Finalize
```

### Mistake 2 — doing network I/O inside `session.begin()`

Holding a transaction open during slow HTTP calls is unnecessary and can create lock contention and operational problems. Keep claim and finalize transactions short.

### Mistake 3 — inventing a new lease expiration timestamp

Never calculate `datetime.now() + timedelta(...)` when calling job finalization to **pretend** it is the original lease. Use `target.lease_until` returned by the claim operation.

### Mistake 4 — forgetting `await`

Our repository methods and handler are async:

```python
recovered = await recover_expired_leases(session)
targets = await claim_targets(session, limit=2)
result = await job_handler(target)
```

Without `await`, you receive a coroutine instead of the result.

### Mistake 5 — using `asyncio.run()` inside `async def`

Start the event loop once, in the command-line entry point. Inside async functions, `await` other coroutines.

### Mistake 6 — sharing one AsyncSession across concurrent jobs

A database session represents one unit of work / transaction context. Don't pass the Runner's claim-session object to multiple concurrently executing jobs. Give jobs separate sessions for robots lookups, attempts and finalization.

---

# 20. Important implementation limitations / TODOs

This section is not hypothetical criticism; it describes what the **current** `runner.py` does and does not do.

- **`jobs.py` integration is required.** Without a real async `process_job()` that returns a valid result and finalizes a target, the Runner cannot safely execute production work. `--help` remains available because the import is lazy.
- **This Runner commits lease changes.** There is no `--dry-run` flag. Use the separate `test_live_pipeline.py` for no-commit pipeline experiments.
- **`batch_size` isn't the number claimed when concurrency is smaller.** The code uses `min(batch_size, concurrency)`. If you want batches larger than concurrency, you'll need explicit lease-aware queue management or wave scheduling.
- **Retry/blocked/deferred/stale statistics are incomplete.** The `report.outcomes` counter records returned outcome names, but `report.failed` increments only for `failed`, `error`, local timeout, or exceptions. A zero exit code is not proof that all jobs succeeded or that documents were saved.
- **Leases aren't heartbeated or renewed.** Long jobs must finish before expiry or be abandoned/recovered. Increasing the timeout without modifying lease policy can cause stale writes if the job fails to guard finalization.
- **A timed-out job isn't immediately marked failed by the Runner.** If it didn't finalize, it remains leased until recovery. That is intentional here, but creates delay before retry.
- **A completed source might become disabled while a job is running.** Enforce current source state during job finalization, and consider making scheduler claims source-aware.
- **Local concurrency doesn't enforce fleet-wide limits.** Several workers/VMs need shared per-host politeness and rate limiting before scaling out.
- **No process-wide metrics exporter yet.** Logs and in-memory reports are available; the admin-dashboard telemetry pipeline is a separate stage.
- **No worker-level stop-after-N-batches or max-runtime option.** `--forever` runs until interrupted or a fatal error propagates.
- **Potential tight loop when work constantly exists.** After a nonempty batch, this runner doesn't sleep. Usually that's desirable, but monitor CPU and database polling if jobs finish instantly.
- **No automatic seed/discovery in this file.** Bootstrap occurs separately; runner processes already queued targets.
- **No document indexing call here.** Your job may persist documents; the Search Indexer remains a separate responsibility.

---

# 21. Function-by-function cheat sheet

| Function / class | Purpose | Database interaction? |
|---|---|---|
| `RunnerConfig` | Stores and validates execution settings | No |
| `BatchReport` | Holds counters and timings for a batch | No |
| `claim_batch()` | Recover expired leases and claim/commit eligible URLs | **Yes; commits on success** |
| `execute_target()` | Await one job under concurrency/deadline controls | Through `job_handler` |
| `run_batch()` | Claim and dispatch one wave; produce report | Calls `claim_batch()` and jobs |
| `run_worker()` | Loop over batches and perform shutdown cleanup | Through subfunctions; disposes engine |
| `parse_args()` | Parse CLI arguments | No |
| `load_job_handler()` | Import required `process_job` callable | No direct database operation |
| `main()` | Wire config and job handler into the runner | Through `run_worker()` |
| `__main__` block | Initialize logging and event loop | Through `main()` |

---

# 22. The difference between `runner.py`, `jobs.py`, and the Scheduler

Imagine a real delivery service:

- **Scheduler** = the dispatcher that chooses which package needs to be delivered and assigns it for a limited time.
- **Runner** = the team lead deciding how many couriers to send and when to ask for more assignments.
- **Job** = a courier actually performing one delivery and reporting what happened.

For our crawler:

```text
Scheduler = claim_targets / recover leases
Runner    = claim_batch / execute_target / run_worker
Job       = fetch / parse / process / finalize
```

This separation matters because we can test, optimize, and scale each responsibility independently.

---

# 23. What should we test before calling the Worker complete?

Use isolated job handlers and a **development PostgreSQL database** to cover:

1. **Claim correctness:** one target gets claimed once and its lease commits before job execution.
2. **Empty Frontier:** `--once` exits without crashing; `--forever` polls at the configured idle interval.
3. **Two concurrent targets:** both handlers run without sharing the claim session.
4. **Job returns success:** counters/logs are correct and the real job's attempt/finalization is durable.
5. **Job returns blocked/deferred:** no inappropriate document write or retry.
6. **Job crashes:** Runner logs exception; expired lease can be recovered on a later cycle.
7. **Job times out:** cancellation propagates correctly to DB cleanup; target can be reclaimed later.
8. **Stale lease:** old job cannot publish results after the lease changes.
9. **Source disabled:** no new document is published against an invalid/disabled source.
10. **Multiple processes:** `SKIP LOCKED` avoids simultaneously claiming the same row, while shared politeness policy is assessed separately.

Avoid testing this by pointing it at production until the real job handler and database writer have been reviewed.

---

# 24. Final recap — what did we build?

Our old test worked like this:

```text
Hardcoded URLs -> Policy -> Fetch -> Parse -> Process -> Terminal
```

Our new production-oriented design works like this:

```text
Frontier -> Scheduler claims -> Runner commits leases
        -> Runner starts jobs (concurrently)
        -> Job handles fetch/parse/process/finalize
        -> Runner logs outcomes -> Repeat when --forever
```

The most important principle is:

> **The Runner decides which jobs run and how many. The Job decides how to process one target and whether it can safely commit the result.**

Don't mark a target complete just because it was claimed. Don't start a network request inside a long claim transaction. Don't invent a new lease timestamp. And don't interpret a Runner report as proof of persistence until the underlying job has safely finalized.

**Next implementation milestone:** write and thoroughly test the real `process_job(target: CrawlTargetRead)` implementation that uses the already completed Policy Coordinator, Fetcher, Parser, Processor and the transactional `_finalize()` logic.
