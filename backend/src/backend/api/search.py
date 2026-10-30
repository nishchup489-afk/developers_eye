"""Public GET /search, called server-side by the Next.js /api/search bridge."""

import logging
import unicodedata
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError

from backend.db.session import SessionFactory
from backend.schema.search import SearchCategory, SearchResponseOut
from backend.search.service import search_documents

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponseOut)
async def search(
    response: Response,
    q: Annotated[str, Query(max_length=300)],
    source: SearchCategory | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponseOut:
    query = " ".join(q.split())
    if not query:
        raise HTTPException(422, "Enter a query between 1 and 300 characters.")
    if any(unicodedata.category(char) == "Cc" for char in query):
        raise HTTPException(422, "The query contains unsupported control characters.")
    response.headers["Cache-Control"] = "no-store"
    try:
        async with SessionFactory() as session:
            results = await search_documents(session, query, category=source, limit=limit)
    except SQLAlchemyError as exc:
        logger.error("Search query failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Search is unavailable. Check the database connection.") from exc
    return SearchResponseOut(query=query, results=results)
