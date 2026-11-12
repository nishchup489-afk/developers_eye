"""Indexer trade-offs 7, 8 and 13: batch size, concurrency, vocabulary refresh.

Run from the repository root with the crawler environment (it has indexer installed):

  python backend/scripts/tradeoffs/indexer_bench.py batch       --docs 3000 --sizes 25 50 100 250 500
  python backend/scripts/tradeoffs/indexer_bench.py concurrency --docs 3000 --workers 1 2 4 8
  python backend/scripts/tradeoffs/indexer_bench.py processes   --docs 3000 --processes 1 2 4
  python backend/scripts/tradeoffs/indexer_bench.py vocabulary  --docs 2000

WRITES to the benchmark copy only (common.configure refuses other databases).
Each run first deletes the search_index rows of a fixed random sample of
documents, so the indexer rebuilds them exactly as it indexes new pages. It then
runs the real indexer code (index_candidate: load, analyze, build vectors,
persist under FOR UPDATE, queue vocabulary change) in batches, draining the
vocabulary outbox after every batch the way run_worker does. Only the candidate
selection scan is replaced by the sampled ID list, so unrelated unindexable
rows in the copy cannot add noise.

Lock waits: a separate connection samples pg_stat_activity every 50 ms and counts
sessions of this database whose wait_event_type is 'Lock'.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SAMPLE_SEED = 20261112


async def sample_ids(session, n: int, seed: int = SAMPLE_SEED) -> list[int]:
    from sqlalchemy import text
    ids = (await session.execute(text(
        "SELECT s.document_id FROM search_index s JOIN document d ON d.id = s.document_id "
        "WHERE d.is_available ORDER BY s.document_id"))).scalars().all()
    rng = random.Random(seed)
    return sorted(rng.sample(list(ids), n))


async def table_counters(session) -> dict:
    from sqlalchemy import text
    rows = (await session.execute(text(
        "SELECT relname, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables "
        "WHERE relname IN ('search_index','search_terms','vocabulary_change')"))).all()
    wal = await session.scalar(text("SELECT pg_current_wal_lsn()::text"))
    return {"tables": {r.relname: r.n_tup_ins + r.n_tup_upd + r.n_tup_del for r in rows}, "wal_lsn": wal}


async def wal_bytes(session, start_lsn: str) -> int:
    from sqlalchemy import text
    return int(await session.scalar(text("SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), CAST(CAST(:l AS text) AS pg_lsn))"),
                                    {"l": start_lsn}))


async def reset_sample(ids: list[int]) -> None:
    """Remove the sample's index rows so the next run rebuilds them (bench copy only)."""
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session, session.begin():
        await session.execute(text("DELETE FROM search_index WHERE document_id = ANY(:ids)"), {"ids": ids})
        await session.execute(text("DELETE FROM vocabulary_change"))
    from backend.db.session import engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("VACUUM (ANALYZE) search_index"))


class LockSampler:
    def __init__(self, url: str):
        self.url = url.replace("+asyncpg", "")
        self.samples = 0
        self.waiting = 0
        self.max_waiting = 0

    async def __aenter__(self):
        import asyncpg
        self.conn = await asyncpg.connect(self.url)
        self.task = asyncio.create_task(self._loop())
        return self

    async def _loop(self):
        while True:
            n = await self.conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                "AND wait_event_type = 'Lock'")
            self.samples += 1
            self.waiting += n
            self.max_waiting = max(self.max_waiting, n)
            await asyncio.sleep(0.05)

    async def __aexit__(self, *exc):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        await self.conn.close()

    def report(self):
        return {"samples": self.samples, "mean_sessions_waiting_on_locks": round(self.waiting / max(1, self.samples), 3),
                "max_sessions_waiting_on_locks": self.max_waiting}


async def index_ids(ids: list[int], *, batch_size: int, concurrency: int) -> dict:
    """The work of indexer.worker.runner.run_worker over a fixed ID list."""
    from sqlalchemy import select
    from backend.db.session import SessionFactory
    from backend.models.documents import Document
    from indexer.config import IndexerConfig
    from indexer.schemas import IndexCandidate
    from indexer.vocabulary import drain_vocabulary_changes
    from indexer.worker.runner import _process_index
    import logging
    logging.getLogger("indexer.worker.runner").setLevel(logging.WARNING)
    config = IndexerConfig(batch_size=batch_size, concurrency=concurrency)
    outcomes: Counter[str] = Counter()
    batch_ms, doc_ms, drain_ms = [], [], []
    for start in range(0, len(ids), batch_size):
        chunk = ids[start:start + batch_size]
        t0 = time.perf_counter()
        async with SessionFactory() as session:
            rows = (await session.execute(select(Document.id, Document.updated_at)
                                          .where(Document.id.in_(chunk)).order_by(Document.id))).all()
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(*(
            _process_index(SessionFactory, IndexCandidate(document_id=i, source_updated_at=u), config, semaphore)
            for i, u in rows))
        t1 = time.perf_counter()
        await drain_vocabulary_changes(SessionFactory)
        t2 = time.perf_counter()
        batch_ms.append((t2 - t0) * 1000)
        drain_ms.append((t2 - t1) * 1000)
        for result in results:
            outcomes[result.status.value] += 1
            doc_ms.append(result.duration_ms)
    return {"outcomes": dict(outcomes), "batch_ms": common.summarize(batch_ms),
            "per_document_ms": common.summarize(doc_ms), "drain_ms": common.summarize(drain_ms)}


