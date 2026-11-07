"""Read-only capacity, politeness and problem reporting for the admin dashboard.

Three builders share one module because they read the same PostgreSQL
catalogs and crawl tables:

- build_system_report: database size against the disk budget, a projection to
  the document goal, crawl progress and ETA, per-source yield, telemetry age.
- build_host_report: request rate and throttling per host across all workers.
- build_problems: rule checks that the dashboard banner and the alert job show.

Nothing here writes, locks or runs work. Row counts for large tables use the
planner estimate (pg_class.reltuples) so a 5M-row table is not scanned on
every refresh.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, Integer, and_, cast, func, or_, select, text

from backend.admin_services.crawler_reporting import _percentage, _utc
from backend.core.config import settings
from backend.models.crawl_attempt import CrawlAttempt as Attempt
from backend.models.crawl_monitor import CrawlEvent as Event, CrawlWorker, IndexerWorker
from backend.models.crawler_frontier import CrawlTarget as Target
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.search_minute import SearchMinute
from backend.models.search_terms import SearchTerm
from backend.models.source import Source

GB = 1024 ** 3
HEARTBEAT_STALE = timedelta(seconds=120)
WORKER_ONLINE = timedelta(seconds=20)
BUDGET_WARN = 0.8
BUDGET_CRITICAL = 0.95
HOST_LIMIT = 50


def _round(value, digits=2):
    return round(float(value), digits) if value is not None else None


def host_expression(column):
    # Scheme-qualified URLs only; the frontier never stores relative URLs.
    return func.lower(func.substring(column, r"^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^@/]*@)?([^/:?#]+)"))


def _budget(db_bytes: int, documents: int, *, budget_gb: float, target: int):
    budget = int(budget_gb * GB)
    per_doc = db_bytes / documents if documents else None
    projected = int(per_doc * target) if per_doc else None
    used = db_bytes / budget if budget else None
    if used is not None and used >= BUDGET_CRITICAL:
        status = "critical"
    elif (used is not None and used >= BUDGET_WARN) or (projected is not None and projected > budget):
        status = "warning"
    else:
        status = "ok"
    return dict(
        budget_bytes=budget, used_bytes=db_bytes, used_percent=_percentage(db_bytes, budget) if budget else None,
        warn_at_bytes=int(budget * BUDGET_WARN), target_documents=target,
        bytes_per_document=_round(per_doc), target_bytes_per_document=_round(budget / target) if target else None,
        projected_bytes_at_target=projected,
        projected_percent_of_budget=_percentage(projected, budget) if projected is not None and budget else None,
        documents_that_fit=int(budget / per_doc) if per_doc else None, status=status)


async def _table_sizes(session):
    rows = (await session.execute(text("""
        SELECT c.relname AS name,
               pg_total_relation_size(c.oid) AS total_bytes,
               pg_relation_size(c.oid) AS heap_bytes,
               pg_indexes_size(c.oid) AS index_bytes,
               COALESCE(pg_total_relation_size(NULLIF(c.reltoastrelid, 0)), 0) AS toast_bytes,
               GREATEST(c.reltuples, 0)::bigint AS estimated_rows,
               COALESCE(s.n_dead_tup, 0) AS dead_rows,
               GREATEST(s.last_autovacuum, s.last_vacuum) AS last_vacuum_at,
               GREATEST(s.last_autoanalyze, s.last_analyze) AS last_analyze_at
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p')
        ORDER BY total_bytes DESC, c.relname
        LIMIT 30"""))).mappings().all()
    return [dict(row, last_vacuum_at=_utc(row["last_vacuum_at"]), last_analyze_at=_utc(row["last_analyze_at"]),
                 dead_percent=_percentage(row["dead_rows"], row["dead_rows"] + row["estimated_rows"]))
            for row in rows]


async def _slow_queries(session):
    # Only when the extension is both created and preloaded; otherwise the view errors.
    enabled = await session.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements')
           AND current_setting('shared_preload_libraries') LIKE '%pg_stat_statements%'"""))
    if not enabled:
        return None
    rows = (await session.execute(text("""
        SELECT left(regexp_replace(query, '\\s+', ' ', 'g'), 240) AS query, calls,
               round(mean_exec_time::numeric, 2)::float AS mean_ms,
               round(total_exec_time::numeric, 0)::float AS total_ms
        FROM pg_stat_statements
        WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
        ORDER BY total_exec_time DESC LIMIT 10"""))).mappings().all()
    return [dict(row) for row in rows]


