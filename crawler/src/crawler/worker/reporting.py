"""Developer's Eye - read-only PostgreSQL crawler reporting (MVP).

Location:
    crawler/src/crawler/worker/reporting.py

This module reads EXISTING committed crawler records. It does not run jobs,
claim targets, recover leases, enqueue URLs, or modify the database.

It provides:
    build_report(session, ...)   -> JSON-serializable dictionary for an admin API
    format_text_report(report)  -> human-readable CLI summary
    main()                      -> one-off PostgreSQL report

Run from the repository root after setting PYTHONPATH:
    python -m crawler.worker.reporting
    python -m crawler.worker.reporting --days 7 --format json
    python -m crawler.worker.reporting --days 30 --output crawler-report.json

Future work (NOT implemented): Redis Pub/Sub, SSE, OpenTelemetry, Prometheus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import selectors
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import SessionFactory, engine
from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.robot_cache import RobotsCache
from backend.models.search_index import SearchIndex
from backend.models.source import Source


TargetState = Literal["queued", "leased", "blocked", "disabled"]
AttemptOutcome = Literal["success", "failed", "blocked", "not_modified", "unfinished"]

_TARGET_STATES: tuple[TargetState, ...] = ("queued", "leased", "blocked", "disabled")
_ATTEMPT_OUTCOMES: tuple[AttemptOutcome, ...] = (
    "success", "failed", "blocked", "not_modified", "unfinished",
)


def _utc(value: datetime | None) -> str | None:
    """Return ISO-8601 text; PostgreSQL timestamptz values are aware."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected a timezone-aware database timestamp")
    return value.astimezone(timezone.utc).isoformat()


def _percentage(numerator: int, denominator: int) -> float | None:
    """Return None rather than an invented 0% when there is no sample."""
    return round(100 * numerator / denominator, 2) if denominator else None


