"""Read-only corpus statistics for the admin dashboard.

This page must stay fast at millions of documents, so nothing here scans a large
table. Past EXACT_LIMIT rows, totals come from the planner and every breakdown
comes from one page sample. `exact` tells the reader which of the two they got.
Small corpora are counted exactly.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, literal, select, text

from backend.admin_services.crawler_reporting import _percentage, _utc
from backend.admin_services.system_reporting import _table_sizes, host_expression
from backend.models.crawl_monitor import IndexerWorker
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.search_terms import VocabularyChange
from backend.models.source import Source
from backend.search.service import corpus_snapshot_info

EXACT_LIMIT = 100_000
SAMPLE_ROWS = 50_000
HOST_LIMIT = 50
AGE_LABELS = (("day", "Last 24 hours"), ("week", "1 to 7 days"), ("month", "8 to 30 days"), ("older", "Over 30 days"))


async def _estimated_rows(session, table: str) -> int | None:
    """Planner density times the current size, so growth since ANALYZE still counts.

    None means the table has no usable statistics and must be counted.
    """
    row = (await session.execute(text("""
        SELECT c.reltuples, c.relpages,
               pg_relation_size(c.oid) / current_setting('block_size')::bigint AS pages
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema() AND c.relname = :table"""), {"table": table})).mappings().one()
    if row["reltuples"] <= 0 or row["relpages"] <= 0:
        return None
    return int(row["reltuples"] / row["relpages"] * row["pages"])


def _sample(table, estimate: int | None):
    """Return (selectable, exact). With no estimate, or a small table, read every row."""
    if estimate is None or estimate <= EXACT_LIMIT:
        return table, True
    return table.tablesample(func.system(100.0 * SAMPLE_ROWS / estimate)), False


def _age(column, now):
    return case((column >= now - timedelta(days=1), literal("day")),
                (column >= now - timedelta(days=7), literal("week")),
                (column >= now - timedelta(days=30), literal("month")),
                else_=literal("older"))


async def _document_rows(session, now, table, estimate):
    """Scale one grouped pass over the sample to the whole table."""
    source, exact = _sample(table, estimate)
    columns = source.c
    host = host_expression(columns.canonical_url).label("host")
    age = _age(columns.last_seen_at, now).label("age")
    rows = (await session.execute(select(
        columns.source_id, host, columns.document_type, columns.is_available, age,
        func.count().label("documents"),
        # octet_length reads the stored size without decompressing the body.
        func.coalesce(func.sum(func.octet_length(columns.body)), 0).label("body_bytes"))
        .select_from(source)
        .group_by(columns.source_id, host, columns.document_type, columns.is_available, age))).mappings().all()
    sampled = sum(r["documents"] for r in rows)
    scale = 1.0 if exact or not sampled else estimate / sampled
    return rows, sampled, scale, exact


async def _index_rows(session, now, table, estimate):
    source, exact = _sample(table, estimate)
    columns = source.c
    age = _age(columns.indexed_at, now).label("age")
    rows = (await session.execute(select(columns.category, age, func.count().label("documents"))
                                  .select_from(source).group_by(columns.category, age))).mappings().all()
    sampled = sum(r["documents"] for r in rows)
    return rows, sampled, 1.0 if exact or not sampled else estimate / sampled, exact


def _ranked(counts: Counter, scale: float, total: int, limit: int | None = None):
    return [dict(name=name or "(unknown)", documents=round(count * scale), share_percent=_percentage(count * scale, total))
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[:limit]]


def _ages(counts: Counter, scale: float, total: int):
    return [dict(id=key, label=label, documents=round(counts[key] * scale),
                 share_percent=_percentage(counts[key] * scale, total)) for key, label in AGE_LABELS]


async def build_corpus_report(session):
    now = datetime.now(timezone.utc)
    document_table, index_table = Document.__table__, SearchIndex.__table__
    document_rows, documents_sampled, scale, exact = await _document_rows(
        session, now, document_table, await _estimated_rows(session, "document"))
    index_rows, indexed_sampled, index_scale, index_exact = await _index_rows(
        session, now, index_table, await _estimated_rows(session, "search_index"))

    available, per_type, per_host, seen = Counter(), Counter(), Counter(), Counter()
    per_source: dict[int, Counter] = {}
    body_bytes = 0
    for row in document_rows:
        count = row["documents"]
        available[bool(row["is_available"])] += count
        per_type[row["document_type"]] += count
        per_host[row["host"]] += count
        seen[row["age"]] += count
        body_bytes += row["body_bytes"]
        entry = per_source.setdefault(row["source_id"], Counter())
        entry["documents"] += count
        entry["available"] += count if row["is_available"] else 0
        entry["body_bytes"] += row["body_bytes"]
    total = round(documents_sampled * scale)
    available_total = round(available[True] * scale)
    indexed_total = round(indexed_sampled * index_scale)

    categories, indexed_ages = Counter(), Counter()
    for row in index_rows:
        categories[row["category"]] += row["documents"]
        indexed_ages[row["age"]] += row["documents"]

    source_rows = (await session.execute(select(Source.id, Source.slug, Source.name, Source.is_enabled)
                                         .order_by(Source.name))).mappings().all()
    sources = []
    for row in source_rows:
        entry = per_source.get(row["id"], Counter())
        sources.append(dict(
            id=row["id"], slug=row["slug"], name=row["name"], enabled=bool(row["is_enabled"]),
            documents=round(entry["documents"] * scale), available=round(entry["available"] * scale),
            share_percent=_percentage(entry["documents"] * scale, total),
            average_body_bytes=round(entry["body_bytes"] / entry["documents"]) if entry["documents"] else None))
    sources.sort(key=lambda s: (-s["documents"], s["name"]))

    sizes = {t["name"]: t for t in await _table_sizes(session)}
    storage = [dict(table=name, total_bytes=sizes[name]["total_bytes"], heap_bytes=sizes[name]["heap_bytes"],
                    index_bytes=sizes[name]["index_bytes"], toast_bytes=sizes[name]["toast_bytes"],
                    bytes_per_document=round(sizes[name]["total_bytes"] / total, 1) if total else None)
               for name in ("document", "search_index", "search_terms") if name in sizes]

    terms_estimate = await _estimated_rows(session, "search_terms")
    if terms_estimate is None or terms_estimate <= EXACT_LIMIT:
        terms = int(await session.scalar(text("SELECT count(*) FROM search_terms")))
        terms_exact = True
    else:
        terms, terms_exact = terms_estimate, False
    outbox = int(await session.scalar(select(func.count()).select_from(
        select(VocabularyChange.id).limit(EXACT_LIMIT + 1).subquery())))

    last_batch = await session.scalar(select(func.max(IndexerWorker.last_batch_at)))
    last_seen = await session.scalar(select(func.max(Document.last_seen_at)))
    snapshot = corpus_snapshot_info()

    return dict(
        version=1, generated_at=_utc(now),
        estimates=dict(exact=exact and index_exact, sampled_documents=documents_sampled, sampled_index_rows=indexed_sampled),
        summary=dict(total_documents=total, available_documents=available_total,
                     unavailable_documents=max(0, total - available_total), indexed_documents=indexed_total,
                     indexed_percent=_percentage(min(indexed_total, available_total), available_total),
                     total_body_bytes=round(body_bytes * scale),
                     average_body_bytes=round(body_bytes / documents_sampled) if documents_sampled else None,
                     sources=len(source_rows), enabled_sources=sum(bool(r["is_enabled"]) for r in source_rows),
                     hosts=len(per_host), hosts_exact=exact),
        vocabulary=dict(terms=terms, exact=terms_exact, pending_changes=outbox),
        freshness=dict(last_crawled_at=_utc(last_seen), last_indexed_at=_utc(last_batch),
                       seen=_ages(seen, scale, total), indexed=_ages(indexed_ages, index_scale, indexed_total)),
        bm25=dict(loaded=snapshot is not None, documents=snapshot["documents"] if snapshot else None,
                  average_text_length=snapshot["average_text_length"] if snapshot else None,
                  average_code_length=snapshot["average_code_length"] if snapshot else None,
                  loaded_at=_utc(snapshot["loaded_at"]) if snapshot else None),
        storage=storage, sources=sources,
        hosts=_ranked(per_host, scale, total, HOST_LIMIT),
        document_types=_ranked(per_type, scale, total),
        categories=_ranked(categories, index_scale, indexed_total),
    )
