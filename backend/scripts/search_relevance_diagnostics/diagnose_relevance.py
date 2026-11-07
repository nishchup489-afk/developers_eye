"""Run a 100-query read-only search diagnostic with Rich output.

From backend/:
    poetry add --group dev rich
    poetry run python scripts/diagnose_relevance.py
    poetry run python scripts/diagnose_relevance.py --limit 10 --k 10

Reuses Developer's Eye retrieval and BM25, with one corpus-statistics scan per
active channel for the entire suite. Reports ranking agreement and heuristics;
it does NOT calculate judged Precision, Recall, MRR or nDCG.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
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

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_SUITE = SCRIPT_DIR / "diagnostic_queries.json"
DEFAULT_REPORTS = BACKEND_ROOT / "reports" / "exp-0004"
KNOWN_NON_ENGLISH = frozenset({
    "ar", "bn", "cs", "da", "de", "el", "es", "fa", "fi", "fr", "he", "hi", "hu",
    "id", "it", "ja", "ko", "nl", "no", "pl", "pt", "ro", "ru", "sv", "th", "tr",
    "uk", "vi", "zh",
})


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    category: str
    query: str
    mode: SearchMode
    expected_title_contains: str | None = None
    expect_zero: bool = False


def load_cases(path: Path) -> list[Case]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("The suite must be an object with version=1")
    rows = payload.get("queries")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Suite 'queries' must be a nonempty list")
    seen_ids: set[str] = set()
    seen_queries: set[tuple[str, SearchMode]] = set()
    cases: list[Case] = []
    for i, raw in enumerate(rows, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"Query {i} is not an object")
        key = raw.get("id")
        query = raw.get("query")
        group = raw.get("category")
        mode = SearchMode(raw.get("mode", "all"))
        hint = raw.get("expected_title_contains")
        zero = raw.get("expect_zero", False)
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", key):
            raise ValueError(f"Invalid query ID at row {i}")
        if not isinstance(query, str) or not query.strip() or len(query) > 256:
            raise ValueError(f"Invalid query text at row {i}")
        if not isinstance(group, str) or not group.strip() or len(group) > 70:
            raise ValueError(f"Invalid category at row {i}")
        if hint is not None and (not isinstance(hint, str) or not hint.strip()):
            raise ValueError(f"Invalid expected_title_contains at row {i}")
        if type(zero) is not bool:
            raise ValueError(f"expect_zero must be boolean at row {i}")
        if key in seen_ids or (query, mode) in seen_queries:
            raise ValueError(f"Duplicate ID or (query, mode) at row {i}")
        seen_ids.add(key)
        seen_queries.add((query, mode))
        cases.append(Case(key, group, query, mode, hint, zero))
    return cases


def document_language(url: str) -> str:
    """Best-effort URL locale detection, not content-language classification."""
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return "unknown"
    host = (parsed.hostname or "").lower()
    segments = parsed.path.strip("/").split("/")
    first = segments[0].lower() if segments else ""
    if host in {"docs.djangoproject.com", "developer.mozilla.org", "fastapi.tiangolo.com"}:
        language = first.split("-")[0]
        if language == "en":
            return "en"
        if language in KNOWN_NON_ENGLISH:
            return language
        if host == "fastapi.tiangolo.com":
            return "en"  # English FastAPI docs omit locale in the URL.
        return "unknown"
    if host == "docs.python.org":
        return first if first in KNOWN_NON_ENGLISH else "en"
    if host == "doc.rust-lang.org":
        return "en"
    return "unknown"


def native_score(query: str, mode: SearchMode):
    """Score the SAME candidate IDs, not an independent unrestricted search.

    Uses normalization=32 for CODE to match search_code's production retrieval.
    ALL is explicitly an unweighted sum of text/code scores (comparison only).
    """
    text_query = func.websearch_to_tsquery("english", query)
    code_query = func.websearch_to_tsquery("simple", query)
    text_score = func.ts_rank_cd(SearchIndex.search_vector, text_query, 0)
    code_score = func.ts_rank_cd(SearchIndex.code_vector, code_query, 32)
    if mode is SearchMode.TEXT:
        return text_score
    if mode is SearchMode.CODE:
        return code_score
    return text_score + code_score


async def compare_case(
    session: AsyncSession,
    case: Case,
    *,
    k: int,
    settings: SearchConfig,
    text_corpus: CorpusStatistics | None,
    code_corpus: CorpusStatistics | None,
) -> dict:
    started = perf_counter()
    normalized = analyze_query(case.query, config=settings)
    hits = await _retrieve_candidates(session, normalized, case.mode)
    candidate_ids = [hit.document_id for hit in hits]
    report = {
        "id": case.id,
        "category": case.category,
        "query": case.query,
        "normalized_query": normalized,
        "mode": case.mode.value,
        "expected_title_contains": case.expected_title_contains,
        "expect_zero": case.expect_zero,
        "candidate_count": len(candidate_ids),
        "top_k": k,
        "top_k_overlap": None,
        "mean_absolute_rank_shift": None,
        "bm25_top1": None,
        "postgres_top1": None,
        "bm25_order": [],
        "postgresql_order": [],
        "target_bm25_rank": None,
        "target_postgres_rank": None,
        "non_english_top_k": 0,
        "documents": [],
        "flags": [],
    }
    if candidate_ids:
        bm_hits = await rank_candidates(
            session,
            normalized,
            hits,
            mode=case.mode,
            text_corpus=text_corpus,
            code_corpus=code_corpus,
            tokenizer_config=settings,
        )
        native = native_score(normalized, case.mode)
        stmt = (
            select(
                SearchIndex.document_id,
                native.label("postgres_score"),
                Document.title,
                Document.canonical_url,
            )
            .join(Document, Document.id == SearchIndex.document_id)
            .where(SearchIndex.document_id.in_(candidate_ids))
            .order_by(native.desc(), SearchIndex.document_id.asc())
        )
        pg_rows = (await session.execute(stmt)).all()
        bm_ids = [hit.document_id for hit in bm_hits]
        pg_ids = [int(row.document_id) for row in pg_rows]
        if len(pg_ids) != len(candidate_ids) or set(pg_ids) != set(bm_ids):
            raise RuntimeError("BM25/PG candidate mismatch; check index/metadata consistency")
        bm_positions = {doc_id: i for i, doc_id in enumerate(bm_ids, 1)}
        pg_positions = {doc_id: i for i, doc_id in enumerate(pg_ids, 1)}
        bm_scores = {hit.document_id: hit.score for hit in bm_hits}
        documents = [
            {
                "document_id": int(row.document_id),
                "title": row.title or "(untitled)",
                "url": row.canonical_url or "",
                "language": document_language(row.canonical_url or ""),
                "postgres_rank": pg_positions[int(row.document_id)],
                "bm25_rank": bm_positions[int(row.document_id)],
                "postgres_score": float(row.postgres_score or 0),
                "bm25_score": float(bm_scores[int(row.document_id)]),
            }
            for row in pg_rows
        ]
        by_id = {row["document_id"]: row for row in documents}
        top_n = min(k, len(pg_ids))
        report.update({
            "top_k_overlap": len(set(bm_ids[:top_n]) & set(pg_ids[:top_n])) / top_n,
            "mean_absolute_rank_shift": sum(
                abs(doc["bm25_rank"] - doc["postgres_rank"]) for doc in documents
            ) / len(documents),
            "bm25_top1": by_id[bm_ids[0]]["title"],
            "postgres_top1": by_id[pg_ids[0]]["title"],
            "bm25_order": bm_ids,
            "postgresql_order": pg_ids,
            "documents": documents,
            "non_english_top_k": sum(
                by_id[doc_id]["language"] not in {"en", "unknown"}
                for doc_id in bm_ids[:top_n]
            ),
        })
        if case.expected_title_contains:
            matching = [
                doc for doc in documents
                if case.expected_title_contains.casefold() in doc["title"].casefold()
            ]
            if matching:
                report["target_bm25_rank"] = min(doc["bm25_rank"] for doc in matching)
                report["target_postgres_rank"] = min(doc["postgres_rank"] for doc in matching)
    report["elapsed_ms"] = round((perf_counter() - started) * 1000, 1)
    return report


def classify(report: dict, *, k: int, slow_ms: float) -> list[str]:
    if "error" in report:
        return ["ERROR"]
    count = report["candidate_count"]
    flags: list[str] = []
    if report["expect_zero"]:
        if count:
            flags.append("UNEXPECTED_RESULTS")
        return flags
    if count == 0:
        flags.append("ZERO_RESULTS")
    elif count < 5:
        flags.append("THIN_POOL")
    if count >= k and report["top_k_overlap"] is not None and report["top_k_overlap"] < 0.30:
        flags.append("LOW_AGREEMENT")
    if report["non_english_top_k"] >= 3:
        flags.append("MULTILINGUAL_TOP")
    if report["expected_title_contains"]:
        target_rank = report["target_bm25_rank"]
        if target_rank is None:
            flags.append("TARGET_NOT_IN_CANDIDATES")
        elif target_rank > k:
            flags.append("TARGET_BELOW_K")
    if report["elapsed_ms"] >= slow_ms:
        flags.append("SLOW")
    return flags


def as_top_rows(report: dict, *, rank_key: str, k: int) -> list[dict]:
    return sorted(report.get("documents", []), key=lambda row: row[rank_key])[:k]


def markdown_report(data: dict, *, k: int) -> str:
    queries = data["queries"]
    total = len(queries)
    counts = Counter(flag for row in queries for flag in row["flags"])
    flag_lines = ", ".join(f"{flag}: {n}" for flag, n in counts.most_common()) or "None"
    parts = [
        "# Developer's Eye | EXP-0004 Batch Search Diagnostics",
        "",
        f"Run: `{data['run_id']}` | Queries: **{total}** | Corpus snapshot: {data['corpus']}",
        "",
        "**Scope:** same retrieved candidate IDs, ranked by BM25 versus PostgreSQL ",
        "`ts_rank_cd`. TITLE_HINT and language are heuristics, not human relevance ",
        "grades. Rank agreement is not ranking quality. The corpus can change ",
        "between queries while the crawler runs. This is not Recall@100, ",
        "Precision@10, MRR@10 or nDCG@10.",
        "",
        f"Flags: {flag_lines}",
        "",
        "## All queries",
        "",
        "| ID | Category | Query | Mode | Candidates | Overlap | Time (ms) | Flags |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    def clean(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    for row in queries:
        overlap = "N/A" if row["top_k_overlap"] is None else f"{row['top_k_overlap']:.0%}"
        parts.append(
            f"| {clean(row['id'])} | {clean(row['category'])} | {clean(row['query'])} | "
            f"{row['mode']} | {row.get('candidate_count', 0)} | {overlap} | "
            f"{row.get('elapsed_ms', 0):.0f} | {', '.join(row['flags']) or 'OK'} |"
        )
    parts.extend(["", "## Flagged queries", ""])
    flagged = [row for row in queries if row["flags"]]
    if not flagged:
        parts.append("No diagnostic flags triggered.")
    for row in flagged:
        parts.extend([
            f"### {row['id']}: {row['query']}",
            "",
            f"Mode: `{row['mode']}` | Flags: `{', '.join(row['flags'])}` | "
            f"Candidates: {row.get('candidate_count', 0)} | "
            f"Time: {row.get('elapsed_ms', 0):.0f} ms",
            "",
        ])
        if row.get("error"):
            parts.extend([f"Error: `{row['error']}`", ""])
        elif row.get("documents"):
            for label, key in (("BM25", "bm25_rank"), ("PostgreSQL", "postgres_rank")):
                parts.extend([f"**{label} top {k}**", ""])
                for doc in as_top_rows(row, rank_key=key, k=k):
                    title = doc["title"].replace("[", "\\[").replace("]", "\\]")
                    parts.append(
                        f"{doc[key]}. [{title}]({doc['url']}) "
                        f"(id={doc['document_id']}, locale={doc['language']})"
                    )
                parts.append("")
    parts.extend([
        "## Next steps",
        "",
        "1. Review flagged queries manually; flags are **leads**, not relevance verdicts.",
        "2. Add independently judged document relevance labels (qrels).",
        "3. Evaluate ranking quality with P@10, MRR@10 and nDCG@10; separately test candidate recall.",
        "",
    ])
    return "\n".join(parts)


def print_summary(console: Console, data: dict, *, k: int) -> None:
    rows = data["queries"]
    flags = Counter(flag for row in rows for flag in row["flags"])
    overlaps = [row["top_k_overlap"] for row in rows if row["top_k_overlap"] is not None]
    latencies = [row["elapsed_ms"] for row in rows if "elapsed_ms" in row and "error" not in row]
    console.print(Panel.fit(
        f"[bold cyan]DEVELOPER'S EYE[/]  [bold]Batch search diagnostics[/]\n"
        f"Executed: [bold]{len(rows)}[/]   "
        f"No-candidate: [yellow]{sum(r.get('candidate_count', 0) == 0 and not r.get('expect_zero', False) for r in rows)}[/]   "
        f"Errors: [red]{flags['ERROR']}[/]\n"
        f"Mean top-{k} overlap: [bold]{statistics.mean(overlaps):.0%}[/]  "
        f"Median elapsed: [bold]{statistics.median(latencies):.0f} ms[/] "
        if overlaps and latencies else
        f"[bold cyan]DEVELOPER'S EYE[/]  Executed {len(rows)} queries",
        title="EXP-0004", border_style="cyan",
    ))
    if flags:
        console.print("[bold]Flag counts[/]  " + "   ".join(f"{key}: [yellow]{value}[/]" for key, value in flags.most_common()))
    table = Table(title="Per-query diagnostics", box=box.SIMPLE_HEAVY, expand=True, show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Group", max_width=16)
    table.add_column("Query", max_width=31)
    table.add_column("Mode", max_width=5)
    table.add_column("N", justify="right")
    table.add_column(f"Top-{k} overlap", justify="right")
    table.add_column("BM25 #1", max_width=30)
    table.add_column("ms", justify="right")
    table.add_column("Flags", max_width=30)
    for row in rows:
        n = row.get("candidate_count", 0)
        agree = row.get("top_k_overlap")
        color = "red" if "ERROR" in row["flags"] else "yellow" if row["flags"] else "green"
        table.add_row(
            row["id"], row["category"], row["query"], row["mode"], str(n),
            "-" if agree is None else f"{agree:.0%}",
            str(row.get("bm25_top1") or "-"),
            "-" if "elapsed_ms" not in row else f"{row['elapsed_ms']:.0f}",
            f"[{color}]{', '.join(row['flags']) or 'OK'}[/]",
        )
    console.print(table)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_group[row["category"]].append(row)
    group_table = Table(title="Category summary", box=box.ROUNDED)
    group_table.add_column("Category")
    group_table.add_column("Queries", justify="right")
    group_table.add_column("Flagged", justify="right")
    group_table.add_column("Zero candidates", justify="right")
    group_table.add_column("Mean overlap", justify="right")
    for name, subset in by_group.items():
        ov = [x["top_k_overlap"] for x in subset if x["top_k_overlap"] is not None]
        group_table.add_row(
            name, str(len(subset)), str(sum(bool(x["flags"]) for x in subset)),
            str(sum(x.get("candidate_count", 0) == 0 for x in subset)),
            "-" if not ov else f"{statistics.mean(ov):.0%}",
        )
    console.print(group_table)
    console.print("[dim]Flags are heuristics. Do not interpret overlap as relevance quality.[/]")


def print_details(console: Console, report: dict, *, k: int) -> None:
    """Render a compact side-by-side ranking audit for one query."""
    console.print(Panel.fit(
        f"[bold]{report['id']}[/]  {report['query']}  "
        f"[dim]({report['mode']}; {report.get('candidate_count', 0)} candidates)[/]",
        border_style="blue",
    ))
    if report.get("error"):
        console.print(f"[red]{report['error']}[/]")
        return
    if not report.get("documents"):
        console.print("[yellow]No retrieved candidates.[/]")
        return
    bm = as_top_rows(report, rank_key="bm25_rank", k=k)
    pg = as_top_rows(report, rank_key="postgres_rank", k=k)
    table = Table(title=f"Top {k}: BM25 vs PostgreSQL", box=box.ROUNDED, expand=True)
    table.add_column("#", justify="right")
    table.add_column("BM25 title", max_width=45)
    table.add_column("BM25 score", justify="right")
    table.add_column("PG title", max_width=45)
    table.add_column("PG score", justify="right")
    for i in range(max(len(bm), len(pg))):
        a = bm[i] if i < len(bm) else None
        b = pg[i] if i < len(pg) else None
        table.add_row(
            str(i + 1),
            a["title"] if a else "-",
            f"{a['bm25_score']:.4f}" if a else "-",
            b["title"] if b else "-",
            f"{b['postgres_score']:.5f}" if b else "-",
        )
    console.print(table)
    console.print("[dim]BM25 and PostgreSQL scores are on different scales; compare order, not magnitudes.[/]")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


async def run(args: argparse.Namespace) -> int:
    cases = load_cases(args.suite)
    if args.ids:
        wanted = set(args.ids)
        found = {case.id for case in cases}
        missing = wanted - found
        if missing:
            raise ValueError(f"Unknown query IDs: {', '.join(sorted(missing))}")
        cases = [case for case in cases if case.id in wanted]
    if args.limit:
        cases = cases[:args.limit]
    console = Console(no_color=args.no_color, record=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{len(cases)}q"
    destination = args.output_dir / run_id
    active_text = any(c.mode in (SearchMode.TEXT, SearchMode.ALL) for c in cases)
    active_code = any(c.mode in (SearchMode.CODE, SearchMode.ALL) for c in cases)
    settings = SearchConfig()
    reports: list[dict] = []
    stats_started = perf_counter()
    try:
        console.print("[cyan]Loading corpus statistics once per active channel...[/]")
        async with SessionFactory() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            text_stats = await get_corpus_statistics(session, "TEXT") if active_text else None
            code_stats = await get_corpus_statistics(session, "CODE") if active_code else None
        stats_ms = round((perf_counter() - stats_started) * 1000, 1)
        with Progress(
            SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
            BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(), console=console,
        ) as progress:
            bar = progress.add_task("Running diagnostics", total=len(cases))
            for case in cases:
                progress.update(bar, description=f"[{case.id}] {case.query[:45]}")
                started = perf_counter()
                try:
                    async with SessionFactory() as session, session.begin():
                        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                        result = await compare_case(
                            session, case, k=args.k, settings=settings,
                            text_corpus=text_stats, code_corpus=code_stats,
                        )
                except Exception as exc:
                    result = {
                        "id": case.id,
                        "category": case.category,
                        "query": case.query,
                        "mode": case.mode.value,
                        "candidate_count": 0,
                        "expected_title_contains": case.expected_title_contains,
                        "expect_zero": case.expect_zero,
                        "top_k_overlap": None,
                        "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                        "error": f"{type(exc).__name__}: {str(exc)[:250]}",
                    }
                result["flags"] = classify(result, k=args.k, slow_ms=args.slow_ms)
                reports.append(result)
                progress.advance(bar)
        data = {
            "run_id": run_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "suite": str(args.suite),
            "settings": {"k": args.k, "slow_ms": args.slow_ms, "candidate_limit_per_channel": 100},
            "corpus": {
                "text": None if text_stats is None else {
                    "N": text_stats.document_count,
                    "avgDL": text_stats.average_document_length,
                },
                "code": None if code_stats is None else {
                    "N": code_stats.document_count,
                    "avgDL": code_stats.average_document_length,
                },
            },
            "corpus_scan_ms": stats_ms,
            "warning": "Diagnostic heuristics and rank agreement, NOT judged retrieval or ranking relevance metrics.",
            "queries": reports,
        }
        print_summary(console, data, k=args.k)
        if args.details:
            if len(reports) > 10:
                console.print("[yellow]--details shows only the first 10; use --id for focused inspection.[/]")
            for report in reports[:10]:
                print_details(console, report, k=args.k)
        atomic_write(destination / "diagnostics.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        atomic_write(destination / "diagnostics.md", markdown_report(data, k=args.k))
        destination.mkdir(parents=True, exist_ok=True)
        console.save_html(str(destination / "terminal.html"), clear=False)
        console.print(Panel.fit(
            f"[green]Saved[/] [bold]{destination / 'diagnostics.json'}[/]\n"
            f"[green]Saved[/] [bold]{destination / 'diagnostics.md'}[/]\n"
            f"[green]Saved[/] [bold]{destination / 'terminal.html'}[/]",
            title="Output", border_style="green",
        ))
        return 2 if any("ERROR" in r["flags"] for r in reports) else 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--id", dest="ids", action="append", help="Run only this query ID; repeatable")
    parser.add_argument("--details", action="store_true", help="Show both top-K rankings for up to 10 queries")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--limit", type=int, default=None, help="Run only first N cases (smoke test)")
    parser.add_argument("--k", type=int, default=10, help="Rank comparison and preview cutoff (1..100)")
    parser.add_argument("--slow-ms", type=float, default=5000, help="Slow query warning threshold")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if not 1 <= args.k <= 100:
        parser.error("--k must be between 1 and 100")
    if args.slow_ms <= 0:
        parser.error("--slow-ms must be positive")
    if not args.suite.is_file():
        parser.error(f"Suite not found: {args.suite}")
    try:
        sys.exit(asyncio.run(run(args)))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
