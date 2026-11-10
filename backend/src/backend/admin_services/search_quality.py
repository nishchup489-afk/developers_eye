"""Admin search diagnostics and human relevance judging (ADR-0057).

Reads: slow and timed-out searches with stage timings, and judged metrics
(P@k, MRR@k, nDCG@k, judged candidate recall) for BM25 and PostgreSQL over the
same pooled candidates. Writes: judging queries, pools, grades and notes.
Metrics use backend.search.evaluation.metrics, the same code as the offline
scorer, and stay "incomplete" until every pooled URL has a human grade.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.models.search_quality import RelevanceJudgment, RelevanceQuery, RelevanceRun, SearchSlowQuery
from backend.search.evaluation.metrics import evaluate_query
from backend.search.evaluation.pooling import capture_pool, pooled_urls
from backend.search.telemetry import SLOW_QUERY_MS, telemetry
from backend.search.trace import STAGES

HUMAN_SET = Path(__file__).resolve().parents[1] / "search" / "evaluation" / "human_judging_queries.json"
MODES = ("all", "text", "code")
SOURCES = ("docs", "github", "stackoverflow", "reddit", "articles", "events", "practice", "discussions")
MAX_NOTE_CHARS = 2000


class JudgingError(ValueError):
    """A judging write that the admin should correct (HTTP 422)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slow_row(row: dict) -> dict:
    return dict(
        recorded_at=row["recorded_at"].isoformat(), query=row["query"], mode=row["mode"],
        category=row["category"], page=row["page"], outcome=row["outcome"], elapsed_ms=row["elapsed_ms"],
        result_count=row["result_count"], stages=row["stages"] or {}, stopped_in=row["stopped_in"],
    )


async def build_slow_query_report(session: AsyncSession, *, hours: int = 24, limit: int = 100) -> dict:
    since = _now() - timedelta(hours=hours)
    columns = (SearchSlowQuery.recorded_at, SearchSlowQuery.query, SearchSlowQuery.mode, SearchSlowQuery.category,
               SearchSlowQuery.page, SearchSlowQuery.outcome, SearchSlowQuery.elapsed_ms,
               SearchSlowQuery.result_count, SearchSlowQuery.stages, SearchSlowQuery.stopped_in)
    stored = [dict(row._mapping) for row in (await session.execute(
        select(*columns).where(SearchSlowQuery.recorded_at >= since)
        .order_by(SearchSlowQuery.recorded_at.desc()).limit(1000)
    )).all()]
    # Rows this process has not flushed yet, so a slow search shows up at once.
    pending = [row for row in telemetry.slow_rows() if row["recorded_at"] >= since]
    rows = sorted(stored + pending, key=lambda r: r["recorded_at"], reverse=True)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        group = grouped.setdefault((row["query"].casefold(), row["mode"]), dict(
            query=row["query"], mode=row["mode"], count=0, timed_out=0, max_ms=0, total_ms=0))
        group["count"] += 1
        group["timed_out"] += row["outcome"] == "timed_out"
        group["max_ms"] = max(group["max_ms"], row["elapsed_ms"])
        group["total_ms"] += row["elapsed_ms"]
    repeated = sorted(grouped.values(), key=lambda g: (-g["count"], -g["max_ms"]))[:20]
    for group in repeated:
        group["mean_ms"] = round(group.pop("total_ms") / group["count"])

    stage_means = {}
    for name in STAGES:
        values = [row["stages"][name] for row in rows if name in (row["stages"] or {})]
        stage_means[name] = round(mean(values), 1) if values else None
    stopped = {}
    for row in rows:
        if row["stopped_in"]:
            stopped[row["stopped_in"]] = stopped.get(row["stopped_in"], 0) + 1
    return dict(
        hours=hours, threshold_ms=SLOW_QUERY_MS, total=len(rows),
        timed_out=sum(row["outcome"] == "timed_out" for row in rows),
        stage_means_ms=stage_means, timeouts_by_stage=stopped,
        repeated=repeated, queries=[_slow_row(row) for row in rows[:limit]],
    )


async def _queries(session: AsyncSession) -> list[RelevanceQuery]:
    return list((await session.scalars(select(RelevanceQuery).order_by(RelevanceQuery.id))).all())


async def _latest_runs(session: AsyncSession) -> dict[str, RelevanceRun]:
    latest = select(RelevanceRun.query_id, func.max(RelevanceRun.id).label("id")).group_by(RelevanceRun.query_id).subquery()
    runs = (await session.scalars(select(RelevanceRun).join(latest, latest.c.id == RelevanceRun.id))).all()
    return {run.query_id: run for run in runs}


