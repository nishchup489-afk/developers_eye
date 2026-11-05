"""GET /search, serving the same response shape as the Next.js bridge."""

import asyncio
import logging
import os
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import SessionFactory
from backend.schema.search import SearchFilter, SearchResponseOut
from backend.schema.search_term import QueryCorrection
from backend.search.query_analyzer.analyzer import QueryValidationError, analyze_query
from backend.search.query_selector.planner import SearchMode
from backend.search.service import search_documents
from backend.search.retrieval.fuzzy.correction import suggest_query_correction

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

MAX_CONCURRENT_SEARCHES = int(os.environ.get("SEARCH_MAX_CONCURRENT", "16"))
QUERY_DEADLINE_MS = int(os.environ.get("SEARCH_QUERY_DEADLINE_MS", "3000"))
_in_flight = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)


async def apply_query_deadline(session: AsyncSession) -> None:
    """Cancel any statement of this search that runs past the deadline."""
    await session.execute(select(func.set_config("statement_timeout", str(QUERY_DEADLINE_MS), True)))


@router.get("/search", response_model=SearchResponseOut)
async def search(
    response: Response,
    q: Annotated[str, Query(max_length=1024)],
    source: SearchFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    page: Annotated[int, Query(ge=1)] = 1,
    mode: SearchMode = SearchMode.ALL,
) -> SearchResponseOut:
    try:
        normalized = analyze_query(q)
    except QueryValidationError as exc:
        raise HTTPException(422, str(exc)) from exc

    response.headers["Cache-Control"] = "no-store"
    if _in_flight.locked():
        raise HTTPException(503, "Search is busy; try again shortly", headers={"Retry-After": "1"})
    try:
        async with _in_flight, SessionFactory() as session:
            await apply_query_deadline(session)
            # Preserve the previous call signature for default requests.
            extra = {}
            if page != 1:
                extra["page"] = page
            if mode is not SearchMode.ALL:
                extra["mode"] = mode
            results = await search_documents(
                session, normalized, category=source, limit=limit, **extra
            )
    except (ValueError, QueryValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception("Search database failure")
        raise HTTPException(503, "Search database is unavailable") from exc
    except RuntimeError as exc:
        logger.error("Search engine unavailable: %s", type(exc).__name__)
        raise HTTPException(503, "Search engine is not initialized") from exc

    return SearchResponseOut(query=normalized, results=results)


@router.get("/search/suggest", response_model=QueryCorrection)
async def suggest_search_query(
    q: Annotated[str, Query(max_length=1024)],
) -> QueryCorrection:
    """Explicit spelling suggestion from the indexer-maintained vocabulary."""
    try:
        normalized = analyze_query(q)
        async with SessionFactory() as session:
            return await suggest_query_correction(normalized, session)
    except (ValueError, QueryValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception("Vocabulary suggestion query failed")
        raise HTTPException(503, "Search suggestions are unavailable") from exc