async def measured_run(url: str, ids: list[int], label: str, work) -> dict:
    from backend.db.session import SessionFactory
    await reset_sample(ids)
    async with SessionFactory() as session:
        before = await table_counters(session)
    async with LockSampler(url) as locks:
        with common.ResourceSampler() as sampler:
            t0 = time.perf_counter()
            detail = await work()
            wall = time.perf_counter() - t0
    await asyncio.sleep(1.5)  # cumulative statistics are flushed to shared memory lazily
    async with SessionFactory() as session:
        after = await table_counters(session)
        wal = await wal_bytes(session, before["wal_lsn"])
    indexed = detail.get("outcomes", {}).get("indexed", len(ids))
    row = {
        "label": label, "documents": len(ids), "indexed": indexed,
        "seconds": round(wall, 2), "docs_per_second": round(indexed / wall, 2),
        "wal_mb": round(wal / 2**20, 2), "wal_kb_per_document": round(wal / 1024 / max(1, indexed), 2),
        "row_writes": {t: after["tables"].get(t, 0) - before["tables"].get(t, 0) for t in before["tables"]},
        "locks": locks.report(), "resources": sampler.report(), **detail,
    }
    print(label, row["docs_per_second"], "docs/s", row["locks"], flush=True)
    return row


async def bench_batch(args, url):
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        ids = await sample_ids(session, args.docs)
        info = await common.postgres_info(session)
    rows = [await measured_run(url, ids, f"batch={b}", lambda b=b: index_ids(ids, batch_size=b, concurrency=args.concurrency))
            for b in args.sizes]
    common.write_report("07-indexer-batch-size", {"postgres": info, "concurrency": args.concurrency,
                                                  "pool": os.environ.get("DB_POOL_SIZE"), "runs": rows}, args.output)


async def bench_concurrency(args, url):
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        ids = await sample_ids(session, args.docs)
        info = await common.postgres_info(session)
    rows = [await measured_run(url, ids, f"concurrency={c}", lambda c=c: index_ids(ids, batch_size=args.batch_size, concurrency=c))
            for c in args.workers]
    common.write_report("08-indexer-concurrency", {"postgres": info, "batch_size": args.batch_size,
                                                   "pool": os.environ.get("DB_POOL_SIZE"), "runs": rows}, args.output)


async def bench_processes(args, url):
    """N separate indexer processes, each owning id % N == k of the sample (like INDEXER_SHARD_*)."""
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        ids = await sample_ids(session, args.docs)
    # Children get the exact ID list: after the reset these documents have no
    # index rows, so sampling again in the child would pick other documents.
    ids_file = common.REPORT_DIR / ".indexer-sample-ids.json"
    ids_file.parent.mkdir(parents=True, exist_ok=True)
    ids_file.write_text(json.dumps(ids), encoding="utf-8")
    rows = []
    for n in args.processes:
        async def work(n=n):
            procs = [subprocess.Popen(
                [sys.executable, __file__, "_shard", "--database-url", url, "--ids-file", str(ids_file),
                 "--shard-count", str(n), "--shard-index", str(k), "--batch-size", str(args.batch_size),
                 "--concurrency", str(args.concurrency)],
                stdout=subprocess.PIPE, text=True) for k in range(n)]
            outs = await asyncio.gather(*(asyncio.to_thread(p.communicate) for p in procs))
            merged: Counter[str] = Counter()
            for out, _ in outs:
                merged.update(json.loads(out.strip().splitlines()[-1])["outcomes"])
            return {"outcomes": dict(merged), "processes": n}
        rows.append(await measured_run(url, ids, f"processes={n}", work))
    ids_file.unlink(missing_ok=True)
    common.write_report("08b-indexer-processes", {"batch_size": args.batch_size, "concurrency_per_process": args.concurrency,
                                                  "pool_per_process": os.environ.get("DB_POOL_SIZE"), "runs": rows}, args.output)


async def shard_worker(args):
    from backend.db.session import SessionFactory
    ids = [i for i in json.loads(Path(args.ids_file).read_text(encoding="utf-8"))
           if i % args.shard_count == args.shard_index]
    result = await index_ids(ids, batch_size=args.batch_size, concurrency=args.concurrency)
    print(json.dumps(result))


