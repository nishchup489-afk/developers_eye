"""Capture one judging pool: both rankers' orders over the same candidates.

Used by the admin judging page (ADR-0057). It runs the production retrieval,
eligibility filter and BM25 ranker, then orders the same eligible candidates
by native PostgreSQL ts_rank_cd, exactly as scripts/compare_rankings.py does.
Documents are identified by canonical URL so judgments survive reindexing.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_index import SearchIndex
from backend.search.categories import categories_for_filter
from backend.search.query_analyzer.analyzer import analyze_query
from backend.search.query_selector.planner import SearchMode
from backend.search.ranking.orchestrator import rank_candidates
from backend.search.ranking.types import CorpusStatistics

POOL_DEPTH = 10


def native_score(query: str, mode: SearchMode):
    """PostgreSQL's own ranking, with the live channel normalizations."""
    text_score = func.ts_rank_cd(SearchIndex.search_vector, func.websearch_to_tsquery("english", query), 0)
    code_score = func.ts_rank_cd(SearchIndex.code_vector, func.websearch_to_tsquery("simple", query), 32)
    if mode is SearchMode.TEXT:
        return text_score
    if mode is SearchMode.CODE:
        return code_score
    return text_score + code_score


async def capture_pool(
    session: AsyncSession,
    query: str,
    mode: str,
    *,
    source: str | None,
    text_corpus: CorpusStatistics,
    code_corpus: CorpusStatistics,
) -> dict[str, Any]:
    """Return {candidate_count, elapsed_ms, documents[{url,title,bm25_rank,postgres_rank}]}."""
    # Imported here: service imports this package's siblings at module load.
    from backend.search.service import _metadata_for_candidates, _retrieve_candidates

    started = perf_counter()
    search_mode = SearchMode(mode)
    normalized = analyze_query(query)
    categories = categories_for_filter(source)
    hits = await _retrieve_candidates(session, normalized, search_mode, categories)
    documents: list[dict[str, Any]] = []
    if hits:
        ranked = await rank_candidates(
            session, normalized, hits, mode=search_mode,
            text_corpus=text_corpus, code_corpus=code_corpus,
        )
        eligible, metadata = await _metadata_for_candidates(session, ranked, categories)
        ids = [hit.document_id for hit in eligible]
        native = native_score(normalized, search_mode)
        pg_ids = [int(row[0]) for row in (await session.execute(
            select(SearchIndex.document_id)
            .where(SearchIndex.document_id.in_(ids))
            .order_by(native.desc(), SearchIndex.document_id.asc())
        )).all()] if ids else []
        pg_rank = {doc_id: rank for rank, doc_id in enumerate(pg_ids, 1)}
        for rank, hit in enumerate(eligible, 1):
            record = metadata[hit.document_id]
            documents.append(dict(
                url=record.canonical_url, title=record.title or "",
                bm25_rank=rank, postgres_rank=pg_rank.get(hit.document_id, len(ids) + 1),
            ))
    return dict(
        candidate_count=len(documents),
        elapsed_ms=round((perf_counter() - started) * 1000),
        documents=documents,
    )


def pooled_urls(documents: list[dict[str, Any]], depth: int = POOL_DEPTH) -> dict[str, str]:
    """URL -> title for the union of both top-`depth` lists."""
    pooled = {}
    for key in ("bm25_rank", "postgres_rank"):
        for doc in sorted(documents, key=lambda d: d[key])[:depth]:
            pooled[doc["url"]] = doc["title"]
    return pooled


__all__ = ["POOL_DEPTH", "capture_pool", "native_score", "pooled_urls"]
