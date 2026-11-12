"""Search trade-offs 1-3: ranking function, candidate depth, query length.

From the repository root (any Python env with backend + psutil installed):

  python scripts/tradeoffs/search_bench.py ranking    --rounds 5
  python scripts/tradeoffs/search_bench.py depth      --rounds 3 --depths 50 100 200 500
  python scripts/tradeoffs/search_bench.py complexity --rounds 10

Defaults to the developers_eye_bench copy (see common.default_bench_url).
Read only. Relevance uses the agent-reviewed checklist-25 grades (EXP-0014);
URLs those grades never saw count as irrelevant and are reported as unjudged.

Timing model (all in one process, one connection, like one API request):
  retrieval  = the live text + code + title candidate SQL
  bm25       = rank_candidates (DF + TF/DL batch loads, Python scoring) + metadata filter
  pg_native  = one ORDER BY ts_rank_cd over the same candidate IDs
"cold" clears the per-process DF cache before each query; "warm" reuses it.
PostgreSQL's own buffer cache is never flushed, so "cold" is application-cold.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

COMPLEXITY_QUERIES = {
    1: ["python", "docker", "kubernetes", "react", "postgresql", "typescript", "redis", "nginx"],
    2: ["python async", "docker compose", "react hooks", "postgresql index", "typescript generics",
        "redis cache", "nginx proxy", "git rebase"],
    5: ["python async http client timeout", "docker compose volume mount permissions",
        "react hooks state update effect", "postgresql index scan query plan",
        "typescript generic type constraint inference", "redis cache key expiration policy",
        "nginx reverse proxy websocket upgrade", "git rebase interactive squash commits"],
    10: ["python async http client timeout retry session connection pool error handling",
         "docker compose volume mount permissions linux user group file owner container",
         "react hooks state update effect cleanup dependency array render memo callback",
         "postgresql index scan query plan analyze buffers cost estimate join order",
         "typescript generic type constraint inference conditional mapped keyof infer union",
         "redis cache key expiration policy eviction memory lru ttl persistence cluster",
         "nginx reverse proxy websocket upgrade header timeout buffer ssl certificate config",
         "git rebase interactive squash commits branch merge conflict history force push"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["ranking", "depth", "complexity"])
    parser.add_argument("--database-url")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--depths", type=int, nargs="+", default=[50, 100, 200, 500])
    parser.add_argument("--output", type=Path)
    return parser


async def _retrieve(session, query, mode, categories, depth):
    """The live retrieval SQL with the per-channel limit as a parameter.

    search_text/search_code cap their limit at 100 by validation; the SQL is the
    same, so deeper pools are built from the same statements here.
    """
    from sqlalchemy import REAL, cast, func, select
    from sqlalchemy.dialects.postgresql import ARRAY, array
    from backend.models import SearchIndex
    from backend.search.merge import merge_hits
    from backend.search.query_selector.planner import SearchMode
    from backend.search.retrieval import code as code_mod
    from backend.search.retrieval.fts import CANDIDATE_POOL
    from backend.search.retrieval.titles import TITLE_CANDIDATES, search_titles
    from backend.search.types import RetrievalHit

    groups = []
    if mode in (SearchMode.ALL, SearchMode.TEXT):
        tsquery = func.websearch_to_tsquery("english", query)
        matches = select(SearchIndex.document_id, SearchIndex.search_vector).where(
            SearchIndex.search_vector.bool_op("@@")(tsquery))
        if categories is not None:
            matches = matches.where(SearchIndex.category.in_(categories))
        pool = matches.limit(CANDIDATE_POOL).subquery()
        score = func.ts_rank(cast(array([0.05, 0.10, 0.35, 1.0]), ARRAY(REAL())),
                             pool.c.search_vector, tsquery, 1).label("score")
        rows = (await session.execute(select(pool.c.document_id, score)
                                      .order_by(score.desc(), pool.c.document_id.asc()).limit(depth))).all()
        groups.append([RetrievalHit(document_id=int(r.document_id), search_rank=float(r.score)) for r in rows])
    if mode in (SearchMode.ALL, SearchMode.CODE):
        normalized = code_mod._validate_query(query)
        rows = (await session.execute(code_mod._CODE_SEARCH_SQL, {
            "query_text": normalized, "limit": depth, "offset": 0,
            "dotted": code_mod.dotted_alternatives(normalized), "pool": code_mod.CANDIDATE_POOL,
            "categories": list(categories) if categories is not None else None,
        })).mappings().all()
        groups.append([RetrievalHit(document_id=int(r["document_id"]), code_rank=float(r["score"])) for r in rows])
    groups.append(await search_titles(session, query, limit=TITLE_CANDIDATES, categories=categories))
    return merge_hits(*groups)


async def _pg_order(session, query, mode, ids):
    """PostgreSQL-native order over the same candidates (compare_rankings._native_score)."""
    from sqlalchemy import select
    from backend.models.search_index import SearchIndex
    sys.path.insert(0, str(common.REPO_ROOT / "scripts"))
    from compare_rankings import _native_score
    score = _native_score(query, mode)
    rows = (await session.execute(select(SearchIndex.document_id).where(SearchIndex.document_id.in_(ids))
                                  .order_by(score.desc(), SearchIndex.document_id.asc()))).all()
    return [int(r.document_id) for r in rows]


class Searcher:
    """Runs retrieval and both rankers for one query with stage timings."""

    def __init__(self, session, text_corpus, code_corpus):
        from backend.search.config import SearchConfig
        from backend.search.ranking.statistics import DocumentFrequencyCache
        self.session = session
        self.text_corpus, self.code_corpus = text_corpus, code_corpus
        self.settings = SearchConfig()
        self.df_cache = DocumentFrequencyCache()

    async def run(self, query, mode, source, depth=100, *, warm=False):
        from backend.search.categories import categories_for_filter
        from backend.search.query_analyzer.analyzer import analyze_query
        from backend.search.query_selector.planner import SearchMode, select_query_plan
        from backend.search.ranking.orchestrator import rank_candidates
        from backend.search.service import _metadata_for_candidates
        if not warm:
            self.df_cache.clear()
        normalized = analyze_query(query, config=self.settings)
        plan = select_query_plan(normalized, mode=SearchMode(mode))
        categories = categories_for_filter(source)
        t0 = time.perf_counter()
        hits = await _retrieve(self.session, plan.query, plan.mode, categories, depth)
        t1 = time.perf_counter()
        ranked = await rank_candidates(self.session, plan.query, hits, mode=plan.mode,
                                       text_corpus=self.text_corpus, code_corpus=self.code_corpus,
                                       tokenizer_config=self.settings, df_cache=self.df_cache) if hits else []
        eligible, meta = await _metadata_for_candidates(self.session, ranked, categories)
        t2 = time.perf_counter()
        ids = [h.document_id for h in eligible]
        pg_ids = await _pg_order(self.session, plan.query, plan.mode, ids) if ids else []
        t3 = time.perf_counter()
        url = lambda i: meta[i].canonical_url
        return {
            "candidates": len(hits),
            "retrieval_ms": (t1 - t0) * 1000,
            "bm25_rank_ms": (t2 - t1) * 1000,
            "pg_rank_ms": (t3 - t2) * 1000,
            "bm25_urls": [url(i) for i in ids],
            "pg_urls": [url(i) for i in pg_ids],
        }


async def _setup(args):
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    from backend.search.ranking.statistics import get_corpus_statistics
    session = SessionFactory()
    await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    info = await common.postgres_info(session)
    text_corpus = await get_corpus_statistics(session, "TEXT")
    code_corpus = await get_corpus_statistics(session, "CODE")
    return session, info, Searcher(session, text_corpus, code_corpus)


async def bench_ranking(args):
    queries, qrels = common.load_checklist_queries()
    session, info, searcher = await _setup(args)
    baseline = common.idle_baseline()
    per_query, timings = [], {"cold": {"bm25": [], "pg": [], "retrieval": []},
                              "warm": {"bm25": [], "pg": [], "retrieval": []}}
    with common.ResourceSampler() as sampler:
        for q in queries:
            grades = qrels[q["query_id"]]["judgments"]
            result = None
            for cache in ("cold", "warm"):
                for _ in range(args.rounds):
                    result = await searcher.run(q["query"], q["mode"], q.get("source"), warm=cache == "warm")
                    t = timings[cache]
                    t["retrieval"].append(result["retrieval_ms"])
                    t["bm25"].append(result["retrieval_ms"] + result["bm25_rank_ms"])
                    t["pg"].append(result["retrieval_ms"] + result["pg_rank_ms"])
            bm = common.graded_metrics(result["bm25_urls"], grades)
            pg = common.graded_metrics(result["pg_urls"], grades)
            per_query.append({"query_id": q["query_id"], "query": q["query"], "mode": q["mode"],
                              "candidates": result["candidates"], "bm25": bm, "postgresql": pg})
            print(q["query_id"], f"bm25 nDCG={bm['ndcg_at_k']} pg nDCG={pg['ndcg_at_k']}", flush=True)
    await session.close()

    def agg(ranker):
        rows = [r[ranker] for r in per_query]
        return {"p_at_10": common.mean_of(rows, "p_at_k"), "mrr_at_10": common.mean_of(rows, "mrr_at_k"),
                "ndcg_at_10": common.mean_of(rows, "ndcg_at_k"),
                "judged_share_of_top10": round(sum(r["judged_in_top_k"] for r in rows) /
                                               max(1, sum(r["returned"] for r in rows)), 4)}
    common.write_report("01-ranking-bm25-vs-pg", {
        "postgres": info, "idle_baseline": baseline, "rounds_per_query": args.rounds,
        "labels": "agent-reviewed checklist-25 qrels (EXP-0014); not human judgments",
        "relevance": {"bm25": agg("bm25"), "postgresql": agg("postgresql")},
        "latency": {cache: {k: common.summarize(v) for k, v in d.items()} for cache, d in timings.items()},
        "resources": sampler.report(), "per_query": per_query,
    }, args.output)


async def bench_depth(args):
    import backend.search.ranking.orchestrator as orchestrator
    import backend.search.ranking.statistics as statistics
    # The live ranker refuses more than 256 candidates; deeper pools need a larger cap here only.
    orchestrator.MAX_CANDIDATES = statistics.MAX_CANDIDATES = 4096
    queries, qrels = common.load_checklist_queries()
    session, info, searcher = await _setup(args)
    results = {}
    for depth in args.depths:
        rows, lat, cands = [], [], []
        with common.ResourceSampler() as sampler:
            for q in queries:
                grades = qrels[q["query_id"]]["judgments"]
                positives = {u for u, g in grades.items() if g and g > 0}
                for _ in range(args.rounds):
                    r = await searcher.run(q["query"], q["mode"], q.get("source"), depth, warm=True)
                    lat.append(r["retrieval_ms"] + r["bm25_rank_ms"])
                cands.append(r["candidates"])
                m = common.graded_metrics(r["bm25_urls"], grades)
                m["recall_at_100"] = (len(positives & set(r["bm25_urls"][:100])) / len(positives)) if positives else None
                m["candidate_recall"] = (len(positives & set(r["bm25_urls"])) / len(positives)) if positives else None
                rows.append(m)
        res = sampler.report()
        results[str(depth)] = {
            "mean_candidates": round(sum(cands) / len(cands), 1),
            "judged_recall_at_100": common.mean_of(rows, "recall_at_100"),
            "judged_candidate_recall": common.mean_of(rows, "candidate_recall"),
            "ndcg_at_10": common.mean_of(rows, "ndcg_at_k"),
            "p_at_10": common.mean_of(rows, "p_at_k"),
            "judged_share_of_top10": round(sum(r["judged_in_top_k"] for r in rows) / max(1, sum(r["returned"] for r in rows)), 4),
            "latency_warm_df": common.summarize(lat),
            "cpu_ms_per_query": {
                "python": round(res["python_cpu_seconds"] * 1000 / len(lat), 2),
                "postgres": round(res["postgres_cpu_seconds"] * 1000 / len(lat), 2),
            },
            "resources": res,
        }
        print(depth, results[str(depth)]["ndcg_at_10"], results[str(depth)]["latency_warm_df"]["p95_ms"], flush=True)
    await session.close()
    common.write_report("02-candidate-depth", {
        "postgres": info, "rounds_per_query": args.rounds,
        "labels": "agent-reviewed checklist-25 qrels; recall is judged recall over known positives, not corpus recall",
        "note": "depth = candidates per channel (text and code); the title channel always adds up to 30",
        "depths": results}, args.output)


async def bench_complexity(args):
    from sqlalchemy import text
    from backend.search import service
    from backend.search.query_selector.planner import SearchMode
    session, info, searcher = await _setup(args)
    service.set_corpus_statistics(searcher.text_corpus, searcher.code_corpus)
    results = {}
    for terms, queries in COMPLEXITY_QUERIES.items():
        cold, warm, cands, rows = [], [], [], []
        with common.ResourceSampler() as sampler:
            for query in queries:
                for cache, bucket in (("cold", cold), ("warm", warm)):
                    for _ in range(args.rounds):
                        if cache == "cold":
                            service._df_cache.clear()
                        t0 = time.perf_counter()
                        found = await service.search_documents(session, query, mode=SearchMode.ALL, limit=10)
                        bucket.append((time.perf_counter() - t0) * 1000)
                r = await searcher.run(query, "all", None, warm=True)
                cands.append(r["candidates"])
                rows.append(len(found))
        res = sampler.report()
        plan = (await session.execute(text(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT document_id FROM search_index "
            "WHERE search_vector @@ websearch_to_tsquery('english', :q) LIMIT 20000"), {"q": queries[0]})).scalar()
        top = plan[0]["Plan"]
        results[str(terms)] = {
            "queries": queries,
            "mean_candidates": round(sum(cands) / len(cands), 1),
            "queries_with_results": sum(1 for n in rows if n),
            "cold_df": common.summarize(cold),
            "warm_df": common.summarize(warm),
            "cpu_ms_per_query": {
                "python": round(res["python_cpu_seconds"] * 1000 / (len(cold) + len(warm)), 2),
                "postgres": round(res["postgres_cpu_seconds"] * 1000 / (len(cold) + len(warm)), 2),
            },
            "text_match_plan": {
                "query": queries[0],
                "execution_ms": plan[0].get("Execution Time"),
                "top_node": top.get("Node Type"),
                "nodes": _plan_nodes(top),
                "shared_hit_blocks": top.get("Shared Hit Blocks"),
                "shared_read_blocks": top.get("Shared Read Blocks"),
            },
            "resources": res,
        }
        print(terms, results[str(terms)]["cold_df"]["p95_ms"], results[str(terms)]["warm_df"]["p95_ms"], flush=True)
    await session.close()
    common.write_report("03-query-complexity", {
        "postgres": info, "rounds_per_query": args.rounds,
        "note": "full search_documents() (retrieval, BM25, metadata, snippets) in one process; mode=all, limit=10",
        "terms": results}, args.output)


def _plan_nodes(node, depth=0):
    out = [f"{'  ' * depth}{node.get('Node Type')} rows={node.get('Actual Rows')} ms={node.get('Actual Total Time')}"]
    for child in node.get("Plans", []):
        out.extend(_plan_nodes(child, depth + 1))
    return out


async def main(args):
    from backend.db.session import engine
    try:
        await {"ranking": bench_ranking, "depth": bench_depth, "complexity": bench_complexity}[args.what](args)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    common.configure(arguments.database_url)
    common.run(main(arguments))