async def direct_upsert(ids: list[int], concurrency: int) -> dict:
    """Strategy B: every indexed document updates search_terms in its own transaction.

    This is the design the outbox replaced (EXP-0006): a common term's row is
    updated once per document, so concurrent writers queue on the same rows.
    Applied to the same lexeme sets the indexer just wrote.
    """
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    semaphore = asyncio.Semaphore(concurrency)
    per_doc = []

    from indexer.vocabulary import vocabulary_terms

    async def one(doc_id: int):
        async with semaphore:
            t0 = time.perf_counter()
            async with SessionFactory() as session, session.begin():
                lexemes = await session.scalar(text(
                    "SELECT tsvector_to_array(search_vector || code_vector) FROM search_index "
                    "WHERE document_id = :id"), {"id": doc_id})
                terms = sorted(vocabulary_terms(lexemes or ()))  # sorted: fixed lock order, no deadlocks
                await session.execute(text("""
                    INSERT INTO search_terms (term, document_frequency)
                    SELECT unnest(CAST(:terms AS text[])), 1
                    ON CONFLICT (term) DO UPDATE SET document_frequency = search_terms.document_frequency + 1
                """), {"terms": terms})
            per_doc.append((time.perf_counter() - t0) * 1000)
    await asyncio.gather(*(one(i) for i in ids))
    return {"outcomes": {"indexed": len(ids)}, "per_document_ms": common.summarize(per_doc)}


async def bench_vocabulary(args, url):
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    from indexer.vocabulary_rebuild import rebuild_vocabulary
    async with SessionFactory() as session:
        ids = await sample_ids(session, args.docs)
        terms = await session.scalar(text("SELECT count(*) FROM search_terms"))
    # A: the shipped outbox (queue rows per document, drained in summed batches).
    outbox = await measured_run(url, ids, "outbox", lambda: index_ids(ids, batch_size=200, concurrency=args.concurrency))
    # The indexer's own writes are the same in B and C, so measure only the vocabulary part:
    # index without draining (changes stay queued), then apply each strategy alone.
    async def index_only():
        import indexer.vocabulary as vocabulary
        original = vocabulary.drain_vocabulary_changes

        async def no_drain(*_args, **_kwargs):
            return 0
        vocabulary.drain_vocabulary_changes = no_drain
        try:
            return await index_ids(ids, batch_size=200, concurrency=args.concurrency)
        finally:
            vocabulary.drain_vocabulary_changes = original
    await measured_run(url, ids, "index-without-drain", index_only)
    async with SessionFactory() as session, session.begin():
        await session.execute(text("DELETE FROM vocabulary_change"))
    direct = await measured_run_existing(url, ids, "direct-upsert", lambda: direct_upsert(ids, args.concurrency))
    rebuild = await measured_run_existing(url, ids, "full-rebuild", lambda: _rebuild(rebuild_vocabulary))
    common.write_report("13-vocabulary-refresh", {
        "documents": len(ids), "search_terms_rows": terms, "concurrency": args.concurrency,
        "strategies": {"outbox": outbox, "direct_upsert": direct, "full_rebuild": rebuild}}, args.output)


async def _rebuild(rebuild_vocabulary):
    from backend.db.session import SessionFactory
    docs, terms = await rebuild_vocabulary(SessionFactory, progress_every=10**9)
    return {"outcomes": {"indexed": docs}, "documents_scanned": docs, "terms_written": terms}


async def measured_run_existing(url, ids, label, work):
    """measured_run without resetting the sample (the index rows must stay)."""
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        before = await table_counters(session)
    async with LockSampler(url) as locks:
        with common.ResourceSampler() as sampler:
            t0 = time.perf_counter()
            detail = await work()
            wall = time.perf_counter() - t0
    await asyncio.sleep(1.5)  # cumulative statistics are flushed to shared memory lazily
    async with SessionFactory() as session:
        after = await table_counters(session)
        wal = await wal_bytes(session, before["wal_lsn"])
    row = {"label": label, "documents": len(ids), "seconds": round(wall, 2),
           "wal_mb": round(wal / 2**20, 2), "wal_kb_per_document": round(wal / 1024 / len(ids), 2),
           "row_writes": {t: after["tables"].get(t, 0) - before["tables"].get(t, 0) for t in before["tables"]},
           "locks": locks.report(), "resources": sampler.report(), **detail}
    print(label, row["seconds"], "s", row["locks"], flush=True)
    return row


async def main(args, url):
    from backend.db.session import engine
    try:
        if args.what == "_shard":
            await shard_worker(args)
        else:
            await {"batch": bench_batch, "concurrency": bench_concurrency, "processes": bench_processes,
                   "vocabulary": bench_vocabulary}[args.what](args, url)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["batch", "concurrency", "processes", "vocabulary", "_shard"])
    parser.add_argument("--database-url")
    parser.add_argument("--docs", type=int, default=3000)
    parser.add_argument("--sizes", type=int, nargs="+", default=[25, 50, 100, 250, 500])
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--processes", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--pool-size", type=int, default=None)
    parser.add_argument("--ids-file")
    parser.add_argument("--output", type=Path)
    a = parser.parse_args()
    biggest = max(a.workers + [a.concurrency]) if a.what == "concurrency" else a.concurrency
    pool = a.pool_size or biggest + 1
    u = common.configure(a.database_url, pool_size=pool, max_overflow=2)
    common.run(main(a, u))