async def build_system_report(session, *, days: int = 7):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    db_bytes = int(await session.scalar(text("SELECT pg_database_size(current_database())")))
    connections = (await session.execute(text("""
        SELECT count(*) FILTER (WHERE datname = current_database()) AS used,
               count(*) FILTER (WHERE datname = current_database() AND state = 'active') AS active,
               current_setting('max_connections')::int AS max
        FROM pg_stat_activity"""))).mappings().one()
    documents = dict((await session.execute(select(
        func.count(Document.id).label("total"),
        func.count(Document.id).filter(Document.is_available.is_(True)).label("available"),
    ))).mappings().one())
    tables = await _table_sizes(session)
    by_name = {t["name"]: t for t in tables}
    per_document = {name: _round(by_name[name]["total_bytes"] / documents["total"]) if documents["total"] and name in by_name else None
                    for name in ("document", "search_index", "search_terms", "crawl_attempt", "crawl_event", "crawl_target")}

    # A DEDUP "new" checkpoint is the one moment a document row is first created.
    new_docs = lambda start: select(func.count(Event.id)).where(  # noqa: E731
        Event.stage == "DEDUP", Event.outcome == "new", Event.created_at >= start)
    new_24h = int(await session.scalar(new_docs(now - timedelta(days=1))))
    new_1h = int(await session.scalar(new_docs(now - timedelta(hours=1))))
    target = settings.admin_target_documents
    remaining = max(0, target - documents["total"])
    eta_days = round(remaining / new_24h, 1) if new_24h and remaining else (0 if not remaining else None)
    progress = dict(target_documents=target, documents=documents["total"], available_documents=documents["available"],
                    percent=_percentage(documents["total"], target), new_last_hour=new_1h, new_last_24h=new_24h,
                    per_day=new_24h, remaining=remaining, eta_days=eta_days,
                    eta_at=_utc(now + timedelta(days=eta_days)) if eta_days else None)

    stored = cast(Attempt.telemetry["stored"].astext, Integer)
    yield_rows = (await session.execute(select(
        Source.id, Source.slug, Source.name, Source.is_enabled,
        func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(stored > 0).label("stored_attempts"),
        func.count(Attempt.id).filter(Attempt.outcome == "failed").label("failed"),
        func.count(Attempt.id).filter(Attempt.outcome == "blocked").label("blocked"),
        func.coalesce(func.sum(Attempt.bytes_received), 0).label("bytes_received"))
        .select_from(Source).outerjoin(Target, Target.source_id == Source.id)
        .outerjoin(Attempt, and_(Attempt.crawl_target_id == Target.id, Attempt.started_at >= since))
        .group_by(Source.id).order_by(Source.name))).mappings().all()
    doc_rows = {row[0]: tuple(row[1:]) for row in (await session.execute(select(
        Document.source_id, func.count(Document.id), func.count(func.distinct(Document.content_hash)),
        func.avg(func.length(Document.body))).group_by(Document.source_id))).all()}
    sources = []
    for row in yield_rows:
        docs, distinct, avg_body = doc_rows.get(row["id"], (0, 0, None))
        sources.append(dict(id=row["id"], slug=row["slug"], name=row["name"], enabled=bool(row["is_enabled"]),
            attempts=row["attempts"], stored_attempts=row["stored_attempts"], failed=row["failed"], blocked=row["blocked"],
            bytes_received=int(row["bytes_received"]), documents=docs, duplicate_documents=docs - distinct,
            duplicate_percent=_percentage(docs - distinct, docs), average_body_characters=_round(avg_body, 0),
            yield_percent=_percentage(row["stored_attempts"], row["attempts"])))

    retention_days = settings.admin_event_retention_days
    oldest_event = await session.scalar(select(func.min(Event.created_at)))
    expired_events = int(await session.scalar(select(func.count(Event.id)).where(
        Event.created_at < now - timedelta(days=retention_days))))

    return dict(
        version=1, generated_at=_utc(now), window_days=days,
        database=dict(size_bytes=db_bytes, connections_used=connections["used"],
                      connections_active=connections["active"], connections_max=connections["max"]),
        budget=_budget(db_bytes, documents["total"], budget_gb=settings.admin_db_budget_gb, target=target),
        per_document_bytes=per_document, tables=tables, progress=progress, sources=sources,
        telemetry=dict(retention_days=retention_days, oldest_event_at=_utc(oldest_event),
                       events_past_retention=expired_events,
                       estimated_event_rows=by_name.get("crawl_event", {}).get("estimated_rows", 0)),
        slow_queries=await _slow_queries(session),
    )


