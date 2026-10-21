"""Read-only monitoring queries. Every stage count comes from worker checkpoints."""
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import Boolean, Float, Integer, and_, case, cast, func, or_, select

from backend.models.crawl_attempt import CrawlAttempt as Attempt
from backend.models.crawl_monitor import CrawlEvent as Event, CrawlWorker as Worker
from backend.models.crawler_frontier import CrawlTarget as Target
from backend.models.documents import Document
from backend.models.source import Source
from backend.services.crawler_reporting import _utc


def measurement(key, kind=Integer):
    return cast(Attempt.telemetry[key].astext, kind)


def event_dict(event, target, source):
    return dict(id=event.id, attempt_id=event.attempt_id, target_id=target.id,
                worker_id=event.worker_id, at=_utc(event.created_at), source=source.slug,
                source_id=source.id, url=target.fetch_url, stage=event.stage,
                outcome=event.outcome, details=event.details)


def document_summary(document, source):
    return dict(id=document.id, source=source.slug, title=document.title,
                canonical_url=document.canonical_url, document_type=document.document_type,
                last_seen_at=_utc(document.last_seen_at), is_available=document.is_available,
                unavailable_at=_utc(document.unavailable_at), unavailable_http_status=document.unavailable_http_status)


async def build_monitor(session, *, days=7, source_id=None, status=None, category=None,
                        q="", document_page=0, frontier_page=0, frontier_state=None, before_event_id=None):
    now = datetime.now(timezone.utc)
    since = datetime.combine(now.date() - timedelta(days=days - 1), time.min, timezone.utc)
    window = [Attempt.started_at >= since]
    if source_id:
        window.append(Target.source_id == source_id)
    # Aggregate in PostgreSQL, never download all attempts to calculate percentiles.
    summary = (await session.execute(select(
        func.count(Attempt.id).label("attempted"),
        func.count(Attempt.id).filter(Attempt.telemetry.is_not(None)).label("instrumented"),
        func.count(Attempt.id).filter(measurement("fetch_success", Boolean).is_(True)).label("fetched"),
        func.count(Attempt.id).filter(measurement("parsed", Boolean).is_(True)).label("parsed"),
        func.count(Attempt.id).filter(measurement("accepted") > 0).label("accepted"),
        func.count(Attempt.id).filter(measurement("stored") > 0).label("persisted"),
        func.count(Attempt.id).filter(Attempt.finished_at.is_(None)).label("unfinished"),
        func.count(Attempt.id).filter(Attempt.http_status.is_not(None)).label("http_responses"),
        func.count(Attempt.id).filter(or_(Attempt.http_status.between(200, 299), Attempt.http_status == 304)).label("http_successes"),
        func.percentile_cont(0.5).within_group(measurement("fetch_ms", Float)).label("fetch_p50_ms"),
        func.percentile_cont(0.95).within_group(measurement("fetch_ms", Float)).label("fetch_p95_ms"),
        func.avg(measurement("storage_ms", Float)).label("storage_avg_ms"),
        func.avg(Attempt.bytes_received).label("response_avg_bytes"),
        func.count(measurement("fetch_ms", Float)).label("fetch_samples"),
    ).join(Target, Target.id == Attempt.crawl_target_id).where(*window))).mappings().one()
    summary = dict(summary)
    for key in ("fetch_p50_ms", "fetch_p95_ms", "storage_avg_ms", "response_avg_bytes"):
        summary[key] = round(float(summary[key]), 2) if summary[key] is not None else None
    summary["historical_uninstrumented"] = summary["attempted"] - summary["instrumented"]
    summary["fetch_success_percent"] = round(100 * summary["http_successes"] / summary["http_responses"], 2) if summary["http_responses"] else None

    # An exact rolling 60-minute series, including partial current minute.
    minute = func.date_trunc("minute", Attempt.started_at)
    start_minute = now.replace(second=0, microsecond=0) - timedelta(minutes=59)
    volume = (await session.execute(select(minute.label("minute"), func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(or_(Attempt.http_status.between(200, 299), Attempt.http_status == 304)).label("successful"))
        .join(Target, Target.id == Attempt.crawl_target_id)
        .where(Attempt.started_at >= start_minute, *([Target.source_id == source_id] if source_id else []))
        .group_by(minute))).all()
    volumes = {row.minute: row for row in volume}
    throughput = []
    for i in range(60):
        stamp = start_minute + timedelta(minutes=i)
        row = volumes.get(stamp)
        throughput.append(dict(at=_utc(stamp), attempts=int(row.attempts) if row else 0,
                               successful=int(row.successful) if row else 0))
    completed = await session.scalar(select(func.count(Attempt.id)).join(Target, Target.id == Attempt.crawl_target_id)
        .where(Attempt.finished_at >= now - timedelta(minutes=5), *([Target.source_id == source_id] if source_id else [])))
    summary["urls_per_second"] = round(completed / 300, 3)
    summary["completed_last_5m"] = completed

    # Exclusive attempt dispositions reconcile to attempted, including older records.
    disposition = case(
        (Attempt.telemetry.is_(None), "historical_unknown"),
        (Attempt.telemetry["error_category"].astext == "persistence", "persistence_failed"),
        (Attempt.telemetry["error_category"].astext == "timeout", "timed_out"),
        (Attempt.telemetry["error_category"].astext == "worker", "worker_failed"),
        (Attempt.telemetry["result"].astext == "stale", "stale"),
        (Attempt.finished_at.is_(None), "unfinished"),
        (Attempt.outcome == "blocked", "blocked"), (Attempt.outcome == "failed", "failed"),
        (Attempt.outcome == "not_modified", "not_modified"),
        (measurement("stored") > 0, "persisted"), else_="skipped")
    summary["dispositions"] = {row[0]: row[1] for row in (await session.execute(
        select(disposition, func.count(Attempt.id)).join(Target, Target.id == Attempt.crawl_target_id)
        .where(*window).group_by(disposition))).all()}

    event_filters = [Event.created_at >= since]
    if source_id:
        event_filters.append(Target.source_id == source_id)
    if status:
        event_filters.append(Event.outcome == status)
    if category:
        event_filters.append(Event.stage == category.upper())
    if q:
        event_filters.append(Target.fetch_url.icontains(q, autoescape=True))
    if before_event_id:
        event_filters.append(Event.id < before_event_id)
    events = [event_dict(*row) for row in (await session.execute(select(Event, Target, Source)
        .join(Attempt, Attempt.id == Event.attempt_id).join(Target, Target.id == Attempt.crawl_target_id)
        .join(Source, Source.id == Target.source_id).where(*event_filters)
        .order_by(Event.id.desc()).limit(81))).all()]
    event_more = len(events) > 80
    events = events[:80]

    docs_query = select(Document.id, Document.title, Document.canonical_url, Document.document_type,
                        Document.is_available, Document.unavailable_at, Document.unavailable_http_status,
                        Document.last_seen_at, Source.slug.label("source")).join(Source, Source.id == Document.source_id)
    if source_id:
        docs_query = docs_query.where(Document.source_id == source_id)
    if q:
        docs_query = docs_query.where(or_(Document.title.icontains(q, autoescape=True), Document.canonical_url.icontains(q, autoescape=True)))
    doc_rows = (await session.execute(docs_query.order_by(Document.last_seen_at.desc(), Document.id.desc())
                                    .offset(document_page * 30).limit(31))).mappings().all()
    documents = [{**dict(row), "last_seen_at": _utc(row["last_seen_at"]), "unavailable_at": _utc(row["unavailable_at"])} for row in doc_rows[:30]]

    target_filters = []
    if source_id:
        target_filters.append(Target.source_id == source_id)
    if q:
        target_filters.append(Target.fetch_url.icontains(q, autoescape=True))
    if frontier_state:
        if frontier_state == "due":
            target_filters.extend([Target.state == "queued", Target.next_fetch_at <= now])
        elif frontier_state == "scheduled":
            target_filters.extend([Target.state == "queued", Target.next_fetch_at > now])
        elif frontier_state == "expired":
            target_filters.extend([Target.state == "leased", or_(Target.lease_until <= now, Target.lease_until.is_(None))])
        elif frontier_state == "retry":
            target_filters.append(Target.failure_count > 0)
        else:
            target_filters.append(Target.state == frontier_state)
    target_rows = (await session.execute(select(Target, Source.slug).join(Source, Source.id == Target.source_id)
        .where(*target_filters).order_by(Target.priority.desc(), Target.next_fetch_at, Target.id)
        .offset(frontier_page * 30).limit(31))).all()
    frontier = [dict(id=t.id, source=slug, url=t.fetch_url, normalized_url=t.normalized_url,
                     state=t.state, priority=t.priority, retries=t.failure_count,
                     next_fetch_at=_utc(t.next_fetch_at), lease_until=_utc(t.lease_until)) for t, slug in target_rows[:30]]

    source_rows = (await session.execute(select(Source.id, Source.slug, Source.name, Source.is_enabled,
        func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(or_(Attempt.http_status.between(200, 299), Attempt.http_status == 304)).label("successful"),
        func.count(Attempt.id).filter(Attempt.outcome == "failed").label("failed"),
        func.count(Attempt.id).filter(Attempt.outcome == "blocked").label("blocked"),
        func.avg(measurement("fetch_ms", Float)).label("avg_fetch_ms"),
        func.max(Attempt.started_at).label("last_activity_at"))
        .outerjoin(Target, Target.source_id == Source.id)
        .outerjoin(Attempt, and_(Attempt.crawl_target_id == Target.id, Attempt.started_at >= since))
        .group_by(Source.id).order_by(Source.id))).mappings().all()
    source_docs = dict((await session.execute(select(Document.source_id, func.count(Document.id)).group_by(Document.source_id))).all())
    sources = [{**dict(row), "documents": source_docs.get(row["id"], 0),
                "avg_fetch_ms": round(row["avg_fetch_ms"], 2) if row["avg_fetch_ms"] is not None else None,
                "last_activity_at": _utc(row["last_activity_at"])} for row in source_rows]
    workers = []
    worker_rows = (await session.scalars(select(Worker).order_by(Worker.heartbeat_at.desc()).limit(50))).all()
    for worker in worker_rows:
        age = max(0, (now - worker.heartbeat_at).total_seconds())
        online = worker.stopped_at is None and age <= 20
        workers.append(dict(id=worker.id, hostname=worker.hostname, pid=worker.pid,
            started_at=_utc(worker.started_at), heartbeat_at=_utc(worker.heartbeat_at),
            status="stopped" if worker.stopped_at else "online" if online else "offline",
            concurrency=worker.concurrency, batch_size=worker.batch_size,
            uptime_seconds=max(0, ((worker.stopped_at or now) - worker.started_at).total_seconds()),
            idle_seconds=0 if online and worker.active_targets else max(0, (now - worker.last_active_at).total_seconds()),
            active_targets=worker.active_targets if online else []))
    return dict(version=1, generated_at=_utc(now), window_start=_utc(since), summary=summary,
                throughput=throughput, sources=sources, workers=workers,
                active_workers=sum(w["status"] == "online" for w in workers),
                events=events, events_has_more=event_more,
                documents=documents, documents_has_more=len(doc_rows) > 30,
                frontier=frontier, frontier_has_more=len(target_rows) > 30)


