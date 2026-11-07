"""Frozen-corpus relevance evaluation: collect once, judge URLs, score offline.

From backend/:
  poetry run python scripts/evaluate_relevance.py collect \
    --corpus-id dev-local-2026-11-06 \
    --queries evaluation/queries.json \
    --snapshot reports/exp-0004-snapshot.json \
    --judgment-template reports/exp-0004-qrels.json

  # Manually grade every URL in the generated qrels (0=irrelevant, 3=ideal).
  # Add independently known relevant URLs even when not retrieved.
  poetry run python scripts/evaluate_relevance.py score \
    --snapshot reports/exp-0004-snapshot.json \
    --qrels reports/exp-0004-qrels.json \
    --output reports/exp-0004-results.json

The collect phase is READ ONLY. A repeatable-read transaction freezes the
view for all queries; a single TEXT/CODE statistics scan is reused. The
score phase needs neither PostgreSQL nor network access.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never silently overwrite judgments; partial manual annotations are work.
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def load_queries(path: Path) -> list[dict[str, str]]:
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("queries"), list):
        raise ValueError("manifest must be an object containing a queries list")
    queries = data["queries"]
    if not queries:
        raise ValueError("query manifest is empty")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in queries:
        if not isinstance(entry, dict):
            raise ValueError("each query must be an object")
        qid, query, mode = (entry.get(key) for key in ("query_id", "query", "mode"))
        if not isinstance(qid, str) or not qid or qid in seen:
            raise ValueError("query IDs must be nonempty and unique")
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError(f"query {qid} is invalid")
        if mode not in ("text", "code", "all"):
            raise ValueError(f"query {qid} has an invalid mode")
        stratum = entry.get("stratum", "unspecified")
        if not isinstance(stratum, str) or not stratum.strip():
            raise ValueError(f"query {qid} has an invalid stratum")
        seen.add(qid)
        result.append({"query_id": qid, "query": query, "mode": mode, "stratum": stratum})
    return result


def judgment_template(snapshot: dict[str, Any]) -> dict[str, Any]:
    queries: dict[str, Any] = {}
    for report in snapshot["reports"]:
        ranked = sorted(report["documents"], key=lambda row: row["bm25_rank"])
        baseline = sorted(report["documents"], key=lambda row: row["postgres_rank"])
        urls = dict.fromkeys(
            str(row["url"]) for row in (ranked[:10] + baseline[:10])
        )
        queries[report["query_id"]] = {
            "judgments": {url: None for url in urls},
            "no_relevant_documents": False,
        }
    return {
        "instructions": (
            "Grade all top-10 pooled URLs: 0=irrelevant, 1=marginal, "
            "2=useful, 3=ideal. Add known relevant URLs from outside the "
            "candidate pool; otherwise recall is biased upwards. "
            "Set no_relevant_documents=true only after confirming no relevant "
            "document exists in the frozen corpus."
        ),
        "corpus_id": snapshot["corpus_id"],
        "queries": queries,
    }


async def collect(
    manifest: list[dict[str, str]],
    corpus_id: str,
) -> dict[str, Any]:
    from sqlalchemy import text
    from backend.db.session import SessionFactory, engine
    from backend.search.query_selector.planner import SearchMode
    from backend.search.ranking.statistics import get_corpus_statistics
    from compare_rankings import compare_one

    try:
        async with SessionFactory() as session:
            async with session.begin():
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                text_corpus = await get_corpus_statistics(session, "TEXT")
                code_corpus = await get_corpus_statistics(session, "CODE")

                reports = []
                for position, item in enumerate(manifest, start=1):
                    print(f"[{position}/{len(manifest)}] {item['query_id']}  {item['query']}")
                    report = await compare_one(
                        session,
                        item["query"],
                        SearchMode(item["mode"]),
                        k=10,
                        text_corpus=text_corpus,
                        code_corpus=code_corpus,
                    )
                    report.update(query_id=item["query_id"], stratum=item["stratum"])
                    reports.append(report)
        return {
            "schema_version": 1,
            "corpus_id": corpus_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "retrieval_budget": "100 candidates per channel (ALL: union of up to 200)",
            "postgres_baseline": "ts_rank_cd(text, 0) + ts_rank_cd(code, 32), same candidate set",
            "reports": reports,
        }
    finally:
        await engine.dispose()


def display_results(results: dict[str, Any]) -> None:
    print(f"Corpus: {results['corpus_id']}")
    print(f"Queries: {results['query_count']}")
    if results["status"] != "complete":
        print(f"STATUS: INCOMPLETE; {len(results['unjudged_query_ids'])} queries still need judgments.")
        for item in results["per_query"]:
            if item["status"] == "incomplete":
                print(f"  {item['query_id']}: {item['reason']} "
                      f"({len(item['missing_top_10_judgments'])} missing top-10 URLs)")
        return
    aggregate = results["aggregate"]
    print("Metric                             BM25          PostgreSQL")
    for key in ("precision_at_10", "mrr_at_10", "ndcg_at_10"):
        a, b = aggregate["bm25"][key], aggregate["postgresql"][key]
        print(f"{key:30} {a if a is not None else 'N/A':>12} "
              f"{b if b is not None else 'N/A':>18}")
    print(f"Judged candidate recall (100/channel): "
          f"{aggregate['candidate_recall_at_100_per_channel']}")
    print("Only judged relevance determines which ranker performs better.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collecting = commands.add_parser("collect", help="Read-only PostgreSQL capture and qrel template")
    collecting.add_argument("--queries", type=Path, required=True)
    collecting.add_argument("--corpus-id", required=True)
    collecting.add_argument("--snapshot", type=Path, required=True)
    collecting.add_argument("--judgment-template", type=Path, required=True)

    scoring = commands.add_parser("score", help="Score frozen snapshot against manual judgments")
    scoring.add_argument("--snapshot", type=Path, required=True)
    scoring.add_argument("--qrels", type=Path, required=True)
    scoring.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "collect":
        if not args.corpus_id.strip():
            parser.error("--corpus-id must not be blank")
        if args.snapshot.exists() or args.judgment_template.exists():
            parser.error("snapshot/template already exists; choose new paths to preserve judgments")
        if args.snapshot.resolve() == args.judgment_template.resolve():
            parser.error("snapshot and judgment template must be different files")
        snapshot = asyncio.run(collect(load_queries(args.queries), args.corpus_id))
        write_json(args.snapshot, snapshot)
        write_json(args.judgment_template, judgment_template(snapshot))
        print(f"Snapshot saved to {args.snapshot}")
        print(f"Judgment template saved to {args.judgment_template}")
        return 0

    from backend.search.evaluation.metrics import evaluate_suite

    snapshot, qrels = read_json(args.snapshot), read_json(args.qrels)
    if snapshot.get("corpus_id") != qrels.get("corpus_id"):
        parser.error("snapshot and judgments have different corpus_id values")
    results = evaluate_suite(snapshot, qrels)
    write_json(args.output, results, overwrite=True)
    display_results(results)
    return 0 if results["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