async def _online_crawlers(session, now):
    return int(await session.scalar(select(func.count(CrawlWorker.id)).where(
        CrawlWorker.stopped_at.is_(None), CrawlWorker.heartbeat_at >= now - WORKER_ONLINE)))


async def build_host_report(session, *, minutes: int = 60):
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=minutes)
    recent = now - timedelta(minutes=5)
    host = host_expression(Target.fetch_url).label("host")
    error_category = Attempt.telemetry["error_category"].astext
    rows = (await session.execute(select(
        host,
        func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(Attempt.started_at >= recent).label("attempts_last_5m"),
        func.count(Attempt.id).filter(or_(Attempt.http_status.between(200, 299), Attempt.http_status == 304)).label("successful"),
        func.count(Attempt.id).filter(Attempt.http_status == 429).label("http_429"),
        func.count(Attempt.id).filter(Attempt.http_status == 503).label("http_503"),
        func.count(Attempt.id).filter(Attempt.http_status.between(500, 599)).label("http_5xx"),
        func.count(Attempt.id).filter(Attempt.http_status.between(400, 499)).label("http_4xx"),
        func.count(Attempt.id).filter(Attempt.outcome == "blocked").label("blocked"),
        func.count(Attempt.id).filter(error_category == "timeout").label("timeouts"),
        func.count(func.distinct(Target.source_id)).label("sources"),
        func.avg(cast(Attempt.telemetry["fetch_ms"].astext, Float)).label("avg_fetch_ms"),
        func.max(Attempt.started_at).label("last_attempt_at"))
        .join(Target, Target.id == Attempt.crawl_target_id)
        .where(Attempt.started_at >= since).group_by(host)
        .order_by(func.count(Attempt.id).desc(), host).limit(HOST_LIMIT))).mappings().all()
    total = sum(r["attempts"] for r in rows)
    polite_per_minute = round(60 / settings.admin_host_min_interval_seconds, 2) if settings.admin_host_min_interval_seconds > 0 else None
    hosts = []
    for r in rows:
        per_minute = round(r["attempts_last_5m"] / 5, 2)
        share = _percentage(r["attempts"], total)
        flags = []
        if polite_per_minute and per_minute > polite_per_minute:
            flags.append("over_rate")
        if r["http_429"] or r["http_503"]:
            flags.append("throttled")
        if len(rows) > 1 and share is not None and share > 50:
            flags.append("hot")
        hosts.append(dict(host=r["host"] or "(unknown)", attempts=r["attempts"], attempts_last_5m=r["attempts_last_5m"],
            requests_per_minute=per_minute, share_percent=share, successful=r["successful"],
            http_429=r["http_429"], http_503=r["http_503"], http_4xx=r["http_4xx"], http_5xx=r["http_5xx"],
            blocked=r["blocked"], timeouts=r["timeouts"], sources=r["sources"],
            avg_fetch_ms=_round(r["avg_fetch_ms"]), last_attempt_at=_utc(r["last_attempt_at"]), flags=flags))
    workers = await _online_crawlers(session, now)
    return dict(version=1, generated_at=_utc(now), window_minutes=minutes, total_attempts=total,
                min_interval_seconds=settings.admin_host_min_interval_seconds,
                polite_requests_per_minute=polite_per_minute, online_workers=workers,
                # Politeness is enforced inside each process, so N workers can reach N times the polite rate.
                worst_case_requests_per_minute=round(polite_per_minute * workers, 2) if polite_per_minute else None,
                hosts=hosts)


