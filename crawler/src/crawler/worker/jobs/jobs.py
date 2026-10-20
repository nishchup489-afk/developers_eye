"""Run one leased HTML crawl target through Developer's Eye's offline pipeline.

Runner responsibility: claim/commit target leases, provide one shared
PolitenessManager, and dispatch one process_job() call per target.

Job responsibility: record attempt -> fetch/policy -> parse -> process ->
lease-safe transaction (reschedule + write + enqueue + finish attempt).

MVP limitation: only target.kind == 'page' is supported. RSS, API and
sitemaps need dedicated parsers/dispatchers before enabling those kinds.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from crawler.worker.jobs.schemas import JobOutcome, JobResult, TargetAction
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.session import SessionFactory
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate
from crawler.fetcher.fetch import HTTPXHopFetcher
from crawler.fetcher.schemas import OneHopFetcher
from crawler.frontier.repository import enqueue_targets
from crawler.frontier.urls import normalize_url
from crawler.parser.parser import parse
from crawler.parser.schemas import ParseResult
from crawler.policy_and_politeness.host_policy import is_allowed_host
from crawler.policy_and_politeness.policy_coordinator import FetchResult, PolicyCoordinator, _header
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision, USER_AGENT
from crawler.processing.normalize.normalize import normalize_document
from crawler.processing.processing import process
from crawler.processing.schemas import ProcessingResult, SkipReason
from crawler.schedular.repository import complete_target, fail_target
from crawler.worker.jobs.utility import _add_x_robots, _create_discovered_targets, _finalize
from crawler.worker.jobs.constants import _HTML_MEDIA_TYPES
from crawler.writer.attempts import finish_attempt, start_attempt
from crawler.writer.documents import upsert_document

logger = logging.getLogger(__name__)








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
            attempt_id = await start_attempt(session, target_id)

    action: TargetAction = "retry"
    outcome: JobOutcome = "failed"
    message = "Unknown failure"
    http_status: int | None = None
    body_bytes = 0
    retry_after: float | None = None
    parsed: ParseResult | None = None
    processed: ProcessingResult | None = None
    new_targets: list[CrawlTargetCreate] = []

    if kind != "page":
        action, message = "disable", f"Unsupported target kind for HTML Worker: {kind}"
    else:
        try:
            coordinator = PolicyCoordinator(
                allowed_hosts=allowed_hosts,
                fetcher=fetcher if fetcher is not None else HTTPXHopFetcher(),
                politeness_manager=politeness_manager,
            )

            # Policy code uses PostgreSQL robots_cache. Commit cache entries
            # independently; no attempt/frontier/document transaction is open.
            # Current coordinator interface holds a DB transaction across fetch;
            # refactor policy-cache access separately when optimizing throughput.
            async with session_factory() as session:
                async with session.begin():
                    fetched: FetchResult = await coordinator.fetch(session, url)

            http_status = fetched.status_code
            body_bytes = len(fetched.body)
            retry_after = fetched.retry_after_seconds
            message = fetched.reason

            if fetched.decision == RobotsDecision.DENY:
                action, outcome = "block", "blocked"
            elif fetched.decision == RobotsDecision.DEFER:
                action, outcome = "retry", "failed"
            elif fetched.decision != RobotsDecision.ALLOW:
                raise RuntimeError(f"Unexpected policy decision: {fetched.decision!r}")
            elif http_status == 304:
                action, outcome = "complete", "not_modified"
            elif http_status in (401, 403):
                action, outcome = "block", "blocked"
            elif http_status in (204, 205):
                action, outcome = "complete", "success"
                message = f"HTTP {http_status}: no content"
            elif http_status in (404, 410):
                action, outcome = "disable", "failed"
                message = f"HTTP {http_status}: resource unavailable"
            elif http_status != 200:
                action, outcome = "retry", "failed"
                message = f"Unhandled HTTP status: {http_status}"
            else:
                content_type = _header(fetched.headers, "content-type") or ""
                mime_type = content_type.split(";", 1)[0].strip().casefold()
                if mime_type not in _HTML_MEDIA_TYPES:
                    # An accepted 200 non-HTML response is valid, but this job
                    # cannot parse/index it yet; schedule a normal recrawl.
                    action, outcome = "complete", "success"
                    message = f"Skipped unsupported MIME: {mime_type or '(none)'}"
                elif not fetched.body:
                    action, outcome = "retry", "failed"
                    message = "HTTP 200 HTML response had empty body"
                else:
                    parsed = parse(
                        url=fetched.final_url,
                        content=fetched.body,
                        content_type=content_type,
                    )
                    parsed = _add_x_robots(parsed, fetched.headers)
                    processed = process(parsed)
                    new_targets = _create_discovered_targets(
                        parsed,
                        target_id=target_id,
                        source_id=source_id,
                        allowed_hosts=allowed_hosts,
                        max_links=max_links,
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
            parsed, processed, new_targets = None, None, []

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
    )


__all__ = ["JobResult", "process_job"]
