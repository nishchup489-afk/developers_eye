"""Indexer throughput at several concurrency levels, with a post-run recount.

Usage (from crawler/):
    BENCH_DATABASE_URL=postgresql+asyncpg://.../name_with_test \
    python tests/benchmarks/bench_indexer.py --documents 3000 --levels 1,2,4,8

Inserts synthetic documents in one fakeindex source, indexes them from empty at
each concurrency level, and checks search_terms against a full recount. The
database must be disposable: search_index and search_terms are emptied.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import random
import selectors
import sys
import time
from pathlib import Path
from bench_safety import benchmark_database_url

ALPHABET = "abcdefghijklmnopqrstuvwxyz"


def vocabulary(size: int) -> list[str]:
    rng = random.Random(7)
    return ["".join(rng.choices(ALPHABET, k=rng.randint(4, 10))) for _ in range(size)]


async def prepare(session_factory, count: int, words: list[str]) -> None:
    from sqlalchemy import delete, insert, text

    from backend.models import Document
    from backend.models.source import Source

    async with session_factory() as session, session.begin():
        await session.execute(text("TRUNCATE search_index, search_terms"))
        await session.execute(delete(Document).where(Document.canonical_url.like("https://fakeindex.example/%")))
        await session.execute(delete(Source).where(Source.slug == "fakeindex"))
        source = Source(slug="fakeindex", name="Fake index", kind="website", base_url="https://fakeindex.example/",
                        allowed_hosts=["fakeindex.example"], crawl_interval_seconds=86_400, is_enabled=True, config={})
        session.add(source)
        await session.flush()
        rng = random.Random(11)
        for start in range(0, count, 500):
            rows = []
            for number in range(start, min(start + 500, count)):
                # A few very common words plus a long tail, like real prose.
                body = " ".join(rng.choices(words, weights=[1 / (i + 1) for i in range(len(words))], k=400))
                rows.append(dict(source_id=source.id, canonical_url=f"https://fakeindex.example/{number}",
                                 document_type="documentation", title=f"Page {number}", body=body,
                                 content_hash=hashlib.sha256(body.encode()).hexdigest(), metadata_={},
                                 last_seen_at=datetime.now(timezone.utc)))
            await session.execute(insert(Document), rows)


async def index_shard(session_factory, config) -> int:
    from indexer.worker.runner import run_batch

    cursor, indexed = 0, 0
    while True:
        report = await run_batch(session_factory, config=config, index_cursor=cursor)
        indexed += report.outcomes.get("indexed", 0)
        cursor = report.next_index_cursor
        if report.selected == 0:
            return indexed


async def shard_main(args) -> None:
    from backend.db.session import SessionFactory, engine
    from indexer.config import IndexerConfig

    logging.disable(logging.WARNING)
    await index_shard(SessionFactory, IndexerConfig(
        batch_size=args.batch_size, concurrency=args.levels[0],
        shard_count=args.processes, shard_index=args.shard_index,
    ))
    await engine.dispose()


async def run_level(session_factory, concurrency: int, args, *, drain) -> dict:
    from sqlalchemy import text

    from indexer.config import IndexerConfig

    async with session_factory() as session, session.begin():
        await session.execute(text("TRUNCATE search_index, search_terms"))
    started = time.perf_counter()
    if args.processes == 1:
        config = IndexerConfig(batch_size=args.batch_size, concurrency=concurrency)
        await index_shard(session_factory, config)
    else:
        children = [await asyncio.create_subprocess_exec(
            sys.executable, __file__, "--shard-index", str(number), "--processes", str(args.processes),
            "--levels", str(concurrency), "--batch-size", str(args.batch_size),
        ) for number in range(args.processes)]
        await asyncio.gather(*(child.wait() for child in children))
    async with session_factory() as session:
        indexed = await session.scalar(text("SELECT count(*) FROM search_index"))
    index_seconds = time.perf_counter() - started
    if drain is not None:
        await drain(session_factory)
    total_seconds = time.perf_counter() - started
    async with session_factory() as session:
        drift = await session.scalar(text("""
            WITH recount AS (
                SELECT lexeme AS term, count(*) AS frequency
                FROM search_index, unnest(tsvector_to_array(search_vector || code_vector)) AS lexeme
                GROUP BY lexeme
            )
            SELECT count(*) FROM search_terms t
            JOIN recount r USING (term)
            WHERE t.document_frequency <> r.frequency
        """))
    return {"processes": args.processes, "concurrency": concurrency, "indexed": indexed,
            "documents_per_second": round(indexed / total_seconds, 1),
            "index_seconds": round(index_seconds, 2), "total_seconds": round(total_seconds, 2),
            "terms_with_wrong_count": drift}


async def main(args) -> None:
    from backend.db.session import SessionFactory, engine

    try:
        from indexer.vocabulary import drain_vocabulary_changes as drain
    except ImportError:
        drain = None
    logging.disable(logging.WARNING)
    await prepare(SessionFactory, args.documents, vocabulary(args.vocabulary))
    for level in args.levels:
        print(json.dumps(await run_level(SessionFactory, level, args, drain=drain)))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=3000)
    parser.add_argument("--vocabulary", type=int, default=20_000)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=None)
    parser.add_argument("--levels", type=lambda value: [int(item) for item in value.split(",")], default=[1, 2, 4, 8])
    arguments = parser.parse_args()
    url = os.environ.get("BENCH_DATABASE_URL", "")
    try:
        url = benchmark_database_url(url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("DB_POOL_SIZE", "20")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    entry = main if arguments.shard_index is None else shard_main
    # Subprocesses need the default Windows loop; shards need asyncpg's selector.
    if sys.platform == "win32" and arguments.shard_index is not None:
        asyncio.run(entry(arguments), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(entry(arguments))
