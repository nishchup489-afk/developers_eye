"""EXP-0009: Human-judged lexical search relevance evaluation.

Works against the JSON saved by scripts/search_relevance_diagnostics/diagnose_relevance.py.
No database access. No invented relevance labels. No third-party dependencies.

Prepare a human-review CSV using a UNION of BM25/PostgreSQL top-N results:
  python scripts/search_relevance_metrics/evaluate_relevance.py prepare \
    --diagnostics reports/exp-0004/RUN/diagnostics.json \
    --qrels evaluation/exp-0009/qrels.csv --depth 20 --include Q051:51

Human enters grades 0,1,2,3 in relevance_grade (blank = unjudged).

Score only queries with every result in BOTH top-10 lists judged:
  python scripts/search_relevance_metrics/evaluate_relevance.py score \
    --diagnostics reports/exp-0004/RUN/diagnostics.json \
    --qrels evaluation/exp-0009/qrels.csv \
    --output reports/exp-0009/results.json

Recall@100 is intentionally NOT claimed from a shallow judged pool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

MIN_RELEVANT_GRADE = 2  # 0 irrelevant, 1 tangential, 2 useful, 3 directly answers

CSV_FIELDS = (
    "run_id", "query_id", "query", "mode", "document_id", "title", "url",
    "relevance_grade", "notes",
)


class EvaluationError(ValueError):
    """Invalid or incomplete human-judgment evaluation."""


def read_diagnostics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvaluationError(f"Diagnostics file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("queries"), list):
        raise EvaluationError("Invalid diagnostic report: expected object with queries list")
    if not isinstance(payload.get("run_id"), str):
        raise EvaluationError("Diagnostic report is missing run_id")
    seen: set[str] = set()
    for q in payload["queries"]:
        if not isinstance(q, dict) or not isinstance(q.get("id"), str):
            raise EvaluationError("Invalid query entry")
        if q["id"] in seen:
            raise EvaluationError(f"Duplicate query ID: {q['id']}")
        seen.add(q["id"])
        for field in ("bm25_order", "postgresql_order", "documents"):
            if not isinstance(q.get(field), list):
                raise EvaluationError(f"Missing {field} for {q['id']}")
        if q.get("error") or "ERROR" in q.get("flags", []):
            raise EvaluationError(f"Cannot evaluate failed diagnostic query {q['id']}: {q.get('error')}")
        for name in ("bm25_order", "postgresql_order"):
            values = q[name]
            if any(type(doc_id) is not int or doc_id <= 0 for doc_id in values):
                raise EvaluationError(f"Bad document ID in {q['id']}.{name}")
            if len(set(values)) != len(values):
                raise EvaluationError(f"Duplicate documents in {q['id']}.{name}")
        if set(q["bm25_order"]) != set(q["postgresql_order"]):
            raise EvaluationError(f"Scorers have unequal candidate sets for {q['id']}")
    return payload


def prepare_qrels(report: dict[str, Any], *, depth: int,
                  includes: list[str]) -> list[dict[str, str]]:
    if depth < 10 or depth > 200:
        raise EvaluationError("--depth must be 10..200; at least 10 for top-10 metrics")
    forced: dict[str, set[int]] = {}
    qids = {q["id"] for q in report["queries"]}
    for entry in includes:
        try:
            query_id, raw_doc_id = entry.split(":", 1)
            document_id = int(raw_doc_id)
        except (ValueError, TypeError) as exc:
            raise EvaluationError(f"Bad --include {entry!r}; expected Q051:51") from exc
        if query_id not in qids or document_id <= 0:
            raise EvaluationError(f"Unknown query or invalid document ID in --include {entry!r}")
        forced.setdefault(query_id, set()).add(document_id)

    rows: list[dict[str, str]] = []
    for query in report["queries"]:
        if query.get("expect_zero"):
            continue
        query_id = query["id"]
        by_id = {int(d["document_id"]): d for d in query["documents"]}
        if len(by_id) != len(query["documents"]):
            raise EvaluationError(f"Duplicate document metadata in {query_id}")
        wanted = set(query["bm25_order"][:depth]) | set(query["postgresql_order"][:depth])
        wanted |= forced.get(query_id, set())
        unknown = wanted - by_id.keys()
        if unknown:
            raise EvaluationError(f"Document IDs not in report {query_id}: {sorted(unknown)}")
        if not wanted and not query.get("expect_zero"):
            # The query may have zero candidates due to a search failure;
            # don't invent negative judgments.
            continue
        # Blind the grading queue to both systems' ranks. Stable hashed order
        # avoids anchoring judgments to the incumbent scorer's top result.
        for document_id in sorted(wanted, key=lambda d: hashlib.sha256(
            f"{query_id}:{d}".encode("utf-8")
        ).digest()):
            d = by_id[document_id]
            rows.append({
                "run_id": report["run_id"],
                "query_id": query_id,
                "query": str(query["query"]),
                "mode": str(query["mode"]),
                "document_id": str(document_id),
                "title": str(d.get("title") or ""),
                "url": str(d.get("url") or ""),
                "relevance_grade": "",
                "notes": "",
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if path.exists():
        raise EvaluationError(f"Refusing to overwrite existing human judgments: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_qrels(path: Path, report: dict[str, Any]) -> dict[str, dict[int, int | None]]:
    if not path.is_file():
        raise EvaluationError(f"Qrels file not found: {path}")
    queries = {q["id"]: q for q in report["queries"]}
    judgments: dict[str, dict[int, int | None]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(CSV_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise EvaluationError(f"Qrels missing CSV columns: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, 2):
            query_id = row["query_id"]
            if query_id not in queries:
                raise EvaluationError(f"Row {row_number}: unknown query {query_id}")
            query = queries[query_id]
            if row["run_id"] != report["run_id"]:
                raise EvaluationError(f"Row {row_number}: run_id mismatch; don't mix corpus snapshots")
            if row["query"] != query["query"] or row["mode"] != query["mode"]:
                raise EvaluationError(f"Row {row_number}: query/mode mismatch")
            try:
                document_id = int(row["document_id"])
            except (ValueError, TypeError) as exc:
                raise EvaluationError(f"Row {row_number}: invalid document_id") from exc
            if document_id not in query["bm25_order"]:
                raise EvaluationError(f"Row {row_number}: document {document_id} missing from report candidate pool")
            if document_id in judgments.get(query_id, {}):
                raise EvaluationError(f"Row {row_number}: duplicate ({query_id}, {document_id})")
            value = (row.get("relevance_grade") or "").strip()
            if not value:
                grade = None
            elif value in ("0", "1", "2", "3"):
                grade = int(value)
            else:
                raise EvaluationError(f"Row {row_number}: relevance_grade must be blank or 0,1,2,3")
            judgments.setdefault(query_id, {})[document_id] = grade
    return judgments


def precision_at_k(order: list[int], qrels: dict[int, int], k: int = 10) -> float:
    if k <= 0:
        raise EvaluationError("k must be positive")
    return sum(qrels.get(doc_id, 0) >= MIN_RELEVANT_GRADE for doc_id in order[:k]) / k


def mrr_at_k(order: list[int], qrels: dict[int, int], k: int = 10) -> float:
    if k <= 0:
        raise EvaluationError("k must be positive")
    return next((1.0 / rank for rank, doc_id in enumerate(order[:k], 1)
                 if qrels.get(doc_id, 0) >= MIN_RELEVANT_GRADE), 0.0)


def dcg_at_k(grades: list[int], k: int = 10) -> float:
    if k <= 0:
        raise EvaluationError("k must be positive")
    return sum((2.0 ** grade - 1.0) / math.log2(rank + 1)
               for rank, grade in enumerate(grades[:k], 1))


def ndcg_at_k(order: list[int], qrels: dict[int, int], k: int = 10) -> float | None:
    ideal = sorted(qrels.values(), reverse=True)
    denominator = dcg_at_k(ideal, k)
    if denominator == 0:
        return None  # No judged relevant documents: undefined, not a zero-quality query.
    numerator = dcg_at_k([qrels.get(doc_id, 0) for doc_id in order[:k]], k)
    return numerator / denominator


def pooled_recall_at_k(order: list[int], qrels: dict[int, int], k: int = 100) -> float | None:
    """Recall against known relevant judgments ONLY, not exhaustive corpus recall."""
    relevant = {doc_id for doc_id, grade in qrels.items() if grade >= MIN_RELEVANT_GRADE}
    if not relevant:
        return None
    return len(relevant & set(order[:k])) / len(relevant)


def evaluate(report: dict[str, Any], judgments: dict[str, dict[int, int | None]],
             *, k: int = 10) -> dict[str, Any]:
    if k != 10:
        raise EvaluationError("This experiment currently supports top-10 ranking metrics")
    results: list[dict[str, Any]] = []
    incomplete: list[str] = []
    expected_zero: list[dict[str, Any]] = []

    for query in report["queries"]:
        query_id = query["id"]
        if query.get("expect_zero"):
            expected_zero.append({
                "query_id": query_id,
                "passed": len(query["bm25_order"]) == 0,
                "candidate_count": len(query["bm25_order"]),
            })
            continue
        bm_order = query["bm25_order"]
        pg_order = query["postgresql_order"]
        if not bm_order or not pg_order:
            incomplete.append(f"{query_id}: no candidates; investigate retrieval failure separately")
            continue
        judged = judgments.get(query_id, {})
        needed = set(bm_order[:k]) | set(pg_order[:k])
        unjudged = sorted(doc_id for doc_id in needed if judged.get(doc_id) is None)
        if unjudged:
            incomplete.append(f"{query_id}: {len(unjudged)} unjudged top-10 documents (IDs: {unjudged[:12]})")
            continue
        known: dict[int, int] = {doc_id: grade for doc_id, grade in judged.items()
                                 if grade is not None}
        # A complete label pool for the top-k is sufficient for fair P@k/MRR@k.
        # nDCG and pooled recall are relative to *known* judgments, not all
        # relevant documents in the indexed corpus.
        result: dict[str, Any] = {
            "query_id": query_id,
            "query": query["query"],
            "mode": query["mode"],
            "human_judgments": len(known),
            "relevant_judgments": sum(grade >= MIN_RELEVANT_GRADE for grade in known.values()),
        }
        for label, order in (("bm25", bm_order), ("postgresql", pg_order)):
            result[label] = {
                "precision_at_10": precision_at_k(order, known, k),
                "mrr_at_10": mrr_at_k(order, known, k),
                "pooled_ndcg_at_10": ndcg_at_k(order, known, k),
                "known_relevant_recall_at_100": pooled_recall_at_k(order, known, 100),
            }
        results.append(result)

    if incomplete:
        raise EvaluationError("Cannot score incomplete queries:\n  " + "\n  ".join(incomplete))
    if not results:
        raise EvaluationError("No evaluable human-labeled queries (expected no-result checks don't count)")

    averages: dict[str, dict[str, float | None]] = {}
    for label in ("bm25", "postgresql"):
        averages[label] = {}
        for metric in ("precision_at_10", "mrr_at_10", "pooled_ndcg_at_10",
                       "known_relevant_recall_at_100"):
            values = [q[label][metric] for q in results if q[label][metric] is not None]
            averages[label][metric] = sum(values) / len(values) if values else None

    return {
        "experiment": "EXP-0009",
        "run_id": report["run_id"],
        "query_count": len(results),
        "no_result_checks": expected_zero,
        "mean_metrics": averages,
        "queries": results,
        "methodology": (
            "Grades 0..3 are human supplied. P@10 uses relevant>=2 and denominator 10; "
            "MRR@10 uses first relevant rank; nDCG@10 uses graded 2^grade-1 gains "
            "and ideal ordering from judged qrels. Both scorers are rerankings "
            "of the SAME retrieved candidate set. known_relevant_recall_at_100 "
            "is NOT exhaustive Recall@100; nDCG also depends on judgment-pool completeness. "
            "All top-10 results in both rankings require labels."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Create CSV queue for human relevance judgments")
    prepare.add_argument("--diagnostics", type=Path, required=True)
    prepare.add_argument("--qrels", type=Path, required=True)
    prepare.add_argument("--depth", type=int, default=20,
                         help="Union depth from BOTH ranking systems (10..200, default 20)")
    prepare.add_argument("--include", action="append", default=[],
                         help="Anchor document from existing pool e.g. Q051:51; repeatable")
    score = sub.add_parser("score", help="Compute human-judged metrics")
    score.add_argument("--diagnostics", type=Path, required=True)
    score.add_argument("--qrels", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = read_diagnostics(args.diagnostics)
        if args.command == "prepare":
            rows = prepare_qrels(report, depth=args.depth, includes=args.include)
            write_csv(args.qrels, rows)
            print(f"Prepared {len(rows)} unlabeled document judgments for "
                  f"{len(report['queries'])} query cases: {args.qrels}")
            print("Open the CSV and supply independent relevance_grade values 0..3. "
                  "Leave unknown judgments blank.")
        else:
            judgments = read_qrels(args.qrels, report)
            results = evaluate(report, judgments)
            if args.output.exists():
                raise EvaluationError(f"Refusing to overwrite existing score report: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
            print(f"Scored {results['query_count']} fully judged queries; "
                  f"saved {args.output}")
            for name, metrics in results["mean_metrics"].items():
                print(f"{name.upper():10} " + "  ".join(
                    f"{key}={value:.4f}" if value is not None else f"{key}=N/A"
                    for key, value in metrics.items()
                ))
            print("Caution: recall is known-relevant pool coverage, NOT exhaustive Recall@100.")
        return 0
    except (EvaluationError, OSError, json.JSONDecodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