async def _judgments(session: AsyncSession) -> dict[str, list[RelevanceJudgment]]:
    by_query: dict[str, list[RelevanceJudgment]] = {}
    for judgment in (await session.scalars(select(RelevanceJudgment).order_by(RelevanceJudgment.url))).all():
        by_query.setdefault(judgment.query_id, []).append(judgment)
    return by_query


def _query_metrics(query: RelevanceQuery, run: RelevanceRun | None, judgments: list[RelevanceJudgment], k: int) -> dict:
    graded = sum(j.grade is not None for j in judgments)
    base = dict(
        id=query.id, query=query.query, mode=query.mode, stratum=query.stratum, source=query.source,
        note=query.note, no_relevant_documents=query.no_relevant_documents,
        pooled=len(judgments), graded=graded, positives=sum((j.grade or 0) > 0 for j in judgments),
        last_pooled_at=run.created_at.isoformat() if run else None,
        candidate_count=run.candidate_count if run else None,
    )
    if run is None:
        return {**base, "status": "not_pooled", "reason": "Capture a pool first"}
    report = dict(query_id=query.id, query=query.query, mode=query.mode,
                  candidate_count=run.candidate_count, documents=run.documents)
    result = evaluate_query(report, dict(
        judgments={j.url: j.grade for j in judgments},
        no_relevant_documents=query.no_relevant_documents,
    ), k=k)
    keep = ("status", "reason", "candidate_recall_at_100_per_channel", "bm25", "postgresql")
    return {**base, **{key: result[key] for key in keep if key in result}}


def _aggregate(rows: list[dict], k: int) -> dict:
    complete = [row for row in rows if row["status"] == "complete"]

    def avg(variant: str | None, name: str):
        values = [(row[variant][name] if variant else row[name]) for row in complete]
        values = [v for v in values if v is not None]
        return round(mean(values), 4) if values else None

    names = (f"precision_at_{k}", f"mrr_at_{k}", f"ndcg_at_{k}")
    return dict(
        complete_queries=len(complete), total_queries=len(rows),
        status="complete" if rows and len(complete) == len(rows) else "incomplete",
        bm25={name: avg("bm25", name) for name in names},
        postgresql={name: avg("postgresql", name) for name in names},
        candidate_recall=avg(None, "candidate_recall_at_100_per_channel"),
    )


async def build_evaluation_report(session: AsyncSession, *, k: int = 10) -> dict:
    if k not in (5, 10):
        raise JudgingError("k must be 5 or 10")
    queries = await _queries(session)
    runs = await _latest_runs(session)
    judgments = await _judgments(session)
    rows = [_query_metrics(q, runs.get(q.id), judgments.get(q.id, []), k) for q in queries]
    return dict(k=k, human_set_available=HUMAN_SET.exists(), aggregate=_aggregate(rows, k), queries=rows)


async def get_judging_query(session: AsyncSession, query_id: str) -> dict | None:
    query = await session.get(RelevanceQuery, query_id)
    if query is None:
        return None
    judgments = (await session.scalars(
        select(RelevanceJudgment).where(RelevanceJudgment.query_id == query_id).order_by(RelevanceJudgment.url)
    )).all()
    # Alphabetical by URL and without either ranker's position, so order cannot bias a grade.
    return dict(
        id=query.id, query=query.query, mode=query.mode, stratum=query.stratum, source=query.source,
        note=query.note, no_relevant_documents=query.no_relevant_documents,
        judgments=[dict(url=j.url, title=j.title, grade=j.grade, note=j.note, origin=j.origin,
                        judged_by=j.judged_by, judged_at=j.judged_at.isoformat() if j.judged_at else None)
                   for j in judgments],
    )


def _clean_note(note: object) -> str:
    if note is None:
        return ""
    if not isinstance(note, str) or len(note) > MAX_NOTE_CHARS:
        raise JudgingError(f"note must be text of at most {MAX_NOTE_CHARS} characters")
    return note.strip()


