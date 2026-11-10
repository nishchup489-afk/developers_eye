"""Run one leased crawl target through Developer's Eye's offline pipeline.

Runner responsibility: claim/commit target leases, provide one shared
PolitenessManager, and dispatch one process_job() call per target.

Job responsibility: record attempt -> fetch/policy -> parse -> process ->
lease-safe transaction (reschedule + write + enqueue + finish attempt).

HTML, sitemap, feed and JSON API resources share one policy and lease lifecycle.
"""

from __future__ import annotations

import logging
import time

import asyncio
import random

from collections.abc import Awaitable, Callable
from sqlalchemy.exc import DBAPIError
from crawler.worker.jobs.schemas import JobOutcome, JobResult, TargetAction
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.session import SessionFactory
from backend.models.crawler_frontier import CrawlTarget
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate
from crawler.fetcher.fetch import HTTPXHopFetcher
from crawler.fetcher.config import ALLOWED_MEDIA_TYPES, FetcherConfig
from crawler.fetcher.schemas import OneHopFetcher
from crawler.frontier.repository import enqueue_targets
from crawler.frontier.scope import CrawlScope
from crawler.parser.parser import parse
from crawler.parser.schemas import ParseResult
from crawler.parser.sitemap import MAX_ENTRIES as MAX_SITEMAP_ENTRIES, parse_sitemap_resource
from crawler.parser.feeds import parse_feed
from crawler.parser.api import parse_json_api
from crawler.policy_and_politeness.policy_coordinator import FetchResult, PolicyCoordinator, _header
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.processing.processing import process
from crawler.processing.schemas import ProcessingResult
from crawler.worker.jobs.utility import _create_discovered_targets, _finalize
from crawler.worker.jobs.resources import plan_response, parse_resource
from crawler.writer.attempts import start_attempt
from crawler.worker.telemetry import checkpoint, checkpoint_batch
from crawler.worker.recovery import recover_failed_claim

logger = logging.getLogger(__name__)


