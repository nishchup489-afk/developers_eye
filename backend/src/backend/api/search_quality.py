"""Admin search diagnostics and relevance judging API (ADR-0057).

Every route needs the shared report key; the Next.js proxy additionally lets
only administrators (not read-only viewers) reach the write routes.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError

from backend.admin_services import search_quality as quality
from backend.api.crawler_report import monitor_query, require_report_key
from backend.db.session import SessionFactory

router = APIRouter(prefix="/admin/search-quality", tags=["search quality"], dependencies=[Depends(require_report_key)])
logger = logging.getLogger(__name__)
MAX_JUDGE_CHARS = 64


@router.get("/slow")
async def slow_searches(response: Response, hours: Annotated[int, Query(ge=1, le=24 * 30)] = 24,
                        limit: Annotated[int, Query(ge=1, le=500)] = 100):
    return await monitor_query(response, quality.build_slow_query_report, hours=hours, limit=limit)


@router.get("/evaluation")
async def evaluation(response: Response, k: Annotated[int, Query()] = 10):
    if k not in (5, 10):
        raise HTTPException(422, "k must be 5 or 10")
    return await monitor_query(response, quality.build_evaluation_report, k=k)


@router.get("/queries/{query_id}")
async def judging_query(response: Response, query_id: str):
    return await monitor_query(response, quality.get_judging_query, query_id=query_id)


async def _write(response: Response, action, *args, **kwargs) -> Any:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        async with SessionFactory() as session, session.begin():
            result = await action(session, *args, **kwargs)
    except quality.JudgingError as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Search quality write failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Search quality storage is unavailable. Apply database migrations.") from exc
    if result is None or result is False:
        raise HTTPException(404, "Judging query not found")
    return result


def _judge(payload: dict) -> str | None:
    judge = payload.get("judge")
    return judge[:MAX_JUDGE_CHARS] if isinstance(judge, str) and judge.strip() else None


@router.put("/queries/{query_id}")
async def save_query(response: Response, query_id: str, payload: Annotated[dict, Body()]):
    return await _write(response, quality.upsert_query, {**payload, "id": query_id})


@router.delete("/queries/{query_id}")
async def remove_query(response: Response, query_id: str):
    await _write(response, quality.delete_query, query_id)
    return {"deleted": query_id}


@router.post("/queries/import")
async def import_queries(response: Response):
    return await _write(response, quality.import_human_set)


@router.post("/queries/{query_id}/pool")
async def capture_pool(response: Response, query_id: str):
    from backend.search import service
    from backend.search.ranking.statistics import get_corpus_statistics

    async def run(session, query_id):
        snapshot = service._corpus_snapshots
        text_corpus = snapshot.text if snapshot else await get_corpus_statistics(session, "TEXT")
        code_corpus = snapshot.code if snapshot else await get_corpus_statistics(session, "CODE")
        return await quality.capture_query_pool(session, query_id, text_corpus=text_corpus, code_corpus=code_corpus)

    return await _write(response, run, query_id)


@router.put("/queries/{query_id}/judgments")
async def save_judgment(response: Response, query_id: str, payload: Annotated[dict, Body()]):
    return await _write(response, quality.save_judgment, query_id, payload, judge=_judge(payload))


@router.delete("/queries/{query_id}/judgments")
async def remove_added_url(response: Response, query_id: str, url: Annotated[str, Query(max_length=2048)]):
    await _write(response, quality.remove_added_url, query_id, url)
    return {"deleted": url}