async def upsert_query(session: AsyncSession, payload: dict) -> dict:
    query_id = payload.get("id")
    text_value = (payload.get("query") or "").strip() if isinstance(payload.get("query"), str) else ""
    mode = payload.get("mode", "all")
    source = payload.get("source") or None
    if not isinstance(query_id, str) or not query_id or len(query_id) > 32 or not all(c.isalnum() or c in "_-" for c in query_id):
        raise JudgingError("id must be 1-32 letters, digits, - or _")
    if not 1 <= len(text_value) <= 256:
        raise JudgingError("query must be 1-256 characters")
    if mode not in MODES:
        raise JudgingError("mode must be all, text or code")
    if source is not None and source not in SOURCES:
        raise JudgingError("source is not a search filter")
    values = dict(id=query_id, query=text_value, mode=mode, source=source,
                  stratum=_clean_note(payload.get("stratum"))[:64], note=_clean_note(payload.get("note")),
                  no_relevant_documents=bool(payload.get("no_relevant_documents", False)), updated_at=_now())
    statement = insert(RelevanceQuery).values(values)
    await session.execute(statement.on_conflict_do_update(
        index_elements=["id"], set_={k: statement.excluded[k] for k in values if k != "id"}))
    return values


async def delete_query(session: AsyncSession, query_id: str) -> bool:
    result = await session.execute(delete(RelevanceQuery).where(RelevanceQuery.id == query_id))
    return bool(result.rowcount)


async def import_human_set(session: AsyncSession, path: Path = HUMAN_SET) -> dict:
    """Add the prepared judging queries; existing ids and their grades are kept."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JudgingError("The prepared judging set is not shipped with this backend") from exc
    added = 0
    for item in manifest["queries"]:
        exists = await session.get(RelevanceQuery, item["query_id"])
        if exists is None:
            await upsert_query(session, dict(id=item["query_id"], query=item["query"], mode=item["mode"],
                                             stratum=item.get("stratum", ""), source=item.get("source")))
            added += 1
    return dict(added=added, total=len(manifest["queries"]))


async def capture_query_pool(session: AsyncSession, query_id: str, *, text_corpus, code_corpus) -> dict | None:
    query = await session.get(RelevanceQuery, query_id)
    if query is None:
        return None
    captured = await capture_pool(session, query.query, query.mode, source=query.source,
                                  text_corpus=text_corpus, code_corpus=code_corpus)
    session.add(RelevanceRun(query_id=query_id, candidate_count=captured["candidate_count"],
                             elapsed_ms=captured["elapsed_ms"], documents=captured["documents"]))
    pooled = pooled_urls(captured["documents"])
    if pooled:
        statement = insert(RelevanceJudgment).values(
            [dict(query_id=query_id, url=url, title=title, origin="pool") for url, title in pooled.items()])
        # A URL graded earlier keeps its grade; titles refresh.
        await session.execute(statement.on_conflict_do_update(
            index_elements=["query_id", "url"], set_=dict(title=statement.excluded.title)))
    return dict(id=query_id, candidate_count=captured["candidate_count"], pooled=len(pooled),
                elapsed_ms=captured["elapsed_ms"])


async def save_judgment(session: AsyncSession, query_id: str, payload: dict, *, judge: str | None) -> dict | None:
    url = payload.get("url")
    grade = payload.get("grade")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")) or len(url) > 2048:
        raise JudgingError("url must be an http(s) URL")
    if grade is not None and (type(grade) is not int or not 0 <= grade <= 3):
        raise JudgingError("grade must be 0, 1, 2, 3 or null")
    if await session.get(RelevanceQuery, query_id) is None:
        return None
    note = _clean_note(payload.get("note"))
    existing = await session.get(RelevanceJudgment, (query_id, url))
    if existing is None:
        if not payload.get("add"):
            raise JudgingError("This URL is not in the pool; add it as an independently found page")
        title = await session.scalar(select(Document.title).where(Document.canonical_url == url)) or ""
        session.add(RelevanceJudgment(query_id=query_id, url=url, title=title, grade=grade, note=note,
                                      origin="added", judged_by=judge, judged_at=_now() if grade is not None else None))
    else:
        await session.execute(update(RelevanceJudgment)
                              .where(RelevanceJudgment.query_id == query_id, RelevanceJudgment.url == url)
                              .values(grade=grade, note=note, judged_by=judge,
                                      judged_at=_now() if grade is not None else None))
    return dict(query_id=query_id, url=url, grade=grade, note=note)


async def remove_added_url(session: AsyncSession, query_id: str, url: str) -> bool:
    result = await session.execute(delete(RelevanceJudgment).where(
        RelevanceJudgment.query_id == query_id, RelevanceJudgment.url == url, RelevanceJudgment.origin == "added"))
    return bool(result.rowcount)


__all__ = [
    "JudgingError", "build_evaluation_report", "build_slow_query_report", "capture_query_pool",
    "delete_query", "get_judging_query", "import_human_set", "remove_added_url", "save_judgment", "upsert_query",
]
