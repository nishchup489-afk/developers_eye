"""Read-only PostgreSQL indexer reporting for the admin control center.

Mirrors the coverage definitions of crawler/src/indexer/reporting.py, but lives
in the backend so the API never imports the worker package. It reads committed
`document` and `search_index` rows only: it does not run, claim, or mark work.

Liveness is inferred from committed writes. The indexer has no heartbeat table,
so "indexing" means rows were written recently, not that a process is alive.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, literal, select

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.source import Source
from backend.services.crawler_reporting import _percentage, _utc

REINDEX_MARKER = "reindex:pending"
# Matches the worker's default poll interval plus one batch of slack.
ACTIVE_WITHIN = timedelta(minutes=2)
LIST_LIMIT = 30


def _conditions(index_version: int):
    prefix = f"v{index_version}:"
    available = Document.is_available.is_(True)
    has_index = SearchIndex.document_id.is_not(None)
    current = and_(has_index, SearchIndex.indexed_at >= Document.updated_at,
                   SearchIndex.indexed_hash.startswith(prefix))
    return available, has_index, current, prefix


def _pending_reason(prefix: str):
    return case(
        (SearchIndex.document_id.is_(None), literal("missing")),
        (SearchIndex.indexed_hash == REINDEX_MARKER, literal("reindex_requested")),
        (~SearchIndex.indexed_hash.startswith(prefix), literal("old_version")),
        else_=literal("content_changed"),
    )


async def build_indexer_report(session, *, index_version: int = 1, source_id: int | None = None):
    now = datetime.now(timezone.utc)
    available, has_index, current, prefix = _conditions(index_version)
    scope = [Document.source_id == source_id] if source_id else []
    joined = lambda statement: statement.select_from(Document).outerjoin(  # noqa: E731
        SearchIndex, SearchIndex.document_id == Document.id).where(*scope)

    coverage = (await session.execute(joined(select(
        func.count(Document.id).label("total_documents"),
        func.count(Document.id).filter(available).label("available_documents"),
        func.count(SearchIndex.document_id).label("indexed_rows"),
        func.count(Document.id).filter(and_(available, current)).label("current_documents"),
        func.count(Document.id).filter(and_(available, ~has_index)).label("missing_documents"),
        func.count(Document.id).filter(and_(available, has_index, ~current)).label("stale_documents"),
        func.count(Document.id).filter(and_(available, SearchIndex.indexed_hash == REINDEX_MARKER)).label("reindex_requested"),
        func.count(Document.id).filter(and_(~available, has_index)).label("unavailable_index_rows"),
        func.max(SearchIndex.indexed_at).label("last_indexed_at"),
        func.count(SearchIndex.document_id).filter(SearchIndex.indexed_at >= now - timedelta(minutes=5)).label("indexed_last_5m"),
        func.count(SearchIndex.document_id).filter(SearchIndex.indexed_at >= now - timedelta(hours=1)).label("indexed_last_hour"),
        func.count(SearchIndex.document_id).filter(SearchIndex.indexed_at >= now - timedelta(days=1)).label("indexed_last_24h"),
        func.max(Document.updated_at).filter(available).label("last_document_change_at"),
    )))).mappings().one()
    coverage = dict(coverage)
    last_indexed_at = coverage.pop("last_indexed_at")
    last_change = coverage.pop("last_document_change_at")
    activity = {key: coverage.pop(key) for key in ("indexed_last_5m", "indexed_last_hour", "indexed_last_24h")}
    coverage["pending_documents"] = coverage["missing_documents"] + coverage["stale_documents"]
    coverage["coverage_percent"] = _percentage(coverage["current_documents"], coverage["available_documents"])

    if last_indexed_at and now - last_indexed_at <= ACTIVE_WITHIN:
        status = "indexing"
    elif not coverage["available_documents"]:
        status = "empty"
    elif not coverage["pending_documents"]:
        status = "caught_up"
    else:
        status = "backlog_waiting"
    activity.update(status=status, last_indexed_at=_utc(last_indexed_at),
                    last_document_change_at=_utc(last_change),
                    docs_per_minute=round(activity["indexed_last_5m"] / 5, 2))

    # One bucket per minute; a document re-indexed later moves to its newest minute.
    start = (now - timedelta(minutes=59)).replace(second=0, microsecond=0)
    minute = func.date_trunc("minute", SearchIndex.indexed_at)
    rows = (await session.execute(joined(select(minute.label("at"), func.count().label("indexed")))
        .where(SearchIndex.indexed_at >= start).group_by(minute))).all()
    per_minute = {at.astimezone(timezone.utc): count for at, count in rows}
    throughput = [dict(at=_utc(start + timedelta(minutes=i)), indexed=per_minute.get(start + timedelta(minutes=i), 0))
                  for i in range(60)]

    recent = (await session.execute(
        select(Document, Source.slug, SearchIndex.indexed_at, SearchIndex.indexed_hash, and_(available, current).label("current"))
        .join(SearchIndex, SearchIndex.document_id == Document.id)
        .join(Source, Source.id == Document.source_id).where(*scope)
        .order_by(SearchIndex.indexed_at.desc(), Document.id.desc()).limit(LIST_LIMIT))).all()
    pending = (await session.execute(
        joined(select(Document, Source.slug, SearchIndex.indexed_at, _pending_reason(prefix).label("reason")))
        .join(Source, Source.id == Document.source_id).where(available, ~current)
        .order_by(Document.id).limit(LIST_LIMIT))).all()

    per_source = (await session.execute(
        select(Source.id, Source.slug, Source.name,
               func.count(Document.id).filter(available).label("available"),
               func.count(Document.id).filter(and_(available, current)).label("current"),
               func.count(Document.id).filter(and_(available, ~has_index)).label("missing"),
               func.count(Document.id).filter(and_(available, has_index, ~current)).label("stale"),
               func.max(SearchIndex.indexed_at).label("last_indexed_at"))
        .select_from(Source).outerjoin(Document, Document.source_id == Source.id)
        .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
        .group_by(Source.id).order_by(Source.name))).mappings().all()

    return dict(
        version=1, generated_at=_utc(now), index_version=index_version,
        coverage=coverage, activity=activity, throughput=throughput,
        recent=[dict(document_id=doc.id, title=doc.title, canonical_url=doc.canonical_url, source=slug,
                     indexed_at=_utc(indexed_at), index_version=hash_.split(":", 1)[0] if ":" in hash_ else hash_,
                     current=bool(is_current)) for doc, slug, indexed_at, hash_, is_current in recent],
        pending=[dict(document_id=doc.id, title=doc.title, canonical_url=doc.canonical_url, source=slug,
                      updated_at=_utc(doc.updated_at), indexed_at=_utc(indexed_at), reason=reason)
                 for doc, slug, indexed_at, reason in pending],
        sources=[dict(row, last_indexed_at=_utc(row["last_indexed_at"]),
                      coverage_percent=_percentage(row["current"], row["available"])) for row in per_source],
    )
