"""Storage trade-offs 11 and 12: corpus scaling and PostgreSQL index alternatives.

From the repository root, on the benchmark copy (it creates schemas there):

  python backend/scripts/tradeoffs/storage_bench.py scaling --sizes 10000 50000 100000 --rounds 3
  python backend/scripts/tradeoffs/storage_bench.py indexes --insert-rows 2000

scaling: copies a deterministic sample of search_index rows (ordered by
md5(document_id)) into schema c<size>, with the same indexes, and runs the real
search_documents() with search_path = c<size>, public. The document table stays
shared, so only the index side shrinks, which is what grows with the corpus.
The full size uses public.search_index itself. Sizes the copy does not have are
extrapolated linearly in guide/tradeoffs_calculation.md, never measured here.

indexes: copies search_index (no indexes) into schema idx and compares the
search_vector index choices: none, GIN (fastupdate on, the default), GIN with
fastupdate off, and GiST. Per variant: build time, size, match-query latency,
and the time to insert rows with that index in place.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SCALING_QUERIES = [
    ("python", "all"), ("docker", "all"), ("react hooks", "all"), ("postgresql index", "text"),
    ("asyncio gather", "all"), ("FastAPI Depends", "all"), ("typescript generics", "text"),
    ("git rebase", "all"), ("redis cache", "all"), ("kubernetes deployment", "text"),
    ("asyncio.create_task", "code"), ("useEffect cleanup", "all"),
]
MATCH_SQL = ("SELECT document_id FROM {table} WHERE search_vector @@ websearch_to_tsquery('english', :q) "
             "LIMIT 20000")

_search_path = {"value": "public"}


async def _autocommit(sql: str, params: dict | None = None):
    from sqlalchemy import text
    from backend.db.session import engine
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        return await conn.execute(text(sql), params or {})


async def _scalar(sql: str, params: dict | None = None):
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        return await session.scalar(text(sql), params or {})


async def relation_sizes(schema: str) -> dict:
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        rows = (await session.execute(text(
            "SELECT c.relname, c.relkind::text AS relkind, pg_relation_size(c.oid) AS main, pg_total_relation_size(c.oid) AS total "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :s AND (c.relname = 'search_index' OR c.relname LIKE '%search_index%')"),
            {"s": schema})).all()
    mb = lambda b: round(b / 2**20, 1)
    table = next(r for r in rows if r.relkind == "r")
    return {"table_total_mb": mb(table.total), "table_heap_mb": mb(table.main),
            "toast_and_other_mb": mb(table.total - table.main - sum(r.main for r in rows if r.relkind == "i")),
            "indexes_mb": {r.relname: mb(r.main) for r in rows if r.relkind == "i"}}


async def build_sample(size: int) -> str:
    schema = f"c{size}"
    exists = await _scalar("SELECT count(*) FROM pg_namespace WHERE nspname = :s", {"s": schema})
    if exists:
        return schema
    t0 = time.perf_counter()
    await _autocommit(f"CREATE SCHEMA {schema}")
    await _autocommit(f"CREATE TABLE {schema}.search_index (LIKE public.search_index INCLUDING DEFAULTS INCLUDING GENERATED)")
    await _autocommit(f"INSERT INTO {schema}.search_index SELECT * FROM public.search_index "
                      f"ORDER BY md5(document_id::text) LIMIT {size}")
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        defs = (await session.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'search_index'"))).scalars().all()
    for definition in defs:
        await _autocommit(definition.replace(" ON public.search_index", f" ON {schema}.search_index")
                          .replace("CREATE UNIQUE INDEX ", f"CREATE UNIQUE INDEX {schema}_")
                          .replace("CREATE INDEX ", f"CREATE INDEX {schema}_"))
    await _autocommit(f"VACUUM (ANALYZE) {schema}.search_index")
    print(f"built {schema} in {time.perf_counter() - t0:.1f}s", flush=True)
    return schema


def _install_search_path_hook():
    from sqlalchemy import event
    from backend.db.session import engine

    @event.listens_for(engine.sync_engine, "connect")
    def set_path(dbapi_connection, _record):
        path = _search_path["value"]
        dbapi_connection.run_async(lambda conn: conn.execute(f"SET search_path TO {path}"))


async def bench_scaling(args):
    from backend.db.session import SessionFactory, engine
    from backend.search import service
    from backend.search.ranking.statistics import get_corpus_statistics
    _install_search_path_hook()
    full = await _scalar("SELECT count(*) FROM public.search_index")
    results = {}
    for size in args.sizes:
        schema = "public" if size >= full else await build_sample(size)
        _search_path["value"] = f"{schema}, public"
        await engine.dispose()
        async with SessionFactory() as session:
            rows = await session.scalar(__import__("sqlalchemy").text("SELECT count(*) FROM search_index"))
            service.set_corpus_statistics(await get_corpus_statistics(session, "TEXT"),
                                          await get_corpus_statistics(session, "CODE"))
            cold, warm, matches = [], [], []
            with common.ResourceSampler() as sampler:
                for query, mode in SCALING_QUERIES:
                    for cache, bucket in (("cold", cold), ("warm", warm)):
                        for _ in range(args.rounds):
                            if cache == "cold":
                                service._df_cache.clear()
                            t0 = time.perf_counter()
                            await service.search_documents(session, query, mode=mode, limit=10)
                            bucket.append((time.perf_counter() - t0) * 1000)
                    matches.append(await session.scalar(__import__("sqlalchemy").text(
                        "SELECT count(*) FROM search_index WHERE search_vector @@ websearch_to_tsquery('english', :q)"),
                        {"q": query}))
        sizes = await relation_sizes(schema)
        res = sampler.report()
        results[str(size)] = {
            "schema": schema, "rows": rows, **sizes,
            "mb_per_1000_docs": round(sizes["table_total_mb"] / rows * 1000, 3),
            "mean_text_matches_per_query": round(sum(matches) / len(matches), 1),
            "cold_df": common.summarize(cold), "warm_df": common.summarize(warm),
            "peak_postgres_rss_mb": res["peak_postgres_rss_mb"], "resources": res,
        }
        print(size, sizes["table_total_mb"], "MB", results[str(size)]["cold_df"]["p95_ms"], flush=True)
    async with SessionFactory() as session:
        info = await common.postgres_info(session)
    common.write_report("11-corpus-scaling", {
        "postgres": info, "rounds_per_query": args.rounds, "queries": SCALING_QUERIES,
        "note": "search_index sampled per size; document table shared; search_documents() end to end",
        "sizes": results}, args.output)


async def bench_indexes(args):
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    await _autocommit("DROP SCHEMA IF EXISTS idx CASCADE")
    await _autocommit("CREATE SCHEMA idx")
    await _autocommit("CREATE TABLE idx.search_index AS SELECT * FROM public.search_index")
    await _autocommit("CREATE TABLE idx.spare AS SELECT * FROM idx.search_index ORDER BY md5(document_id::text) "
                      f"LIMIT {args.insert_rows}")
    await _autocommit("VACUUM (ANALYZE) idx.search_index")
    queries = [q for q, _ in SCALING_QUERIES]
    variants = {
        "none (sequential scan)": None,
        "GIN fastupdate=on (current)": "CREATE INDEX idx_v ON idx.search_index USING gin (search_vector)",
        "GIN fastupdate=off": "CREATE INDEX idx_v ON idx.search_index USING gin (search_vector) WITH (fastupdate = off)",
        "GiST": "CREATE INDEX idx_v ON idx.search_index USING gist (search_vector)",
    }
    rows = []
    for name, ddl in variants.items():
        await _autocommit("DROP INDEX IF EXISTS idx.idx_v")
        build = 0.0
        if ddl:
            t0 = time.perf_counter()
            await _autocommit(ddl)
            build = time.perf_counter() - t0
        await _autocommit("ANALYZE idx.search_index")
        size = await _scalar("SELECT coalesce(pg_relation_size('idx.idx_v'::regclass), 0)") if ddl else 0
        lat = []
        async with SessionFactory() as session:
            await session.execute(text("SET LOCAL statement_timeout = '60s'"))
            for q in queries:
                await session.execute(text(MATCH_SQL.format(table="idx.search_index")), {"q": q})  # warm
                for _ in range(args.rounds):
                    t0 = time.perf_counter()
                    await session.execute(text(MATCH_SQL.format(table="idx.search_index")), {"q": q})
                    lat.append((time.perf_counter() - t0) * 1000)
            plan = (await session.execute(text("EXPLAIN (FORMAT JSON) " + MATCH_SQL.format(table="idx.search_index")),
                                          {"q": "python"})).scalar()
        # Insert overhead: delete the spare rows, then insert them back with the index in place.
        await _autocommit("DELETE FROM idx.search_index WHERE document_id IN (SELECT document_id FROM idx.spare)")
        t0 = time.perf_counter()
        async with SessionFactory() as session, session.begin():
            for start in range(0, args.insert_rows, 100):
                await session.execute(text(
                    "INSERT INTO idx.search_index SELECT * FROM idx.spare ORDER BY document_id "
                    f"OFFSET {start} LIMIT 100"))
        insert_s = time.perf_counter() - t0
        rows.append({
            "variant": name, "build_seconds": round(build, 2), "index_mb": round(size / 2**20, 1),
            "match_query": common.summarize(lat), "plan_for_python": _node(plan[0]["Plan"]),
            "insert_rows": args.insert_rows, "insert_ms_per_row": round(insert_s * 1000 / args.insert_rows, 3),
        })
        print(name, rows[-1]["index_mb"], rows[-1]["match_query"]["p50_ms"], rows[-1]["insert_ms_per_row"], flush=True)
    await _autocommit("DROP SCHEMA idx CASCADE")
    common.write_report("12-index-alternatives", {
        "table_rows": await _scalar("SELECT count(*) FROM public.search_index"),
        "query": MATCH_SQL.format(table="search_index"), "queries": queries, "rounds": args.rounds,
        "variants": rows}, args.output)


def _node(node):
    child = node.get("Plans", [{}])[0] if node.get("Plans") else {}
    return f"{node.get('Node Type')} > {child.get('Node Type', '-')}"


async def main(args):
    from backend.db.session import engine
    try:
        await (bench_scaling if args.what == "scaling" else bench_indexes)(args)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["scaling", "indexes"])
    parser.add_argument("--database-url")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000])
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--insert-rows", type=int, default=2000)
    parser.add_argument("--output", type=Path)
    a = parser.parse_args()
    common.configure(a.database_url)
    common.run(main(a))
