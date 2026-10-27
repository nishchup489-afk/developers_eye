"""Read-only PostgreSQL backlog/coverage report for Developer's Eye indexer.

No attempt-history claims: failures, retries, latency, and throughput require
worker logs or a durable telemetry store. This report only measures DB state.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from indexer.config import IndexerConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexerReport:
    generated_at: datetime
    index_version: int
    total_documents: int
    available_documents: int
    indexed_rows: int
    current_documents: int
    missing_documents: int
    stale_documents: int
    unavailable_index_rows: int
    last_indexed_at: datetime | None

    @property
    def pending_documents(self) -> int:
        return self.missing_documents + self.stale_documents

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["generated_at"] = self.generated_at.isoformat()
        result["last_indexed_at"] = (
            self.last_indexed_at.isoformat() if self.last_indexed_at else None
        )
        result["pending_documents"] = self.pending_documents
        return result


def coverage_statement(config: IndexerConfig):
    """Aggregate one row per Document, never fetching vector payloads."""
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    available = Document.is_available.is_(True)
    has_index = SearchIndex.document_id.is_not(None)
    current = and_(
        has_index,
        SearchIndex.indexed_at >= Document.updated_at,
        SearchIndex.indexed_hash.startswith(config.index_hash_prefix),
    )
    return (
        select(
            func.count(Document.id).label("total_documents"),
            func.count(Document.id).filter(available).label("available_documents"),
            func.count(Document.id).filter(and_(available, current)).label("current_documents"),
            func.count(Document.id).filter(
                and_(available, SearchIndex.document_id.is_(None))
            ).label("missing_documents"),
            func.count(Document.id).filter(
                and_(available, has_index, ~current)
            ).label("stale_documents"),
            func.count(Document.id).filter(
                and_(Document.is_available.is_(False), has_index)
            ).label("unavailable_index_rows"),
        )
        .select_from(Document)
        .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
    )


async def get_indexer_report(
    session: AsyncSession, *, config: IndexerConfig
) -> IndexerReport:
    """Report current DB coverage, including version-stale search indexes."""
    row = (await session.execute(coverage_statement(config))).one()
    index_count, last_indexed = (
        await session.execute(
            select(func.count(SearchIndex.document_id), func.max(SearchIndex.indexed_at))
        )
    ).one()

    return IndexerReport(
        generated_at=datetime.now(timezone.utc),
        index_version=config.index_version,
        total_documents=int(row.total_documents),
        available_documents=int(row.available_documents),
        indexed_rows=int(index_count),
        current_documents=int(row.current_documents),
        missing_documents=int(row.missing_documents),
        stale_documents=int(row.stale_documents),
        unavailable_index_rows=int(row.unavailable_index_rows),
        last_indexed_at=last_indexed,
    )


async def _main() -> None:
    from backend.db.session import SessionFactory, engine

    config = IndexerConfig.from_env()
    try:
        async with SessionFactory() as session:
            report = await get_indexer_report(session, config=config)
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Developer's Eye indexer coverage report")
    parser.parse_args()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