async def inspect_document(session, document_id):
    row = (await session.execute(select(Document, Source).join(Source, Source.id == Document.source_id)
                                 .where(Document.id == document_id))).one_or_none()
    if row is None:
        return None
    document, source = row
    target = await session.get(Target, document.last_crawl_target_id) if document.last_crawl_target_id else None
    latest_attempt = await session.scalar(select(Attempt).where(Attempt.crawl_target_id == target.id)
        .order_by(Attempt.started_at.desc(), Attempt.id.desc()).limit(1)) if target else None
    # Current persisted content, deliberately fetched only when the inspector opens.
    body = document.body or ""
    matches = (await session.execute(select(Document.id, Document.canonical_url).where(
        Document.content_hash == document.content_hash, Document.id != document.id).limit(20))).all()
    return {**document_summary(document, source), "description": document.description,
            "body": body[:200_000], "body_truncated": len(body) > 200_000, "body_characters": len(body),
            "word_count": len(body.split()), "content_hash": document.content_hash,
            "metadata": document.metadata_, "author": document.author,
            "updated_at": _utc(document.updated_at), "published_at": _utc(document.published_at),
            "original_url": target.fetch_url if target else None,
            "normalized_url": target.normalized_url if target else None,
            "matching_content": [dict(id=id, canonical_url=url) for id, url in matches],
            "latest_attempt": dict(id=latest_attempt.id, http_status=latest_attempt.http_status,
                outcome=latest_attempt.outcome) if latest_attempt else None,
            "raw_html_available": False}


async def inspect_attempt(session, attempt_id):
    row = (await session.execute(select(Attempt, Target, Source)
        .join(Target, Target.id == Attempt.crawl_target_id).join(Source, Source.id == Target.source_id)
        .where(Attempt.id == attempt_id))).one_or_none()
    if row is None:
        return None
    attempt, target, source = row
    events = (await session.scalars(select(Event).where(Event.attempt_id == attempt_id).order_by(Event.id).limit(200))).all()
    return dict(id=attempt.id, url=target.fetch_url, normalized_url=target.normalized_url,
                source=source.slug, target_id=target.id, http_status=attempt.http_status,
                started_at=_utc(attempt.started_at), finished_at=_utc(attempt.finished_at),
                outcome=attempt.outcome, error=attempt.error_message, bytes_received=attempt.bytes_received,
                telemetry=attempt.telemetry, events=[event_dict(e, target, source) for e in events])
