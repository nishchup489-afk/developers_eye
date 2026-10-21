from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


from backend.db.session import SessionFactory
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate
from crawler.fetcher.fetch import HTTPXHopFetcher
from crawler.fetcher.schemas import OneHopFetcher
from crawler.frontier.repository import enqueue_targets
from crawler.frontier.urls import normalize_url
from crawler.frontier.scope import CrawlScope, DEFAULT_MAX_PAGES
from crawler.parser.parser import parse
from crawler.parser.schemas import ParseResult
from crawler.policy_and_politeness.host_policy import is_allowed_host
from crawler.policy_and_politeness.policy_coordinator import FetchResult, PolicyCoordinator
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision, USER_AGENT
from crawler.processing.normalize.normalize import normalize_document
from crawler.processing.processing import process
from crawler.processing.schemas import ProcessingResult, SkipReason
from crawler.schedular.repository import complete_target, fail_target
from crawler.worker.jobs.schemas import JobOutcome, JobResult, TargetAction
from crawler.worker.jobs.constants import _AGENT_SCOPE, _DIRECTIVE_SPLIT, _RETRY_AFTER_CAP_SECONDS
from crawler.writer.attempts import finish_attempt, start_attempt
from crawler.writer.documents import upsert_document
from backend.models.crawl_attempt import CrawlAttempt
from crawler.worker.telemetry import event


def _header(headers: dict[str, str], name: str) -> str | None:
    """Response headers are case-insensitive."""
    return next((value for key, value in headers.items() if key.casefold() == name.casefold()),
                None)


def _x_robots_directives(headers: dict[str, str]) -> tuple[str, ...]:
    """Read noindex/nofollow/none from unscoped or own-bot X-Robots-Tag.

    This is an MVP directive parser, not a complete X-Robots-Tag implementation.
    A comma-separated agent scope is carried to following tokens.
    """
    raw = _header(headers, "x-robots-tag")
    if not raw:
        return ()

    own_bot = USER_AGENT.split("/", 1)[0].casefold()
    scope: str | None = None
    found: list[str] = []
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


def _add_x_robots(parsed: ParseResult, headers: dict[str, str]) -> ParseResult:
    """Merge response-header directives into parsed-document metadata."""
    directives = _x_robots_directives(headers)
    if not directives:
        return parsed
    updated = []
    for document in parsed.documents:
        metadata = dict(document.metadata)
        existing = metadata.get("robots_directives", ())
        if isinstance(existing, str):
            existing = (existing,)
        if not isinstance(existing, (tuple, list, set, frozenset)):
            existing = ()
        metadata["robots_directives"] = [
            *[value for value in existing if isinstance(value, str)],
            *directives,
        ]
        updated.append(replace(document, metadata=metadata))
    return replace(parsed, documents=tuple(updated))


def _page_nofollow(parsed: ParseResult) -> bool:
    """A page-wide robots nofollow directive prevents link discovery enqueueing."""
    for document in parsed.documents:
        raw = document.metadata.get("robots_directives", ())
        if isinstance(raw, str):
            raw = (raw,)
        if not isinstance(raw, (tuple, list, set, frozenset)):
            continue
        tokens = {
            directive
            for value in raw if isinstance(value, str)
            for directive in _DIRECTIVE_SPLIT.split(value.casefold())
        }
        if tokens & {"nofollow", "none"}:
            return True
    return False


def _create_discovered_targets(
    parsed: ParseResult,
    *,
    target_id: int,
    source_id: int,
    allowed_hosts: tuple[str, ...],
    max_links: int,
    parent_depth: int = 0,
    scope: CrawlScope | None = None,
    target_kind: str = "page",
) -> list[CrawlTargetCreate]:
    """Create only in-scope, followed URL candidates; no DNS/network here."""
    scope = scope or CrawlScope()
    if _page_nofollow(parsed):
        return []

    output: list[CrawlTargetCreate] = []
    seen: set[str] = set()
    for link in parsed.discovered_links:
        if link.nofollow:
            continue
        try:
            normalized = normalize_url(link.url)
        except (ValueError, TypeError):
            continue
        if normalized in seen or not is_allowed_host(normalized, list(allowed_hosts)):
            continue
        is_seed = (target_kind == "sitemap" and link.kind == "page") or (target_kind != "sitemap" and link.kind == "sitemap")
        depth = 0 if is_seed else parent_depth + 1
        if depth > scope.max_depth or (link.kind == "page" and not scope.allows(normalized, depth)):
            continue
        seen.add(normalized)
        output.append(CrawlTargetCreate(
            source_id=source_id,
            fetch_url=normalized,
            normalized_url=normalized,
            kind=link.kind,
            discovered_from_id=target_id,
            depth=depth,
        ))
        if len(output) >= max_links:
            break
    return output


