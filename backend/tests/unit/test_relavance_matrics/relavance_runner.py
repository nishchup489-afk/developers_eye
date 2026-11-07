"""EXP-0009: Rich human-judged relevance evaluation for Developer's Eye.

Install this file and precision@10.py, mrr@10.py, ndcg@10.py, recall@100.py
in backend/tests/unit/test_relavance_matrics/.

From backend/:
  poetry run python "tests/unit/test_relavance_matrics/relevance_runner.py"
  poetry run python "tests/unit/test_relavance_matrics/relevance_runner.py" --score
  poetry run python "tests/unit/test_relavance_matrics/relevance_runner.py" --query-id Q024
  poetry run python "tests/unit/test_relavance_matrics/relevance_runner.py" --all --report PATH

Default: newest successful Q051 diagnostic, grade union of BM25/PG top 10,
compute metrics for BOTH methods, save Rich terminal HTML + JSON + Markdown.
No database access. Human grades are NEVER derived from ranking scores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
import webbrowser
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError as exc:
    raise SystemExit("Rich is required: poetry add --group dev rich") from exc

HERE = Path(__file__).resolve().parent
BACKEND_ROOT = HERE.parents[2]  # backend/tests/unit/test_relavance_matrics -> backend
REPORTS_ROOT = BACKEND_ROOT / "reports" / "exp-0004"
DEFAULT_QRELS = BACKEND_ROOT / "evaluation" / "exp-0009" / "exp0009_human_labels.csv"
DEFAULT_OUTPUT = BACKEND_ROOT / "reports" / "exp-0009"
CSV_FIELDS = (
    "run_id", "query_id", "query", "mode", "document_id", "title", "url",
    "relevance_grade", "graded_at_utc", "notes",
)
CONSOLE = Console(record=True)


class EvaluationError(ValueError):
    """The diagnostic data or human judgments are incomplete or invalid."""


def _load_metric(filename: str, name: str):
    location = HERE / filename
    if not location.is_file():
        raise EvaluationError(f"Missing metric file: {location}")
    module_name = f"exp0009_{filename.replace('@', '_').replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, location)
    if spec is None or spec.loader is None:
        raise EvaluationError(f"Cannot import {location}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


precision_at_10 = _load_metric("precision@10.py", "precision_at_10")
reciprocal_rank_at_10 = _load_metric("mrr@10.py", "reciprocal_rank_at_10")
ndcg_at_10 = _load_metric("ndcg@10.py", "ndcg_at_10")
known_relevant_recall_at_100 = _load_metric("recall@100.py", "known_relevant_recall_at_100")


def read_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(report, dict) or not isinstance(report.get("queries"), list):
        raise EvaluationError(f"Invalid diagnostic JSON: {path}")
    if not isinstance(report.get("run_id"), str) or not report["run_id"]:
        raise EvaluationError(f"Missing run_id in {path}")
    return report


def check_order(case: dict, key: str) -> list[int]:
    ids = case.get(key)
    if not isinstance(ids, list):
        raise EvaluationError(f"{case.get('id')}: {key} is missing")
    if any(type(doc_id) is not int or doc_id <= 0 for doc_id in ids):
        raise EvaluationError(f"{case.get('id')}: invalid document IDs in {key}")
    if len(set(ids)) != len(ids):
        raise EvaluationError(f"{case.get('id')}: duplicate document IDs in {key}")
    return ids


def case_by_id(report: dict, query_id: str) -> dict | None:
    return next((q for q in report["queries"] if isinstance(q, dict)
                 and q.get("id") == query_id), None)


def select_report(path: Path | None, query_id: str | None, all_queries: bool) -> tuple[Path, dict]:
    if path is not None:
        selected = path.resolve()
        report = read_report(selected)
        if not all_queries and case_by_id(report, query_id) is None:
            raise EvaluationError(f"Query {query_id} not in {selected}")
        return selected, report
    files = sorted(REPORTS_ROOT.glob("*/diagnostics.json"),
                   key=lambda x: x.parent.name, reverse=True)
    for candidate in files:
        try:
            report = read_report(candidate)
        except EvaluationError:
            continue
        if all_queries or (case_by_id(report, query_id) is not None and
                           not case_by_id(report, query_id).get("error")):
            return candidate, report
    raise EvaluationError("No suitable diagnostic report found. Run "
                          "scripts/search_relevance_diagnostics/diagnose_relevance.py first.")


def cases_to_evaluate(report: dict, query_id: str | None, all_queries: bool) -> list[dict]:
    selected = report["queries"] if all_queries else [case_by_id(report, query_id)]
    if not selected or any(not isinstance(q, dict) for q in selected):
        raise EvaluationError("No matching query in diagnostic report")
    seen = set()
    for q in selected:
        qid = q.get("id")
        if not isinstance(qid, str) or not qid or qid in seen:
            raise EvaluationError("Invalid or duplicated query IDs")
        seen.add(qid)
        if q.get("error") or "ERROR" in q.get("flags", []):
            raise EvaluationError(f"Diagnostic {qid} failed: {q.get('error')}")
        bm25 = check_order(q, "bm25_order")
        postgres = check_order(q, "postgresql_order")
        if set(bm25) != set(postgres):
            raise EvaluationError(f"{qid}: candidate IDs differ between BM25 and PG")
    return selected


def doc_details(case: dict) -> dict[int, dict]:
    documents = case.get("documents")
    if not isinstance(documents, list):
        raise EvaluationError(f"{case['id']}: missing documents in diagnostics")
    result = {}
    for row in documents:
        if not isinstance(row, dict) or type(row.get("document_id")) is not int:
            raise EvaluationError("Malformed document metadata")
        did = row["document_id"]
        if did in result:
            raise EvaluationError(f"Duplicate metadata for document {did}")
        result[did] = row
    return result


def load_labels(path: Path) -> dict[tuple[str, str, int], dict[str, str]]:
    if not path.exists():
        return {}
    result = {}
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not set(CSV_FIELDS).issubset(reader.fieldnames):
                raise EvaluationError(f"Unexpected labels CSV format in {path}")
            for lineno, row in enumerate(reader, 2):
                run_id, qid = row["run_id"], row["query_id"]
                try:
                    did = int(row["document_id"])
                except (TypeError, ValueError) as exc:
                    raise EvaluationError(f"CSV line {lineno}: bad document_id") from exc
                if not run_id or not qid or did <= 0:
                    raise EvaluationError(f"CSV line {lineno}: missing/invalid identity")
                grade = (row.get("relevance_grade") or "").strip()
                if grade not in {"", "0", "1", "2", "3"}:
                    raise EvaluationError(f"CSV line {lineno}: grade must be blank or 0..3")
                key = (run_id, qid, did)
                if key in result:
                    raise EvaluationError(f"CSV line {lineno}: duplicate judgment {key}")
                result[key] = {column: row.get(column) or "" for column in CSV_FIELDS}
    except OSError as exc:
        raise EvaluationError(f"Unable to read judgments: {exc}") from exc
    return result


def save_labels(path: Path, labels: Mapping[tuple[str, str, int], dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for key in sorted(labels):
                writer.writerow({column: labels[key].get(column, "") for column in CSV_FIELDS})
        tmp.replace(path)
    except OSError as exc:
        raise EvaluationError(f"Cannot save judgments to {path}: {exc}") from exc


def wanted_documents(case: dict, depth: int, includes: set[int]) -> list[int]:
    bm25 = check_order(case, "bm25_order")
    postgres = check_order(case, "postgresql_order")
    available = doc_details(case)
    wanted = set(bm25[:depth]) | set(postgres[:depth]) | includes
    if wanted - available.keys():
        raise EvaluationError(
            f"{case['id']}: IDs absent from diagnostic metadata: {sorted(wanted - available.keys())}"
        )
    # Blind judging order to BM25/PG rank; deterministic across reruns.
    return sorted(wanted, key=lambda doc_id: hashlib.sha256(
        f"{case['id']}:{doc_id}".encode("utf-8")).digest())


def prepare_labels(report: dict, cases: list[dict], labels: dict, *, depth: int,
                   includes: Mapping[str, set[int]]) -> int:
    created = 0
    for case in cases:
        if case.get("expect_zero"):
            continue
        details = doc_details(case)
        for did in wanted_documents(case, depth, includes.get(case["id"], set())):
            key = (report["run_id"], case["id"], did)
            if key in labels:
                old = labels[key]
                if old.get("url") != str(details[did].get("url") or ""):
                    raise EvaluationError(
                        f"Document {did} changed URL within run_id {report['run_id']}; "
                        "use a fresh diagnostic snapshot and labels file"
                    )
                continue
            doc = details[did]
            labels[key] = {
                "run_id": report["run_id"],
                "query_id": case["id"],
                "query": str(case["query"]),
                "mode": str(case["mode"]),
                "document_id": str(did),
                "title": str(doc.get("title") or ""),
                "url": str(doc.get("url") or ""),
                "relevance_grade": "",
                "graded_at_utc": "",
                "notes": "",
            }
            created += 1
    return created


def _format_grade(grade: str) -> str:
    return {"0": "irrelevant", "1": "tangential", "2": "useful", "3": "excellent"}.get(grade, "unjudged")


def collect_labels(report: dict, cases: list[dict], labels: dict, path: Path,
                   *, depth: int, includes: Mapping[str, set[int]], regrade: bool) -> bool:
    for case in cases:
        if case.get("expect_zero"):
            continue
        doc_ids = wanted_documents(case, depth, includes.get(case["id"], set()))
        for i, did in enumerate(doc_ids, 1):
            key = (report["run_id"], case["id"], did)
            row = labels[key]
            if row["relevance_grade"] and not regrade:
                continue
            CONSOLE.print(Panel(
                f"[bold]Document {i}/{len(doc_ids)}[/]  [cyan]#{did}[/]\n"
                f"{row['title']}\n[blue underline]{row['url']}[/]\n"
                "[dim]0 irrelevant · 1 tangential · 2 useful · 3 excellent[/]",
                title=f"{case['id']} | {case['query']}", border_style="cyan"
            ))
            while True:
                try:
                    response = CONSOLE.input("[bold]Grade [0/1/2/3, o=open, s=skip, q=quit]: [/]").strip().lower()
                except EOFError:
                    CONSOLE.print("[yellow]Input ended; judgments already saved.[/]")
                    return False
                if response == "q":
                    CONSOLE.print("[yellow]Stopped. Graded documents remain saved.[/]")
                    return False
                if response == "s":
                    break
                if response == "o":
                    url = row["url"]
                    parsed = urlsplit(url)
                    if parsed.scheme in {"http", "https"} and parsed.netloc:
                        webbrowser.open(url)
                    else:
                        CONSOLE.print("[red]No valid HTTP(S) URL for this document.[/]")
                    continue
                if response in {"0", "1", "2", "3"}:
                    row["relevance_grade"] = response
                    row["graded_at_utc"] = datetime.now(timezone.utc).isoformat()
                    save_labels(path, labels)  # Incremental persistence.
                    CONSOLE.print(f"[green]Saved:[/] {_format_grade(response)}")
                    break
                CONSOLE.print("[red]Enter 0, 1, 2, 3, o, s or q.[/]")
    return True


def graded_map(report: dict, case: dict, labels: dict) -> dict[int, int]:
    out = {}
    for (rid, qid, doc_id), row in labels.items():
        if rid == report["run_id"] and qid == case["id"] and row["relevance_grade"]:
            out[doc_id] = int(row["relevance_grade"])
    return out


def evaluate_case(report: dict, case: dict, labels: dict) -> dict:
    bm25, pg = check_order(case, "bm25_order"), check_order(case, "postgresql_order")
    if case.get("expect_zero"):
        return {"query_id": case["id"], "query": case["query"], "status": "expected_zero",
                "passed": not bm25 and not pg}
    if not bm25 and not pg:
        return {"query_id": case["id"], "query": case["query"], "status": "unexpected_zero"}
    known = graded_map(report, case, labels)
    needed = set(bm25[:10]) | set(pg[:10])
    missing = sorted(needed - known.keys())
    if missing:
        return {"query_id": case["id"], "query": case["query"], "status": "needs_judgments",
                "missing_count": len(missing), "missing_document_ids": missing}
    entry = {
        "query_id": case["id"], "query": case["query"], "mode": case["mode"],
        "status": "scored", "judged_documents": len(known),
        "known_relevant_documents": sum(grade >= 2 for grade in known.values()),
        "candidate_count": len(bm25),
    }
    for name, ranking in (("bm25", bm25), ("postgresql", pg)):
        entry[name] = {
            "precision_at_10": precision_at_10(ranking, known),
            "reciprocal_rank_at_10": reciprocal_rank_at_10(ranking, known),
            "ndcg_at_10_judged_pool": ndcg_at_10(ranking, known),
            "known_relevant_recall_at_100": known_relevant_recall_at_100(ranking, known),
        }
    return entry


def _mean_defined(values: list[float | None]) -> float | None:
    keep = [v for v in values if v is not None]
    return sum(keep) / len(keep) if keep else None


def aggregate(results: list[dict]) -> dict:
    completed = [r for r in results if r["status"] == "scored"]
    summary = {"queries_scored": len(completed), "queries_total": len(results)}
    for algo in ("bm25", "postgresql"):
        summary[algo] = {
            name: _mean_defined([r[algo][name] for r in completed])
            for name in ("precision_at_10", "reciprocal_rank_at_10",
                         "ndcg_at_10_judged_pool", "known_relevant_recall_at_100")
        }
    summary["expected_zero_passed"] = sum(r.get("status") == "expected_zero" and
                                          r.get("passed") is True for r in results)
    summary["expected_zero_failed"] = sum(r.get("status") == "expected_zero" and
                                          r.get("passed") is False for r in results)
    return summary


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def render_report(report: dict, results: list[dict], summary: dict, cases: list[dict],
                  labels: dict, *, depth: int, details: bool) -> None:
    CONSOLE.print(Panel.fit(
        f"[bold cyan]DEVELOPER'S EYE[/]  EXP-0009 | Human relevance evaluation\n"
        f"Diagnostic: [bold]{report['run_id']}[/]  "
        f"Evaluated: [bold]{summary['queries_scored']}/{summary['queries_total']}[/]",
        border_style="cyan"
    ))
    table = Table(title="BM25 vs PostgreSQL | Human-judged relevance", box=box.ROUNDED)
    for label in ("Query", "Ranker", "P@10", "RR@10", "nDCG@10*", "Known R@100*", "Judged"):
        table.add_column(label, justify="right" if "@" in label or label == "Judged" else "left")
    for result in results:
        qid = result["query_id"]
        if result["status"] != "scored":
            message = result["status"]
            if result["status"] == "needs_judgments":
                message = f"needs {result['missing_count']} human grades"
            elif result["status"] == "expected_zero":
                message = "PASS: zero results" if result["passed"] else "FAIL: nonzero results"
            table.add_row(qid, message, "", "", "", "", "")
            continue
        for ranker in ("bm25", "postgresql"):
            values = result[ranker]
            table.add_row(
                qid, ranker.upper(), _fmt(values["precision_at_10"]),
                _fmt(values["reciprocal_rank_at_10"]),
                _fmt(values["ndcg_at_10_judged_pool"]),
                _fmt(values["known_relevant_recall_at_100"]),
                str(result["judged_documents"]),
            )
    CONSOLE.print(table)
    total = Table(title="Macro-average (scored queries only)", box=box.SIMPLE_HEAVY)
    for header in ("Ranker", "P@10", "MRR@10", "nDCG@10*", "Known R@100*"):
        total.add_column(header)
    for ranker in ("bm25", "postgresql"):
        row = summary[ranker]
        total.add_row(ranker.upper(), _fmt(row["precision_at_10"]),
                      _fmt(row["reciprocal_rank_at_10"]),
                      _fmt(row["ndcg_at_10_judged_pool"]),
                      _fmt(row["known_relevant_recall_at_100"]))
    CONSOLE.print(total)
    if details:
        by_query = {c["id"]: c for c in cases}
        for result in results:
            if result["status"] != "scored":
                continue
            case = by_query[result["query_id"]]
            docs = doc_details(case)
            judged = graded_map(report, case, labels)
            for ranker, key in (("BM25", "bm25_order"), ("PostgreSQL", "postgresql_order")):
                t = Table(title=f"{case['id']} | {case['query']} | {ranker} top 10")
                for col in ("#", "ID", "Grade", "Title"):
                    t.add_column(col)
                for position, doc_id in enumerate(case[key][:10], 1):
                    t.add_row(str(position), str(doc_id), str(judged[doc_id]),
                              str(docs[doc_id].get("title") or "")[:90])
                CONSOLE.print(t)
    CONSOLE.print(Panel(
        "[bold]* Limitations:[/] nDCG@10 is normalized against the judged pool, not all "
        "corpus-relevant documents. Known R@100 uses only labeled relevant documents; "
        "if labels are drawn from these rankers' top results, recall is biased. "
        "Independent relevance discovery is required for true Recall@100.\n"
        f"[dim]Label preparation depth: {depth}; no scores derived from BM25 or PG ranks.[/]",
        title="Interpretation", border_style="yellow"))


def save_report(root: Path, report: dict, source: Path, results: list[dict],
                summary: dict, depth: int, qrels: Path) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    ids = "all" if len(results) > 1 else results[0]["query_id"] if results else "none"
    safe_run_id = "".join(ch for ch in report["run_id"] if ch.isascii() and (ch.isalnum() or ch in "-_"))
    prefix = root / f"{safe_run_id}-{ids}"
    payload = {
        "experiment": "EXP-0009", "run_id": report["run_id"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_diagnostics": str(source.resolve()), "qrels_file": str(qrels.resolve()),
        "judgment_depth": depth, "grade_threshold": 2,
        "recall_warning": "Known-relevant judged-pool recall only; not exhaustive Recall@100",
        "summary": summary, "queries": results,
    }
    json_path = prefix.with_suffix(".json")
    md_path = prefix.with_suffix(".md")
    html_path = prefix.with_suffix(".html")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# EXP-0009 | Human-judged search relevance", "",
          f"Diagnostics run: `{report['run_id']}`", "",
          f"Human labels: `{qrels}`", "",
          "**Recall warning:** Known-relevant Recall@100 is judged-pool recall, NOT exhaustive corpus recall.",
          "nDCG@10 depends on the completeness of the judged pool.", "",
          "| Query | Ranker | P@10 | RR@10 | nDCG@10* | Known R@100* |", "|---|---|---:|---:|---:|---:|"]
    for result in results:
        if result["status"] != "scored":
            md.append(f"| {result['query_id']} | {result['status']} | | | | |")
        else:
            for algo in ("bm25", "postgresql"):
                row = result[algo]
                md.append(f"| {result['query_id']} | {algo} | {_fmt(row['precision_at_10'])} | "
                          f"{_fmt(row['reciprocal_rank_at_10'])} | "
                          f"{_fmt(row['ndcg_at_10_judged_pool'])} | "
                          f"{_fmt(row['known_relevant_recall_at_100'])} |")
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    CONSOLE.save_html(str(html_path), clear=False)
    return json_path, md_path, html_path


def parse_includes(values: list[str], cases: list[dict]) -> dict[str, set[int]]:
    valid = {q["id"] for q in cases}
    out: dict[str, set[int]] = {}
    for text_value in values:
        if ":" in text_value:
            qid, raw_id = text_value.split(":", 1)
        elif len(cases) == 1:
            qid, raw_id = cases[0]["id"], text_value
        else:
            raise EvaluationError("When evaluating multiple queries, use --include Q051:51")
        try:
            did = int(raw_id)
        except ValueError as exc:
            raise EvaluationError(f"Bad --include {text_value!r}") from exc
        if qid not in valid or did <= 0:
            raise EvaluationError(f"Unknown query or invalid document: {text_value!r}")
        out.setdefault(qid, set()).add(did)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-id", default="Q051", help="Diagnostic query ID (default: Q051)")
    parser.add_argument("--all", action="store_true", help="Evaluate every query in one diagnostics report")
    parser.add_argument("--report", type=Path, help="Existing EXP-0004 diagnostics.json")
    parser.add_argument("--labels", type=Path, default=DEFAULT_QRELS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--depth", type=int, default=10, help="Union of each ranker's top N for labeling; 10..100")
    parser.add_argument("--include", action="append", default=[], help="Also judge an ID from report: 51 or Q051:51")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prepare", action="store_true", help="Prepare CSV only, without interactive grading")
    group.add_argument("--judge", action="store_true", help="Prepare and grade; no final scoring")
    group.add_argument("--score", action="store_true", help="Score current human judgments, no prompting")
    parser.add_argument("--regrade", action="store_true", help="Ask again for previously graded documents")
    parser.add_argument("--details", action="store_true", help="Show both ranked top-10 tables")
    parser.add_argument("--self-test", action="store_true", help="Run all four independent metric test suites")
    args = parser.parse_args(argv)
    if not 10 <= args.depth <= 100:
        parser.error("--depth must be between 10 and 100")

    if args.self_test:
        CONSOLE.print(Panel.fit("[bold]EXP-0009 metric self-tests[/]", border_style="cyan"))
        for filename in ("precision@10.py", "mrr@10.py", "ndcg@10.py", "recall@100.py"):
            try:
                _load_metric(filename, "run_tests")()
            except Exception as exc:
                CONSOLE.print(f"[bold red]FAIL[/]  {filename}: {exc}")
                return 1
            CONSOLE.print(f"[bold green]PASS[/]  {filename}")
        return 0

    try:
        source, report = select_report(args.report, args.query_id, args.all)
        cases = cases_to_evaluate(report, args.query_id, args.all)
        includes = parse_includes(args.include, cases)
        labels = load_labels(args.labels)
        CONSOLE.print(f"[cyan]Diagnostics:[/] {source}")
        CONSOLE.print(f"[cyan]Qrels:[/] {args.labels}")
        if not args.score:
            created = prepare_labels(report, cases, labels, depth=args.depth, includes=includes)
            save_labels(args.labels, labels)
            CONSOLE.print(f"[green]Prepared {created} new judgment rows[/]. "
                          "Existing judgments preserved.")
            if args.prepare:
                CONSOLE.print("Open CSV and assign relevance_grade=0..3, or run without --prepare to grade interactively.")
                return 0
            completed_input = collect_labels(report, cases, labels, args.labels,
                                             depth=args.depth, includes=includes,
                                             regrade=args.regrade)
            if args.judge:
                return 0
            if not completed_input:
                return 2
        results = [evaluate_case(report, case, labels) for case in cases]
        summary = aggregate(results)
        render_report(report, results, summary, cases, labels,
                      depth=args.depth, details=args.details)
        paths = save_report(args.output_dir, report, source, results,
                            summary, args.depth, args.labels)
        CONSOLE.print(Panel("\n".join(f"[green]Saved:[/] {p}" for p in paths),
                            title="EXP-0009 report"))
        missing = [r for r in results if r["status"] not in {"scored", "expected_zero"}]
        if missing:
            CONSOLE.print("[yellow]Some queries are incomplete; add human judgments or investigate zero candidates.[/]")
            return 2
        return 0 if summary["expected_zero_failed"] == 0 else 2
    except (EvaluationError, OSError, ValueError) as exc:
        CONSOLE.print(f"[bold red]Evaluation error:[/] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