def _problem(id, severity, title, detail):
    return dict(id=id, severity=severity, title=title, detail=detail)


async def build_problems(session):
    """Cheap rule checks: each one is an indexed lookup or a bounded aggregate."""
    now = datetime.now(timezone.utc)
    problems = []

    crashed = (await session.scalars(select(CrawlWorker).where(
        CrawlWorker.stopped_at.is_(None), CrawlWorker.heartbeat_at < now - HEARTBEAT_STALE,
        CrawlWorker.heartbeat_at >= now - timedelta(days=1)))).all()
    if crashed:
        names = ", ".join(sorted(f"{w.hostname}:{w.pid}" for w in crashed)[:5])
        problems.append(_problem("crawler_heartbeat_stale", "warning", f"{len(crashed)} crawler worker(s) stopped without shutting down",
                                 f"No heartbeat for over 2 minutes and no clean stop: {names}."))
    online = await _online_crawlers(session, now)
    due = int(await session.scalar(select(func.count(Target.id)).where(Target.state == "queued", Target.next_fetch_at <= now)))
    if due and not online:
        problems.append(_problem("crawler_offline", "info", "No crawler worker is online",
                                 f"{due:,} targets are due. Start a crawler worker to work through them."))
    expired = int(await session.scalar(select(func.count(Target.id)).where(
        Target.state == "leased", or_(Target.lease_until <= now, Target.lease_until.is_(None)))))
    if expired >= 10:
        problems.append(_problem("leases_expired", "warning", f"{expired:,} leases have expired",
                                 "Workers claimed these targets and did not finish. Recovery reclaims them on the next claim."))

    indexers = (await session.scalars(select(IndexerWorker).where(IndexerWorker.heartbeat_at >= now - timedelta(days=1)))).all()
    stale_indexers = [w for w in indexers if w.stopped_at is None and w.heartbeat_at < now - HEARTBEAT_STALE]
    if stale_indexers:
        problems.append(_problem("indexer_heartbeat_stale", "warning", "The indexer stopped without shutting down",
                                 f"{len(stale_indexers)} indexer process(es) have not sent a heartbeat for over 2 minutes."))
    last_indexed = await session.scalar(select(func.max(SearchIndex.indexed_at)))
    last_change = await session.scalar(select(func.max(Document.updated_at)).where(Document.is_available.is_(True)))
    if last_change and (last_indexed is None or last_change - last_indexed > timedelta(minutes=30)):
        lag = "never ran" if last_indexed is None else f"is {int((last_change - last_indexed).total_seconds() // 60)} minutes behind the crawler"
        problems.append(_problem("indexer_behind", "warning", "The search index is falling behind", f"The indexer {lag}."))

    db_bytes = int(await session.scalar(text("SELECT pg_database_size(current_database())")))
    documents = int(await session.scalar(select(func.count(Document.id))))
    budget = _budget(db_bytes, documents, budget_gb=settings.admin_db_budget_gb, target=settings.admin_target_documents)
    if budget["status"] == "critical":
        problems.append(_problem("disk_budget_critical", "critical", f"Database is at {budget['used_percent']}% of its disk budget",
                                 f"{db_bytes / GB:.1f} GB of {settings.admin_db_budget_gb:g} GB used."))
    elif budget["used_percent"] is not None and budget["used_percent"] >= BUDGET_WARN * 100:
        problems.append(_problem("disk_budget_warning", "warning", f"Database is at {budget['used_percent']}% of its disk budget",
                                 f"{db_bytes / GB:.1f} GB of {settings.admin_db_budget_gb:g} GB used."))
    if budget["projected_bytes_at_target"] and budget["projected_bytes_at_target"] > budget["budget_bytes"]:
        problems.append(_problem("disk_projection_over", "warning", "The document goal will not fit the disk budget",
            f"At {budget['bytes_per_document'] / 1024:.1f} KB per document, {settings.admin_target_documents:,} documents need "
            f"{budget['projected_bytes_at_target'] / GB:.0f} GB. The budget allows {budget['target_bytes_per_document'] / 1024:.1f} KB per document."))

    hour = now - timedelta(hours=1)
    error_rows = (await session.execute(select(Source.name, func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(Attempt.outcome.in_(("failed", "blocked"))).label("errors"))
        .join(Target, Target.id == Attempt.crawl_target_id).join(Source, Source.id == Target.source_id)
        .where(Attempt.started_at >= hour).group_by(Source.name))).all()
    for name, attempts, errors in error_rows:
        if attempts >= 20 and errors / attempts > 0.2:
            problems.append(_problem(f"source_errors:{name}", "warning", f"{name}: {round(100 * errors / attempts)}% of attempts failed in the last hour",
                                     f"{errors} of {attempts} attempts failed or were blocked."))
    throttled_host = host_expression(Target.fetch_url).label("host")
    throttled = (await session.execute(select(throttled_host, func.count(Attempt.id))
        .join(Target, Target.id == Attempt.crawl_target_id)
        .where(Attempt.started_at >= hour, Attempt.http_status.in_((429, 503)))
        .group_by(throttled_host).order_by(func.count(Attempt.id).desc()).limit(5))).all()
    if throttled:
        problems.append(_problem("hosts_throttling", "warning", "Hosts are rate limiting the crawler",
                                 "HTTP 429/503 in the last hour: " + ", ".join(f"{h} ({c})" for h, c in throttled) + "."))

    indexed = int(await session.scalar(select(func.count(SearchIndex.document_id))))
    overcounted = int(await session.scalar(select(func.count(SearchTerm.term)).where(SearchTerm.document_frequency > indexed)))
    if overcounted:
        problems.append(_problem("vocabulary_overcount", "warning", f"{overcounted:,} vocabulary terms are overcounted",
                                 "A term cannot appear in more documents than are indexed. Rebuild the vocabulary."))

    # The table is missing until its migration runs, and a failed query would end this transaction.
    if await session.scalar(text("SELECT to_regclass('search_minute') IS NOT NULL")):
        failure_columns = (SearchMinute.busy, SearchMinute.timed_out, SearchMinute.database_errors,
                           SearchMinute.engine_errors, SearchMinute.server_errors)
        successful, failed = (await session.execute(select(
            func.coalesce(func.sum(SearchMinute.successful), 0),
            func.coalesce(func.sum(sum(failure_columns)), 0)).where(SearchMinute.minute >= now - timedelta(minutes=15)))).one()
        if failed and successful + failed >= 5 and failed / (successful + failed) > 0.01:
            problems.append(_problem("search_failures", "critical" if failed > successful else "warning",
                                     f"{failed:,} of {successful + failed:,} searches failed in the last 15 minutes",
                                     "See the Availability page for timeouts, busy rejections and database errors."))

    retention = settings.admin_event_retention_days
    old_events = await session.scalar(select(func.min(Event.created_at)))
    if old_events and old_events < now - timedelta(days=retention * 1.5):
        problems.append(_problem("telemetry_retention", "info", "Old crawl events are using disk",
            f"Events older than {retention} days remain. Run: python -m backend.admin_services.maintenance --purge-events"))

    order = {"critical": 0, "warning": 1, "info": 2}
    problems.sort(key=lambda p: (order[p["severity"]], p["id"]))
    return dict(version=1, generated_at=_utc(now), problems=problems,
                counts={level: sum(p["severity"] == level for p in problems) for level in order})