class ShortTransactions:
    """Session-shaped object that runs each statement in its own transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def scalar(self, statement, *args, **kwargs):
        async with self._session_factory() as session, session.begin():
            return await session.scalar(statement, *args, **kwargs)

    async def execute(self, statement, *args, **kwargs) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(statement, *args, **kwargs)


def _resource_fetcher(kind: str) -> HTTPXHopFetcher:
    # Gzip file bodies are permitted only for sitemap jobs, still under byte limits.
    media = ALLOWED_MEDIA_TYPES
    if kind == "sitemap":
        media |= {"application/gzip", "application/x-gzip", "application/octet-stream"}
    return HTTPXHopFetcher(FetcherConfig(allowed_media_types=frozenset(media)))





async def retry_deadlocked_finalization(
    operation: Callable[[], Awaitable[JobResult]],
    *,
    max_attempts: int = 4,
) -> JobResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()

        except DBAPIError as exc:
            sqlstate = getattr(exc.orig, "sqlstate", None)

            # 40P01 = PostgreSQL deadlock detected.
            if sqlstate != "40P01":
                raise

            if attempt == max_attempts:
                logger.error(
                    "Finalization deadlock persisted after %d attempts",
                    max_attempts,
                )
                raise

            delay = min(0.2 * (2 ** (attempt - 1)), 2.0)
            delay += random.uniform(0.0, 0.15)

            logger.warning(
                "Database deadlock, retry %d/%d in %.2fs",
                attempt + 1,
                max_attempts,
                delay,
            )

            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable retry state")






async def _enqueue_overflow(
    session_factory: async_sessionmaker[AsyncSession],
    targets: list[CrawlTargetCreate],
    *,
    max_pages: int,
    batch_size: int,
) -> int:
    """Queue a large sitemap's extra URLs in short transactions of their own.

    Inserts are idempotent, so a crash here is safe: the target stays leased,
    expires, is fetched again, and the retry only adds what is still missing.
    """
    inserted = 0
    for start in range(0, len(targets), batch_size):
        async with session_factory() as session:
            async with session.begin():
                inserted += await enqueue_targets(
                    session, targets[start:start + batch_size], max_pages=max_pages
                )
    return inserted


async def process_job(
    target: CrawlTarget,
    *,
    politeness_manager: PolitenessManager,
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    fetcher: OneHopFetcher | None = None,
    max_links: int = 1_000,
) -> JobResult:
    """Execute ONE target claimed and committed by runner.py.

    Runner must share one PolitenessManager across its concurrently running
    jobs. It must NEVER share an AsyncSession across concurrent jobs.

    Exceptions during fetching/parsing/processing become retryable attempts.
    DB failures propagate to runner; transaction rollback + lease recovery
    protect correctness. Cancellation is intentionally not swallowed.
    """
    if target.id is None or target.lease_until is None or target.state != "leased":
        raise ValueError("process_job requires a committed, leased CrawlTarget")
    if max_links <= 0:
        raise ValueError("max_links must be positive")

    started = time.perf_counter()
    source_id = target.source_id
    target_id = target.id
    lease = target.lease_until

    # Step 1: Verify the claim and fetch the owning source's configuration.
    # Create and commit the attempt BEFORE any HTTP request.
    async with session_factory() as session:
        async with session.begin():
            current = await session.scalar(
                select(CrawlTarget).where(CrawlTarget.id == target_id).with_for_update()
            )
            db_now = await session.scalar(select(func.clock_timestamp()))
            if (
                current is None or current.state != "leased"
                or current.source_id != source_id
                or current.lease_until != lease or lease <= db_now
            ):
                return JobResult(target_id=target_id, outcome="stale", message="Not the current lease")

            source = await session.get(Source, source_id)
            if source is None or not source.is_enabled:
                current.state = "disabled"
                current.lease_until = None
                return JobResult(target_id=target_id, outcome="disabled", message="Source is disabled")

            allowed_hosts = tuple(source.allowed_hosts)
            interval_seconds = source.crawl_interval_seconds
            url = current.fetch_url
            kind = current.kind
            depth = current.depth
            scope = CrawlScope.from_config(source.config)
            discover_sitemaps = source.config.get("discover_sitemaps", kind in {"page", "sitemap"})
            follow_entry_links = source.config.get("follow_entry_links", False)
            api_options = source.config.get("api", {})
            attempt_id = await start_attempt(session, target_id, lease_until=lease)

    measurements = {"version": 1, "fetch_success": False, "parsed": False,
                    "accepted": 0, "skipped": [], "stored": 0, "documents": []}
    await checkpoint(session_factory, attempt_id, "FETCH", "running",
                     {"url": url}, measurements)

    action: TargetAction = "retry"
    outcome: JobOutcome = "failed"
    message = "Unknown failure"
    http_status: int | None = None
    body_bytes = 0
    retry_after: float | None = None
    parsed: ParseResult | None = None
    processed: ProcessingResult | None = None
    new_targets: list[CrawlTargetCreate] = []
    stage = "fetch"
    pending_parse = None

    if type(discover_sitemaps) is not bool or type(follow_entry_links) is not bool:
        action, message = "disable", "discover_sitemaps and follow_entry_links must be booleans"
    elif depth > scope.max_depth or (kind == "page" and not scope.allows(url, depth)):
        action, message = "disable", "URL exceeds the source depth or path scope"
    elif kind not in {"page", "sitemap", "rss", "api"}:
        action, message = "disable", f"Unsupported target kind: {kind}"
    else:
        try:
            coordinator = PolicyCoordinator(
                allowed_hosts=allowed_hosts,
                fetcher=fetcher if fetcher is not None else _resource_fetcher(kind),
                politeness_manager=politeness_manager,
            )

            # Each robots_cache read or write commits on its own, so no database
            # connection is ever held while waiting on a remote server.
            fetch_started = time.perf_counter()
            fetched: FetchResult = await coordinator.fetch(ShortTransactions(session_factory), url)

            measurements.update(
                fetch_ms=round((time.perf_counter() - fetch_started) * 1000, 2),
                final_url=fetched.final_url, redirects=list(fetched.redirect_chain),
                content_type=_header(fetched.headers, "content-type"),
                fetch_success=fetched.decision == RobotsDecision.ALLOW and fetched.status_code is not None
                and (200 <= fetched.status_code < 300 or fetched.status_code == 304),
            )
            await checkpoint(session_factory, attempt_id, "FETCH",
                             "success" if measurements["fetch_success"] else "blocked" if fetched.decision == RobotsDecision.DENY else "failed",
                             {"http_status": fetched.status_code, "bytes": len(fetched.body),
                              "duration_ms": measurements["fetch_ms"], "reason": fetched.reason}, measurements)

            http_status = fetched.status_code
            body_bytes = len(fetched.body)
            retry_after = fetched.retry_after_seconds
            message = fetched.reason

            response_plan = plan_response(fetched, kind=kind, allowed_hosts=allowed_hosts, scope=scope, depth=depth)
            action, outcome, message = response_plan.action, response_plan.outcome, response_plan.message
            if response_plan.parseable:
                content_type = _header(fetched.headers, "content-type") or ""
                stage = "parse"
                parser = {"page": parse, "sitemap": parse_sitemap_resource, "rss": parse_feed, "api": parse_json_api}[kind]
                # Parsing and processing are CPU work. Threads keep the event
                # loop free for other slots and the worker heartbeat.
                parsed = await asyncio.to_thread(
                    parse_resource, parser=parser, kind=kind, fetched=fetched,
                    content_type=content_type, allowed_hosts=allowed_hosts, scope=scope,
                    api_options=api_options, follow_entry_links=follow_entry_links,
                    discover_sitemaps=discover_sitemaps,
                )
                measurements["resource_kind"] = kind
                measurements["parsed"] = True
                pending_parse = {"documents": len(parsed.documents),
                                 "words": sum(len((d.body or "").split()) for d in parsed.documents)}
                stage = "process"
                processed = await asyncio.to_thread(process, parsed)
                measurements["accepted"] = len(processed.documents)
                measurements["skipped"] = [{"url": s.url, "reason": str(s.reason), "details": s.details} for s in processed.skipped]
                await checkpoint_batch(session_factory, attempt_id, [
                    ("PARSE", "success", pending_parse),
                    ("PROCESS", "accepted" if processed.documents else "skipped",
                     {"accepted": len(processed.documents), "skipped": measurements["skipped"]}),
                ], measurements)
                pending_parse = None
                new_targets = _create_discovered_targets(
                    parsed,
                    target_id=target_id,
                    source_id=source_id,
                    allowed_hosts=allowed_hosts,
                    # A sitemap is the source's URL list, so keep all of it.
                    max_links=MAX_SITEMAP_ENTRIES if kind == "sitemap" else max_links,
                    parent_depth=depth,
                    scope=scope,
                    target_kind=kind,
                )
                if len(new_targets) > max_links:
                    new_targets, overflow = new_targets[:max_links], new_targets[max_links:]
                    measurements["links_overflow_enqueued"] = await _enqueue_overflow(
                        session_factory, overflow,
                        max_pages=scope.max_pages, batch_size=max_links,
                    )
                action, outcome = "complete", "success"
                message = (
                    f"Parsed {len(processed.documents)} accepted, "
                    f"{len(processed.skipped)} skipped documents"
                )
        except Exception as exc:
            # This protects runner from a single job's fetch/parser/processor
            # exception. DB failures during final persistence are NOT swallowed.
            logger.exception("Crawl pipeline failed: target_id=%s", target_id)
            action, outcome = "retry", "failed"
            message = f"{type(exc).__name__}: {exc}"[:1000]
            measurements["error_category"] = stage
            if pending_parse is not None:
                await checkpoint_batch(session_factory, attempt_id, [
                    ("PARSE", "success", pending_parse), (stage.upper(), "failed", {"error": message}),
                ], measurements)
            else:
                await checkpoint(session_factory, attempt_id, stage.upper(), "failed", {"error": message}, measurements)
            parsed, processed, new_targets = None, None, []

    async def finalize_once() -> JobResult:
        return await _finalize(
        session_factory=session_factory,
        target_id=target_id,
        source_id=source_id,
        expected_lease_until=lease,
        attempt_id=attempt_id,
        action=action,
        outcome=outcome,
        message=message,
        http_status=http_status,
        body_bytes=body_bytes,
        retry_after_seconds=retry_after,
        interval_seconds=interval_seconds,
        parsed=parsed,
        processed=processed,
        targets=new_targets,
        elapsed=time.perf_counter() - started,
        measurements=measurements,
        max_pages=scope.max_pages,
        )

    try:
        return await retry_deadlocked_finalization(finalize_once)
    except Exception as exc:
        # The storage transaction has rolled back; preserve the reason independently.
        measurements["error_category"] = "persistence"
        await checkpoint(session_factory, attempt_id, "STORE", "failed",
                         {"error": f"{type(exc).__name__}: {exc}"[:1000]}, measurements)
        await recover_failed_claim(session_factory, target_id, lease, "persistence", message=f"{type(exc).__name__}: {exc}"[:1000])
        raise


__all__ = ["JobResult", "process_job"]
