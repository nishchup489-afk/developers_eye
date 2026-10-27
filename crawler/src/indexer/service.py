
"""Orchestrate individual Developer's Eye indexing and removal jobs.

Pipeline:
    IndexCandidate -> builder -> analyzer -> vector -> writer -> IndexResult

The service owns no database transaction, SQL, worker loops, or retries.
The writer owns the short, locked write transaction; a separate read session
is used while preparing the document so expensive text processing holds no lock.

Expected caller: indexer.worker.runner, using backend.db.session.SessionFactory.
"""

from __future__ import annotations

from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from indexer.analyzer import analyze_index_document
from indexer.builder import build_index_document, calculate_index_hash
from indexer.config import IndexerConfig
from indexer.errors import IndexDocumentError, StaleIndexSourceError
from indexer.schemas import IndexCandidate, IndexResult, IndexStatus
from indexer.vector import build_search_vectors
from indexer.writer import persist_search_vectors, remove_search_index


def _result(
    document_id: int,
    status: IndexStatus,
    started_at: float,
    *,
    indexed_hash: str | None = None,
    details: str | None = None,
) -> IndexResult:
    return IndexResult(
        document_id=document_id,
        status=status,
        duration_ms=max(0.0, (perf_counter() - started_at) * 1000.0),
        indexed_hash=indexed_hash,
        details=details,
    )


async def index_candidate(
    session_factory: async_sessionmaker[AsyncSession],
    candidate: IndexCandidate,
    *,
    config: IndexerConfig,
) -> IndexResult:
    """Prepare and synchronize one selected source revision.

    Expected source/data errors become explicit IndexResult outcomes.
    Database errors, programming errors and cancellation propagate unchanged
    so the worker can log, roll back (writer does this), and retry deliberately.

    A returned STALE candidate should be reselected instead of retried as-is.
    """
    if not isinstance(candidate, IndexCandidate):
        raise TypeError("candidate must be an IndexCandidate")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    start = perf_counter()

    try:
        # Read session ends before vector SQL is executed by the writer.
        async with session_factory() as session:
            document = await build_index_document(session, candidate, config=config)

        indexed_hash = calculate_index_hash(document, config=config)
        analyzed = analyze_index_document(document, config=config)
        vectors = build_search_vectors(analyzed, config=config)

    except StaleIndexSourceError as exc:
        return _result(candidate.document_id, IndexStatus.STALE, start, details=str(exc))
    except IndexDocumentError as exc:
        return _result(candidate.document_id, IndexStatus.FAILED, start, details=str(exc))

    # The writer opens its own transaction, locks Document, validates the
    # source snapshot, and upserts only when necessary.
    status = await persist_search_vectors(
        session_factory, vectors, indexed_hash=indexed_hash
    )

    return _result(
        candidate.document_id,
        status,
        start,
        indexed_hash=indexed_hash
        if status in {IndexStatus.INDEXED, IndexStatus.UNCHANGED}
        else None,
        details="source changed before write" if status is IndexStatus.STALE else None,
    )


async def remove_candidate(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: int,
) -> IndexResult:
    """Synchronize an obsolete index, without deleting a live document's index.

    REMOVED: index row deleted; SKIPPED: already absent;
    STALE: source became available before deletion.
    """
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")

    start = perf_counter()
    status = await remove_search_index(session_factory, document_id)

    return _result(
        document_id,
        status,
        start,
        details="document is available; index retained"
        if status is IndexStatus.STALE
        else None,
    )


__all__ = ["index_candidate", "remove_candidate"]
