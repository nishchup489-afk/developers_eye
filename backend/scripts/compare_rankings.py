"""Compare Developer's Eye BM25 with PostgreSQL ts_rank_cd on identical hits.

From backend/:
    poetry run python scripts/compare_rankings.py "python async api" --mode text
    poetry run python scripts/compare_rankings.py "async def fetch" --mode code
    poetry run python scripts/compare_rankings.py "FastAPI Depends" --mode all --output ranking-report.json

Reads the configured DATABASE_URL via backend.core.config. Never writes to DB.
Corpus-statistics aggregation scans the index: run manually, not per request.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import SessionFactory, engine
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.search.config import SearchConfig
from backend.search.query_analyzer.analyzer import analyze_query
from backend.search.query_selector.planner import SearchMode
from backend.search.ranking.orchestrator import rank_candidates
from backend.search.ranking.statistics import get_corpus_statistics
from backend.search.ranking.types import CorpusStatistics
from backend.search.service import _retrieve_candidates


def _native_score(query: str, mode: SearchMode):
    """Native baseline with consistent normalization=0 across channels."""
    text_tsquery = func.websearch_to_tsquery("english", query)
    code_tsquery = func.websearch_to_tsquery("simple", query)
    text_score = func.ts_rank_cd(SearchIndex.search_vector, text_tsquery, 0)
    code_score = func.ts_rank_cd(SearchIndex.code_vector, code_tsquery, 0)

    if mode is SearchMode.TEXT:
        return text_score
    if mode is SearchMode.CODE:
        return code_score
    return text_score + code_score


async def compare_one(
    session: AsyncSession,
    query: str,
    mode: SearchMode,
    *,
    k: int,
) -> dict[str, object]:
    settings = SearchConfig()
    normalized = analyze_query(query, config=settings)

    # The service's real retrieval logic, limited to 100 per channel.
    hits = await _retrieve_candidates(session, normalized, mode)
    ids = [hit.document_id for hit in hits]
    if not ids:
        return {
            "query": normalized,
            "mode": mode.value,
            "candidate_count": 0,
            "top_k_overlap": None,
            "mean_absolute_rank_shift": None,
            "postgresql_order": [],
            "bm25_order": [],
            "documents": [],
        }

    # One full scan per requested channel, used only by this diagnostic.
    text_corpus: CorpusStatistics | None = None
    code_corpus: CorpusStatistics | None = None
    if mode in (SearchMode.TEXT, SearchMode.ALL):
        text_corpus = await get_corpus_statistics(session, "TEXT")
    if mode in (SearchMode.CODE, SearchMode.ALL):
        code_corpus = await get_corpus_statistics(session, "CODE")

    bm25 = await rank_candidates(
        session,
        normalized,
        hits,
        mode=mode,
        text_corpus=text_corpus,
        code_corpus=code_corpus,
        tokenizer_config=settings,
    )

    score = _native_score(normalized, mode)
    stmt = (
        select(
            SearchIndex.document_id,
            score.label("postgres_score"),
            Document.title,
            Document.canonical_url,
        )
        .join(Document, Document.id == SearchIndex.document_id)
        .where(SearchIndex.document_id.in_(ids))
        .order_by(score.desc(), SearchIndex.document_id.asc())
    )
    pg_rows = (await session.execute(stmt)).all()

    pg_ids = [int(row.document_id) for row in pg_rows]
    bm25_ids = [hit.document_id for hit in bm25]
    if set(pg_ids) != set(bm25_ids) or len(pg_ids) != len(bm25_ids):
        raise RuntimeError(
            "Candidate mismatch. A document may be missing from the index or metadata."
        )

    pg_positions = {doc_id: i for i, doc_id in enumerate(pg_ids, start=1)}
    bm25_positions = {doc_id: i for i, doc_id in enumerate(bm25_ids, start=1)}
    pg_by_id = {int(row.document_id): row for row in pg_rows}
    bm25_scores = {hit.document_id: hit.score for hit in bm25}

    documents = [
        {
            "document_id": doc_id,
            "bm25_rank": bm25_positions[doc_id],
            "postgres_rank": pg_positions[doc_id],
            "rank_shift": bm25_positions[doc_id] - pg_positions[doc_id],
            "bm25_score": float(bm25_scores[doc_id]),
            "postgres_score": float(pg_by_id[doc_id].postgres_score),
            "title": pg_by_id[doc_id].title,
            "url": pg_by_id[doc_id].canonical_url,
        }
        for doc_id in bm25_ids
    ]
    top_n = min(k, len(ids))
    overlap = len(set(pg_ids[:top_n]) & set(bm25_ids[:top_n])) / top_n
    mean_shift = sum(abs(row["rank_shift"]) for row in documents) / len(documents)

    return {
        "query": normalized,
        "mode": mode.value,
        "candidate_count": len(ids),
        "evaluation_time_utc": datetime.now(timezone.utc).isoformat(),
        "top_k": top_n,
        "top_k_overlap": overlap,
        "mean_absolute_rank_shift": mean_shift,
        "postgresql_order": pg_ids,
        "bm25_order": bm25_ids,
        "corpus": {
            "text": (
                {"N": text_corpus.document_count,
                 "avgDL": text_corpus.average_document_length}
                if text_corpus else None
            ),
            "code": (
                {"N": code_corpus.document_count,
                 "avgDL": code_corpus.average_document_length}
                if code_corpus else None
            ),
        },
        "documents": documents,
    }


def print_report(report: dict[str, object], *, k: int) -> None:
    print(f"\nQuery: {report['query']} | Mode: {report['mode']}")
    print(f"Candidates: {report['candidate_count']}")
    if report["candidate_count"] == 0:
        print("No retrieval candidates. Try a different query.")
        return

    print(f"Top-{report['top_k']} overlap: {report['top_k_overlap']:.3f}")
    print(f"Mean absolute rank shift: {report['mean_absolute_rank_shift']:.3f}")
    print(f"PostgreSQL top-{k}: {report['postgresql_order'][:k]}")
    print(f"BM25 top-{k}:       {report['bm25_order'][:k]}")
    print("\nBM25#  PG#  Doc ID       BM25 score       PG score   Title")
    for row in report["documents"][:k]:
        title = row["title"].replace("\n", " ")[:68]
        print(
            f"{row['bm25_rank']:5d} {row['postgres_rank']:4d} "
            f"{row['document_id']:7d} "
            f"{row['bm25_score']:15.6f} "
            f"{row['postgres_score']:14.6f}   {title}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Developer search query")
    parser.add_argument("--mode", choices=["text", "code", "all"], default="text")
    parser.add_argument("--k", type=int, default=10, help="Number of top results to inspect")
    parser.add_argument("--output", type=Path, help="Save complete JSON report")
    args = parser.parse_args()
    if not 1 <= args.k <= 100:
        parser.error("--k must be between 1 and 100")

    try:
        async with SessionFactory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                report = await compare_one(
                    session, args.query, SearchMode(args.mode), k=args.k
                )
        print_report(report, k=args.k)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Saved: {args.output}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
