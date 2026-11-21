"""Crawl session reports: total work done between a crawler start and stop, across every worker.

A session is a span of time in which at least one crawler worker was alive. Overlapping worker
lifetimes are merged, so three workers started together and stopped together are one session.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, Integer, cast, func, or_, select

from backend.models.crawl_attempt import CrawlAttempt as Attempt
from backend.models.crawl_monitor import CrawlWorker as Worker
from backend.models.crawler_frontier import CrawlTarget as Target
from backend.models.source import Source
from backend.admin_services.crawler_reporting import _utc

# A worker whose heartbeat is older than this without a stop record is treated as crashed.
HEARTBEAT_STALE = timedelta(seconds=20)


def _measure(key, kind=Integer):
    return cast(Attempt.telemetry[key].astext, kind)


def worker_span(worker, now):
    """(start, end, running) for one worker. A crashed worker ends at its last heartbeat."""
    if worker.stopped_at is not None:
        return worker.started_at, max(worker.started_at, worker.stopped_at), False
    if now - worker.heartbeat_at > HEARTBEAT_STALE:
        return worker.started_at, max(worker.started_at, worker.heartbeat_at), False
    return worker.started_at, now, True


def merge_spans(workers, now):
    """Group workers into sessions of overlapping lifetimes, newest first."""
    spans = sorted(((*worker_span(w, now), w) for w in workers), key=lambda s: s[0])
    sessions = []
    for start, end, running, worker in spans:
        if sessions and start <= sessions[-1]["end"]:
            current = sessions[-1]
            current["end"] = max(current["end"], end)
            current["running"] = current["running"] or running
            current["workers"].append(worker)
        else:
            sessions.append(dict(start=start, end=end, running=running, workers=[worker]))
    return sessions[::-1]


async def session_work(session, start, end):
    """Every attempt that started inside [start, end], regardless of which worker ran it."""
    window = [Attempt.started_at >= start, Attempt.started_at <= end]
    success = or_(Attempt.http_status.between(200, 299), Attempt.http_status == 304)
    row = (await session.execute(select(
        func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(Attempt.finished_at.is_not(None)).label("finished"),
        func.count(Attempt.id).filter(success).label("successful"),
        func.count(Attempt.id).filter(Attempt.outcome == "failed").label("failed"),
        func.count(Attempt.id).filter(Attempt.outcome == "blocked").label("blocked"),
        func.count(Attempt.id).filter(Attempt.outcome == "not_modified").label("not_modified"),
        func.count(Attempt.id).filter(Attempt.telemetry["result"].astext == "stale").label("stale"),
        func.count(Attempt.id).filter(Attempt.telemetry["error_category"].astext == "timeout").label("timeouts"),
        func.count(Attempt.id).filter(_measure("stored") > 0).label("attempts_stored"),
        func.coalesce(func.sum(_measure("stored")), 0).label("documents_stored"),
        func.coalesce(func.sum(_measure("links_discovered")), 0).label("links_discovered"),
        func.coalesce(func.sum(_measure("links_enqueued")), 0).label("links_enqueued"),
        func.coalesce(func.sum(Attempt.bytes_received), 0).label("bytes_received"),
        func.avg(_measure("fetch_ms", Float)).label("avg_fetch_ms"),
        func.percentile_cont(0.95).within_group(_measure("fetch_ms", Float)).label("p95_fetch_ms"),
        func.count(func.distinct(Target.source_id)).label("sources"),
        func.min(Attempt.started_at).label("first_attempt_at"),
        func.max(Attempt.started_at).label("last_attempt_at"),
    ).join(Target, Target.id == Attempt.crawl_target_id).where(*window))).mappings().one()
    work = {k: int(v) for k, v in row.items() if k not in ("avg_fetch_ms", "p95_fetch_ms", "first_attempt_at", "last_attempt_at")}
    for key in ("avg_fetch_ms", "p95_fetch_ms"):
        work[key] = round(float(row[key]), 2) if row[key] is not None else None
    work["first_attempt_at"] = _utc(row["first_attempt_at"])
    work["last_attempt_at"] = _utc(row["last_attempt_at"])
    minutes = max((end - start).total_seconds(), 1) / 60
    work["attempts_per_minute"] = round(work["attempts"] / minutes, 2)
    work["success_percent"] = round(100 * work["successful"] / work["attempts"], 2) if work["attempts"] else None

    by_source = (await session.execute(select(
        Source.slug, func.count(Attempt.id).label("attempts"),
        func.count(Attempt.id).filter(success).label("successful"),
        func.count(Attempt.id).filter(Attempt.outcome.in_(("failed", "blocked"))).label("errors"),
        func.coalesce(func.sum(_measure("stored")), 0).label("documents_stored"))
        .join(Target, Target.id == Attempt.crawl_target_id).join(Source, Source.id == Target.source_id)
        .where(*window).group_by(Source.slug).order_by(func.count(Attempt.id).desc()).limit(15))).mappings().all()
    work["by_source"] = [{**dict(r), "attempts": int(r["attempts"]), "successful": int(r["successful"]),
                          "errors": int(r["errors"]), "documents_stored": int(r["documents_stored"])} for r in by_source]
    return work


def session_dict(s, work, now):
    workers = s["workers"]
    return dict(
        id=f"{int(s['start'].timestamp())}-{len(workers)}",
        started_at=_utc(s["start"]), stopped_at=None if s["running"] else _utc(s["end"]),
        running=s["running"], duration_seconds=round(((now if s["running"] else s["end"]) - s["start"]).total_seconds(), 1),
        worker_count=len(workers), hosts=sorted({w.hostname for w in workers}),
        peak_concurrency=sum(w.concurrency for w in workers),
        workers=[dict(id=w.id, hostname=w.hostname, pid=w.pid, started_at=_utc(w.started_at),
                      stopped_at=_utc(w.stopped_at), crashed=w.stopped_at is None and not worker_span(w, now)[2],
                      concurrency=w.concurrency) for w in sorted(workers, key=lambda w: w.started_at)][:50],
        work=work)


async def build_sessions(session, *, limit=20, start=None, end=None):
    now = datetime.now(timezone.utc)
    if start is not None:
        # A custom window: any start/stop time the admin chooses, still across all workers.
        end = min(end or now, now)
        candidates = (await session.scalars(select(Worker).where(
            Worker.started_at <= end, or_(Worker.stopped_at.is_(None), Worker.stopped_at >= start)).limit(1000))).all()
        # Crashed workers have no stop record; their life ended at the last heartbeat.
        workers = [w for w in candidates if worker_span(w, now)[1] >= start]
        running = end >= now - HEARTBEAT_STALE and any(worker_span(w, now)[2] for w in workers)
        custom = dict(start=start, end=end, running=running, workers=workers)
        return dict(version=1, generated_at=_utc(now), custom=True,
                    sessions=[session_dict(custom, await session_work(session, start, end), now)])
    workers = (await session.scalars(select(Worker).order_by(Worker.started_at.desc()).limit(1000))).all()
    sessions = merge_spans(workers, now)[:limit]
    return dict(version=1, generated_at=_utc(now), custom=False,
                sessions=[session_dict(s, await session_work(session, s["start"], s["end"]), now) for s in sessions])