async def build_report(
    session: AsyncSession,
    *,
    days: int = 7,
    top_sources: int = 10,
    recent_errors: int = 10,
) -> dict[str, Any]:
    """Build an on-demand snapshot exclusively from committed PostgreSQL data.

    `days` means UTC calendar days INCLUDING today, rather than an exact
    rolling 24*days hour window. Counts are historical snapshots; they do not
    measure the live number of in-flight asyncio tasks.

    Caller owns the database session. No commit or DML is performed here.
    """
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")
    if not 1 <= top_sources <= 100:
        raise ValueError("top_sources must be between 1 and 100")
    if not 0 <= recent_errors <= 100:
        raise ValueError("recent_errors must be between 0 and 100")

    now = datetime.now(timezone.utc)
    first_day = now.date() - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)

    # ------------------------------------------------------------------
    # 1. Source registry: how many sources are registered and enabled?
    # ------------------------------------------------------------------
    source_counts = (
        await session.execute(
            select(
                func.count(Source.id),
                func.count(Source.id).filter(Source.is_enabled.is_(True)),
            )
        )
    ).one()
    sources_total, sources_enabled = map(int, source_counts)

    # ------------------------------------------------------------------
    # 2. Frontier: all targets, divided by their persisted state.
    # ------------------------------------------------------------------
    target_states = {state: 0 for state in _TARGET_STATES}
    for state, count in (
        await session.execute(
            select(CrawlTarget.state, func.count(CrawlTarget.id))
            .group_by(CrawlTarget.state)
        )
    ).all():
        target_states[str(state)] = int(count)

    target_counts = (
        await session.execute(
            select(
                func.count(CrawlTarget.id).filter(
                    and_(
                        CrawlTarget.state == "queued",
                        CrawlTarget.next_fetch_at <= now,
                    )
                ),
                func.count(CrawlTarget.id).filter(
                    and_(
                        CrawlTarget.state == "queued",
                        CrawlTarget.next_fetch_at > now,
                    )
                ),
                func.count(CrawlTarget.id).filter(
                    and_(
                        CrawlTarget.state == "leased",
                        CrawlTarget.lease_until > now,
                    )
                ),
                func.count(CrawlTarget.id).filter(
                    and_(
                        CrawlTarget.state == "leased",
                        (CrawlTarget.lease_until <= now)
                        | CrawlTarget.lease_until.is_(None),
                    )
                ),
            )
        )
    ).one()
    due, scheduled, active_leases, expired_leases = map(int, target_counts)

    # ------------------------------------------------------------------
    # 3. Document store and PostgreSQL full-text index state.
    # ------------------------------------------------------------------
    doc_totals = (
        await session.execute(
            select(
                func.count(Document.id),
                func.count(Document.id).filter(Document.last_seen_at >= since),
                func.count(Document.id).filter(Document.updated_at >= since),
                func.count(Document.id).filter(Document.is_available.is_(True)),
            )
        )
    ).one()
    docs_total, docs_seen, docs_updated, docs_available = map(int, doc_totals)

    index_totals = (
        await session.execute(
            select(
                func.count(SearchIndex.document_id),
                func.count(SearchIndex.document_id).filter(
                    SearchIndex.indexed_hash.is_distinct_from(Document.content_hash)
                ),
            )
            .join(Document, Document.id == SearchIndex.document_id)
            .where(Document.is_available.is_(True))
        )
    ).one()
    indexed_total, stale_indexes = map(int, index_totals)

    # ------------------------------------------------------------------
    # 4. Robots cache: known origins and freshness at report time.
    # ------------------------------------------------------------------
    robots_counts = (
        await session.execute(
            select(
                func.count(RobotsCache.origin),
                func.count(RobotsCache.origin).filter(RobotsCache.expires_at > now),
            )
        )
    ).one()
    robots_total, robots_valid = map(int, robots_counts)

    # ------------------------------------------------------------------
    # 5. Crawl attempts: outcomes during requested UTC calendar days.
    #    unfinished attempts have a NULL outcome in your existing schema.
    # ------------------------------------------------------------------
    attempt_counts = {outcome: 0 for outcome in _ATTEMPT_OUTCOMES}
    for outcome, count in (
        await session.execute(
            select(CrawlAttempt.outcome, func.count(CrawlAttempt.id))
            .where(CrawlAttempt.started_at >= since)
            .group_by(CrawlAttempt.outcome)
        )
    ).all():
        name = str(outcome) if outcome is not None else "unfinished"
        attempt_counts[name] = int(count)

    finished = sum(
        attempt_counts[key]
        for key in ("success", "failed", "blocked", "not_modified")
    )
    successful = attempt_counts["success"] + attempt_counts["not_modified"]

    last_activity = (
        await session.execute(
            select(
                func.max(CrawlAttempt.started_at),
                func.max(CrawlAttempt.finished_at).filter(
                    CrawlAttempt.outcome == "success"
                ),
            )
        )
    ).one()

    # ------------------------------------------------------------------
    # 6. Daily attempt volume for graphs (zero-filled UTC calendar days).
    # ------------------------------------------------------------------
    day_expression = func.date(func.timezone("UTC", CrawlAttempt.started_at))
    daily_rows = (
        await session.execute(
            select(
                day_expression.label("day"),
                func.count(CrawlAttempt.id).label("attempts"),
                func.count(CrawlAttempt.id).filter(
                    CrawlAttempt.outcome.in_(("success", "not_modified"))
                ).label("successful"),
                func.count(CrawlAttempt.id).filter(
                    CrawlAttempt.outcome == "failed"
                ).label("failed"),
                func.count(CrawlAttempt.id).filter(
                    CrawlAttempt.outcome == "blocked"
                ).label("blocked"),
            )
            .where(CrawlAttempt.started_at >= since)
            .group_by(day_expression)
            .order_by(day_expression)
        )
    ).all()
    by_day: dict[date, tuple[int, int, int, int]] = {
        row.day: (int(row.attempts), int(row.successful), int(row.failed), int(row.blocked))
        for row in daily_rows
    }
    daily: list[dict[str, int | str]] = []
    for step in range(days):
        day = first_day + timedelta(days=step)
        attempts, success, failed, blocked = by_day.get(day, (0, 0, 0, 0))
        daily.append({
            "date": day.isoformat(),
            "attempts": attempts,
            "successful": success,
            "failed": failed,
            "blocked": blocked,
        })

    # ------------------------------------------------------------------
    # 7. Source breakdown. PRE-aggregate child tables to avoid JOIN fan-out
    #    multiplying target, attempt and document counts.
    # ------------------------------------------------------------------
    per_target = (
        select(
            CrawlTarget.source_id.label("source_id"),
            func.count(CrawlTarget.id).label("targets"),
        )
        .group_by(CrawlTarget.source_id)
        .subquery()
    )
    per_document = (
        select(
            Document.source_id.label("source_id"),
            func.count(Document.id).label("documents"),
        )
        .group_by(Document.source_id)
        .subquery()
    )
    per_attempt = (
        select(
            CrawlTarget.source_id.label("source_id"),
            func.count(CrawlAttempt.id).label("attempts"),
            func.count(CrawlAttempt.id).filter(
                CrawlAttempt.outcome.in_(("success", "not_modified"))
            ).label("successful"),
            func.count(CrawlAttempt.id).filter(
                CrawlAttempt.outcome == "failed"
            ).label("failed"),
        )
        .join(CrawlTarget, CrawlTarget.id == CrawlAttempt.crawl_target_id)
        .where(CrawlAttempt.started_at >= since)
        .group_by(CrawlTarget.source_id)
        .subquery()
    )
    source_rows = (
        await session.execute(
            select(
                Source.id,
                Source.slug,
                Source.name,
                Source.kind,
                Source.is_enabled,
                func.coalesce(per_target.c.targets, 0).label("targets"),
                func.coalesce(per_document.c.documents, 0).label("documents"),
                func.coalesce(per_attempt.c.attempts, 0).label("attempts"),
                func.coalesce(per_attempt.c.successful, 0).label("successful"),
                func.coalesce(per_attempt.c.failed, 0).label("failed"),
            )
            .outerjoin(per_target, per_target.c.source_id == Source.id)
            .outerjoin(per_document, per_document.c.source_id == Source.id)
            .outerjoin(per_attempt, per_attempt.c.source_id == Source.id)
            .order_by(func.coalesce(per_target.c.targets, 0).desc(), Source.id)
            .limit(top_sources)
        )
    ).all()
    sources = [
        {
            "id": int(row.id),
            "slug": row.slug,
            "name": row.name,
            "kind": row.kind,
            "enabled": bool(row.is_enabled),
            "targets": int(row.targets),
            "documents": int(row.documents),
            "attempts": int(row.attempts),
            "successful": int(row.successful),
            "failed": int(row.failed),
        }
        for row in source_rows
    ]

    # ------------------------------------------------------------------
    # 8. Latest failed/blocked attempts with joined URL and source.
    # ------------------------------------------------------------------
    errors: list[dict[str, Any]] = []
    if recent_errors:
        error_rows = (
            await session.execute(
                select(
                    CrawlAttempt.id,
                    CrawlAttempt.crawl_target_id,
                    CrawlAttempt.started_at,
                    CrawlAttempt.finished_at,
                    CrawlAttempt.outcome,
                    CrawlAttempt.http_status,
                    CrawlAttempt.error_message,
                    CrawlTarget.fetch_url,
                    Source.slug,
                )
                .join(CrawlTarget, CrawlTarget.id == CrawlAttempt.crawl_target_id)
                .join(Source, Source.id == CrawlTarget.source_id)
                .where(
                    CrawlAttempt.started_at >= since,
                    CrawlAttempt.outcome.in_(("failed", "blocked")),
                )
                .order_by(CrawlAttempt.started_at.desc(), CrawlAttempt.id.desc())
                .limit(recent_errors)
            )
        ).all()
        errors = [
            {
                "attempt_id": int(row.id),
                "target_id": int(row.crawl_target_id),
                "source": row.slug,
                "url": row.fetch_url,
                "outcome": row.outcome,
                "http_status": row.http_status,
                "error": row.error_message,
                "started_at": _utc(row.started_at),
                "finished_at": _utc(row.finished_at),
            }
            for row in error_rows
        ]

    return {
        "generated_at": now.isoformat(),
        "window": {
            "days": days,
            "start_utc": since.isoformat(),
            "end_utc": now.isoformat(),
        },
        "sources": {
            "total": sources_total,
            "enabled": sources_enabled,
            "disabled": sources_total - sources_enabled,
        },
        "frontier": {
            "total": sum(target_states.values()),
            "by_state": target_states,
            "queued_due": due,
            "queued_scheduled": scheduled,
            "leases_active": active_leases,
            "leases_expired": expired_leases,
        },
        "documents": {
            "total": docs_total,
            "seen_in_window": docs_seen,
            "updated_in_window": docs_updated,
            "indexed": indexed_total,
            "not_indexed": max(0, docs_available - indexed_total),
            "unavailable": docs_total - docs_available,
            "stale_index_hashes": stale_indexes,
        },
        "robots_cache": {
            "origins": robots_total,
            "valid": robots_valid,
            "expired": robots_total - robots_valid,
        },
        "attempts": {
            "total_in_window": sum(attempt_counts.values()),
            "finished_in_window": finished,
            "by_outcome": attempt_counts,
            "success_rate_percent": _percentage(successful, finished),
            "last_attempt_at": _utc(last_activity[0]),
            "last_success_at": _utc(last_activity[1]),
        },
        "daily_attempts": daily,
        "top_sources": sources,
        "recent_errors": errors,
    }


