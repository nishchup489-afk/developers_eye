"""Search latency over a large synthetic index.

Usage (from crawler/):
    BENCH_DATABASE_URL=postgresql+asyncpg://.../name_with_test \
    python tests/benchmarks/bench_search.py --documents 500000 --rounds 5

Seeds document and search_index rows directly in SQL (skip with --reuse), then
times corpus statistics and search_documents() for common, rare and filtered
queries. The database must be disposable: both tables are emptied when seeding.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import selectors
import statistics
import sys
import time
from pathlib import Path
from bench_safety import benchmark_database_url

WORDS = ("python rust kernel socket buffer thread module package index query vector cache schema "
         "lexer parser token stream router client server deploy async await function class method "
         "database network memory process system library framework compile runtime container cluster "
         "pointer lifetime borrow closure iterator generator decorator template interface protocol").split()

SEED_BATCH = """
WITH new_documents AS (
    INSERT INTO document (source_id, canonical_url, document_type, title, body, content_hash, metadata, last_seen_at)
    SELECT :source, 'https://bench.example/' || n, CASE WHEN n % 5 = 0 THEN 'question' ELSE 'documentation' END,
           'Page ' || n, body, md5(n::text), '{}'::jsonb, now()
    FROM (
        SELECT n, (SELECT string_agg(:words_array[1 + floor(power(random(), 2) * CAST(:word_count AS int))::int], ' ')
                   FROM generate_series(1, 300) WHERE n > 0) || ' uniq' || n % 5000 AS body
        FROM generate_series(CAST(:first AS bigint), CAST(:last AS bigint)) n
    ) generated
    RETURNING id, body, document_type
)
INSERT INTO search_index (document_id, search_vector, code_vector, indexed_hash, category)
SELECT id, to_tsvector('english', body), to_tsvector('simple', ''), 'v1:' || repeat('0', 64),
       CASE document_type WHEN 'question' THEN 'stackoverflow' ELSE 'docs' END
FROM new_documents
"""

QUERIES = {
    "common_one_word": {"query": "python"},
    "common_two_words": {"query": "database network"},
    "rare_word": {"query": "uniq1234"},
    "rare_and_common": {"query": "python uniq77"},
    "filtered_common": {"query": "kernel", "category": "stackoverflow"},
    "no_match": {"query": "qqqqzzzz"},
}


async def seed(session_factory, count: int) -> None:
    from sqlalchemy import bindparam, text
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy.types import Text

    from backend.models.source import Source

    async with session_factory() as session, session.begin():
        await session.execute(text("TRUNCATE search_index, search_terms, vocabulary_change"))
        await session.execute(text("DELETE FROM document WHERE canonical_url LIKE 'https://bench.example/%'"))
        await session.execute(text("DELETE FROM source WHERE slug = 'bench'"))
        source = Source(slug="bench", name="Bench", kind="website", base_url="https://bench.example/",
                        allowed_hosts=["bench.example"], crawl_interval_seconds=86_400, is_enabled=True, config={})
        session.add(source)
        await session.flush()
        source_id = source.id
    statement = text(SEED_BATCH.replace(":words_array", "(CAST(:words AS text[]))"))
    started = time.perf_counter()
    for first in range(1, count + 1, 5_000):
        async with session_factory() as session, session.begin():
            await session.execute(statement, {"source": source_id, "words": WORDS, "word_count": len(WORDS) - 1,
                                              "first": first, "last": min(first + 4_999, count)})
        print(f"seeded {min(first + 4_999, count)} in {time.perf_counter() - started:.0f}s", flush=True)
    from backend.db.session import engine

    async with engine.connect() as connection:
        connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("VACUUM ANALYZE search_index"))
        await connection.execute(text("VACUUM ANALYZE document"))


async def measure(session_factory, rounds: int) -> dict:
    from sqlalchemy import text

    from backend.search.ranking.statistics import get_corpus_statistics
    from backend.search.service import _df_cache, search_documents, set_corpus_statistics

    report = {}
    async with session_factory() as session:
        report["indexed_documents"] = await session.scalar(text("SELECT count(*) FROM search_index"))
        report["database_size"] = await session.scalar(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
        started = time.perf_counter()
        text_corpus = await get_corpus_statistics(session, "TEXT")
        code_corpus = await get_corpus_statistics(session, "CODE")
        report["corpus_statistics_seconds"] = round(time.perf_counter() - started, 3)
    set_corpus_statistics(text_corpus, code_corpus)

    for name, query in QUERIES.items():
        for label, clear in (("cold", True), ("warm", False)):
            samples = []
            for _ in range(rounds):
                if clear:
                    _df_cache.clear()
                async with session_factory() as session:
                    started = time.perf_counter()
                    results = await search_documents(session, **query)
                    samples.append((time.perf_counter() - started) * 1000)
            samples.sort()
            report[f"{name}_{label}_ms"] = {"p50": round(statistics.median(samples), 1),
                                            "max": round(samples[-1], 1), "results": len(results)}
    return report


async def main(args) -> None:
    from backend.db.session import SessionFactory, engine

    logging.disable(logging.WARNING)
    if not args.reuse:
        await seed(SessionFactory, args.documents)
    print(json.dumps(await measure(SessionFactory, args.rounds), indent=1))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=100_000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--reuse", action="store_true")
    arguments = parser.parse_args()
    url = os.environ.get("BENCH_DATABASE_URL", "")
    try:
        url = benchmark_database_url(url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    os.environ["DATABASE_URL"] = url
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    if sys.platform == "win32":
        asyncio.run(main(arguments), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main(arguments))
