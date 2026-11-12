"""Read-only, repeatable-read search profiling over the configured corpus.

Run with the crawler environment from the repository root:
    python scripts/profile_search.py --rounds 5 --output backend/reports/checklist/search-before.json

Cold means the application's DF cache is cleared; PostgreSQL/OS caches are not
flushed. No documents, vectors, statistics tables, or database settings are written.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time

from sqlalchemy import event, text
from backend.db.session import SessionFactory, engine
from backend.search.ranking.statistics import get_corpus_statistics
from backend.search.service import _df_cache, search_documents, set_corpus_statistics

QUERIES = {
    "common_text": {"query": "python", "mode": "text"},
    "common_all": {"query": "python async", "mode": "all"},
    "developer_identifier": {"query": "asyncio.create_task", "mode": "code"},
    "fastapi": {"query": "FastAPI Depends", "mode": "all"},
    "filtered": {"query": "fastapi", "mode": "text", "category": "docs"},
    "no_match": {"query": "qqqqzzzz_nonexistent", "mode": "all"},
}


def percentile(values, quantile):
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * quantile) - 1)], 3)


def stage(statement):
    query = statement.lower()
    if "jsonb_object_agg" in query:
        return "candidate_tf_dl"
    if "count(" in query:
        return "document_frequency"
    if "ts_rank" in query:
        return "retrieval"
    if "document." in query:
        return "document_hydration"
    return "query_tokenization"


async def profile(rounds):
    statements = []
    def before(conn, cursor, statement, parameters, context, executemany):
        context.profile_started = time.perf_counter()
    def after(conn, cursor, statement, parameters, context, executemany):
        statements.append({"stage": stage(statement),
                           "ms": (time.perf_counter() - context.profile_started) * 1000})
    event.listen(engine.sync_engine, "before_cursor_execute", before)
    event.listen(engine.sync_engine, "after_cursor_execute", after)
    try:
        async with SessionFactory() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            version = await session.scalar(text("SELECT version()"))
            count = await session.scalar(text("SELECT count(*) FROM search_index"))
            started = time.perf_counter()
            set_corpus_statistics(await get_corpus_statistics(session, "TEXT"),
                                  await get_corpus_statistics(session, "CODE"))
            startup_ms = (time.perf_counter() - started) * 1000
            report = {"created_utc": datetime.now(timezone.utc).isoformat(),
                      "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      "platform": platform.platform(), "python": platform.python_version(),
                      "postgres": version, "documents": count, "rounds": rounds,
                      "snapshot_ms": round(startup_ms, 3),
                      "cold_definition": "application DF cache cleared; shared database/OS caches unchanged",
                      "queries": {}, "plans": {}}
            for name, kwargs in QUERIES.items():
                for cache_mode in ("cold", "warm"):
                    samples, sql_counts, durations, rows = [], [], Counter(), []
                    for _ in range(rounds):
                        if cache_mode == "cold":
                            _df_cache.clear()
                        statements.clear()
                        started = time.perf_counter()
                        results = await search_documents(session, **kwargs)
                        samples.append((time.perf_counter() - started) * 1000)
                        sql_counts.append(len(statements))
                        for statement in statements:
                            durations[statement["stage"]] += statement["ms"]
                        rows = [item.url for item in results]
                    report["queries"][name + "_" + cache_mode] = {
                        **kwargs, "p50_ms": round(statistics.median(samples), 3),
                        "p95_ms": percentile(samples, .95), "p99_ms": percentile(samples, .99),
                        "samples_ms": [round(value, 3) for value in samples],
                        "sql_counts": sql_counts,
                        "mean_sql_stage_ms": {key: round(value / rounds, 3) for key, value in durations.items()},
                        "result_urls": rows,
                    }
                    print(name, cache_mode, report["queries"][name + "_" + cache_mode]["p50_ms"], flush=True)
            for name, query in {
                "common_df": "SELECT count(*) FROM search_index WHERE search_vector @@ 'python'::tsquery",
                "rare_df": "SELECT count(*) FROM search_index WHERE code_vector @@ 'asyncio.create_task'::tsquery",
                "filtered_candidates": "SELECT document_id FROM search_index WHERE search_vector @@ websearch_to_tsquery('english','fastapi') AND category='docs' LIMIT 20000",
            }.items():
                report["plans"][name] = (await session.execute(text(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query))).scalar()
            return report
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before)
        event.remove(engine.sync_engine, "after_cursor_execute", after)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    result = asyncio.run(profile(args.rounds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