def format_text_report(report: dict[str, Any]) -> str:
    """Print-friendly report; no additional database calls."""
    window = report["window"]
    sources = report["sources"]
    frontier = report["frontier"]
    documents = report["documents"]
    robots = report["robots_cache"]
    attempts = report["attempts"]
    by_state = frontier["by_state"]
    by_outcome = attempts["by_outcome"]
    pct = attempts["success_rate_percent"]

    lines = [
        "=" * 72,
        "DEVELOPER'S EYE | CRAWLER REPORT",
        "=" * 72,
        f"Generated: {report['generated_at']}",
        f"Attempt window (UTC): {window['start_utc']} to {window['end_utc']}",
        "",
        "SOURCE REGISTRY",
        f"  Total: {sources['total']} | Enabled: {sources['enabled']} | Disabled: {sources['disabled']}",
        "",
        "URL FRONTIER (CURRENT STATE)",
        f"  Total: {frontier['total']} | Queued: {by_state['queued']} | Leased: {by_state['leased']}",
        f"  Blocked: {by_state['blocked']} | Disabled: {by_state['disabled']}",
        f"  Ready now: {frontier['queued_due']} | Scheduled later: {frontier['queued_scheduled']}",
        f"  Leases active: {frontier['leases_active']} | Expired: {frontier['leases_expired']}",
        "",
        "DOCUMENTS & SEARCH INDEX",
        f"  Stored: {documents['total']} | Seen in window: {documents['seen_in_window']}",
        f"  Updated in window: {documents['updated_in_window']}",
        f"  Indexed: {documents['indexed']} | Not indexed: {documents['not_indexed']}",
        f"  Index hash stale: {documents['stale_index_hashes']}",
        "",
        "ROBOTS CACHE",
        f"  Origins: {robots['origins']} | Valid: {robots['valid']} | Expired: {robots['expired']}",
        "",
        "CRAWL ATTEMPTS (WINDOW)",
        f"  Total: {attempts['total_in_window']} | Finished: {attempts['finished_in_window']}",
        f"  Success: {by_outcome['success']} | Not modified: {by_outcome['not_modified']}",
        f"  Failed: {by_outcome['failed']} | Blocked: {by_outcome['blocked']}",
        f"  Unfinished: {by_outcome['unfinished']}",
        f"  Finished success rate: {str(pct) + '%' if pct is not None else 'N/A'}",
        f"  Last attempt: {attempts['last_attempt_at'] or 'N/A'}",
        f"  Last success: {attempts['last_success_at'] or 'N/A'}",
        "",
        "DAILY ATTEMPTS (UTC)",
    ]
    for day in report["daily_attempts"]:
        lines.append(
            f"  {day['date']}  attempts={day['attempts']}  "
            f"success={day['successful']}  failed={day['failed']}  blocked={day['blocked']}"
        )

    lines.extend(["", "TOP SOURCES (BY FRONTIER TARGET COUNT)"])
    if not report["top_sources"]:
        lines.append("  No sources registered.")
    for src in report["top_sources"]:
        lines.append(
            f"  {src['slug']} (id={src['id']}, enabled={src['enabled']}): "
            f"targets={src['targets']} docs={src['documents']} "
            f"attempts={src['attempts']} success={src['successful']} failed={src['failed']}"
        )

    lines.extend(["", "RECENT FAILED / BLOCKED ATTEMPTS"])
    if not report["recent_errors"]:
        lines.append("  No failed or blocked attempts in this window.")
    for item in report["recent_errors"]:
        lines.append(
            f"  #{item['attempt_id']} {item['outcome']} HTTP={item['http_status']} "
            f"source={item['source']} url={item['url']}"
        )
        if item["error"]:
            lines.append(f"    reason: {item['error']}")

    lines.extend(["", "NOTE: Read-only PostgreSQL snapshot. No work was dispatched."])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Developer's Eye crawler database reporting (read-only)"
    )
    parser.add_argument("--days", type=int, default=7, help="UTC calendar days including today (1-365)")
    parser.add_argument("--top-sources", type=int, default=10, help="Maximum sources to display (1-100)")
    parser.add_argument("--recent-errors", type=int, default=10, help="Maximum failures to display (0-100)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path, help="Optional path for report file")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> int:
    try:
        async with SessionFactory() as session:
            report = await build_report(
                session,
                days=args.days,
                top_sources=args.top_sources,
                recent_errors=args.recent_errors,
            )
        text = (
            json.dumps(report, indent=2, ensure_ascii=False)
            if args.format == "json"
            else format_text_report(report)
        )
        if args.output is not None:
            args.output.write_text(text + "\n", encoding="utf-8")
            print(f"Report saved: {args.output}")
        else:
            print(text)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    args = parse_args()
    if sys.platform == "win32":
        result = asyncio.run(
            main(args),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    else:
        result = asyncio.run(main(args))
    raise SystemExit(result)