def _noindex_urls(parsed: ParseResult, processed: ProcessingResult) -> set[str]:
    """Remove indexed copies of pages that now explicitly forbid indexing.

    Existing canonical identity hints are included when safely normalized.
    The schema does not currently record full canonical-URL alias history.
    """
    rejected = {s.url for s in processed.skipped if s.reason == SkipReason.NOINDEX}
    urls: set[str] = set()
    for document in parsed.documents:
        if document.url not in rejected:
            continue
        try:
            normalized = normalize_document(document)
            urls.update({normalized.url, normalized.canonical_url})
        except (ValueError, TypeError):
            continue
    return urls


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
    measurements: dict | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> JobResult:
    """Atomically transition the target and persist all related job output.

    Lease ownership is checked twice: first with FOR UPDATE, then inside
    scheduler's conditional UPDATE. If it was lost, no documents/links write.
    """
    documents_saved = 0
    links_enqueued = 0
    skipped = len(processed.skipped) if processed else 0
    discovered = len(parsed.discovered_links) if parsed else 0
    storage_started = time.perf_counter()
    measurements = dict(measurements or {})
    measurements["documents"] = []

    async with session_factory() as session:
        async with session.begin():
            row = await session.scalar(
                select(CrawlTarget)
                .where(CrawlTarget.id == target_id)
                .with_for_update()
            )
            database_now = await session.scalar(select(func.clock_timestamp()))
            active = (
                row is not None
                and row.source_id == source_id
                and row.state == "leased"
                and row.lease_until == expected_lease_until
                and row.lease_until is not None
                and row.lease_until > database_now
            )
            if active:
                # A source may have been disabled during the HTTP request.
                enabled = await session.scalar(
                    select(Source.is_enabled).where(Source.id == source_id)
                )
                if not enabled:
                    action = "disable"
                    outcome = "disabled"
                    message = "Source was disabled while job was running"
                    parsed = None
                    processed = None
                    targets = []

            if not active:
                measurements.update(result="stale", reason="Lease lost or expired; output discarded")
                await session.execute(update(CrawlAttempt).where(CrawlAttempt.id == attempt_id, CrawlAttempt.finished_at.is_(None)).values(telemetry=measurements))
                event(session, attempt_id, "FINALIZE", "stale", {"reason": "Lease lost or expired; output discarded"})
                # The attempt belongs to this job, so it is safe to finish.
                # No document/URL writes are made after losing the lease.
                await finish_attempt(
                    session, attempt_id, "failed", http_status=http_status,
                    bytes_received=body_bytes,
                    error_message="Lease lost or expired; discarded stale crawl result",
                )
                return JobResult(
                    target_id=target_id, attempt_id=attempt_id, outcome="stale",
                    http_status=http_status, message="Lease expired or was reassigned",
                    duration_seconds=elapsed,
                )

            # The target is row-locked. Validate/transition it before the writes.
            if action == "complete":
                transitioned = await complete_target(
                    session, target_id, expected_lease_until, interval_seconds,
                )
            elif action == "retry":
                transitioned = await fail_target(
                    session, target_id, expected_lease_until,
                )
                if transitioned and retry_after_seconds is not None:
                    wait = max(0, min(int(retry_after_seconds), _RETRY_AFTER_CAP_SECONDS))
                    await session.execute(
                        update(CrawlTarget)
                        .where(CrawlTarget.id == target_id)
                        .values(next_fetch_at=func.greatest(
                            CrawlTarget.next_fetch_at,
                            func.clock_timestamp() + func.make_interval(
                                0, 0, 0, 0, 0, 0, wait
                            ),
                        ))
                    )
            else:
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

            if not transitioned:
                measurements.update(result="stale", reason="Lease expired before target transition")
                await session.execute(update(CrawlAttempt).where(CrawlAttempt.id == attempt_id, CrawlAttempt.finished_at.is_(None)).values(telemetry=measurements))
                event(session, attempt_id, "FINALIZE", "stale", {"reason": "Lease expired before target transition"})
                await finish_attempt(
                    session, attempt_id, "failed", http_status=http_status,
                    bytes_received=body_bytes,
                    error_message="Lease expired before target transition",
                )
                return JobResult(
                    target_id=target_id, attempt_id=attempt_id, outcome="stale",
                    http_status=http_status,
                    message="Lease expired before completion",
                    duration_seconds=elapsed,
                )

            if action == "complete" and http_status in (404, 410):
                unavailable_ids = (await session.scalars(update(Document).where(
                    Document.last_crawl_target_id == target_id,
                ).values(is_available=False, unavailable_http_status=http_status,
                    unavailable_at=func.coalesce(Document.unavailable_at, func.clock_timestamp()))
                    .returning(Document.id))).all()
                if unavailable_ids:
                    await session.execute(delete(SearchIndex).where(SearchIndex.document_id.in_(unavailable_ids)))
                event(session, attempt_id, "STORE", "not_stored", {
                    "unavailable_document_ids": unavailable_ids, "http_status": http_status,
                    "reason": "Stored content retained as unavailable; search entries removed",
                })

            if action == "complete" and parsed is not None and processed is not None:
                noindex = _noindex_urls(parsed, processed)
                if noindex:
                    await session.execute(
                        delete(Document).where(Document.canonical_url.in_(noindex))
                    )
                # Serialize observations of the same identity/hash across workers.
                lock_keys = sorted({key for d in processed.documents for key in
                                    ("canonical:" + d.canonical_url, "content:" + d.content_hash)})
                for key in lock_keys:
                    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
                for document in processed.documents:
                    previous = await session.scalar(select(Document).where(Document.canonical_url == document.canonical_url))
                    duplicate = await session.scalar(select(Document.id).where(
                        Document.content_hash == document.content_hash,
                        Document.canonical_url != document.canonical_url).limit(1))
                    decision = "unchanged" if previous and previous.content_hash == document.content_hash else "updated" if previous else "new"
                    event(session, attempt_id, "DEDUP", "duplicate" if duplicate else decision,
                          {"canonical_url": document.canonical_url, "matching_document_id": duplicate,
                           "decision": decision, "content_hash": document.content_hash,
                           "reason": "Matching content at another canonical URL; retained by current writer" if duplicate else "Canonical URL content hash comparison"})
                    document_id = await upsert_document(
                        session, document,
                        source_id=source_id,
                        crawl_target_id=target_id,
                    )
                    documents_saved += 1
                    measurements["documents"].append({"id": document_id, "decision": decision,
                                                       "duplicate_of": duplicate, "canonical_url": document.canonical_url})
                if targets:
                    links_enqueued = await enqueue_targets(session, targets, max_pages=max_pages)

            measurements.update(stored=documents_saved, links_discovered=discovered,
                                links_enqueued=links_enqueued, storage_ms=round((time.perf_counter() - storage_started) * 1000, 2),
                                result=outcome, reason=message, target_action=action)
            await session.execute(update(CrawlAttempt).where(CrawlAttempt.id == attempt_id).values(telemetry=measurements))
            event(session, attempt_id, "STORE", "persisted" if documents_saved else "not_stored",
                  {"documents": measurements["documents"], "duration_ms": measurements["storage_ms"], "reason": message})
            if parsed is not None:
                event(session, attempt_id, "DISCOVER", "complete", {"discovered": discovered, "enqueued": links_enqueued})
            event(session, attempt_id, "FINALIZE", outcome, {"reason": message, "action": action})

            # All operations above use this same transaction. Errors roll back
            # target transition, documents, link insertions and attempt update.
            done = await finish_attempt(
                session, attempt_id,
                outcome if outcome in {"success", "failed", "blocked", "not_modified"} else "blocked",
                http_status=http_status,
                bytes_received=body_bytes,
                error_message=message if outcome not in {"success", "not_modified"} else None,
            )
            if not done:
                raise RuntimeError(f"Attempt {attempt_id} missing or already finished")

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

