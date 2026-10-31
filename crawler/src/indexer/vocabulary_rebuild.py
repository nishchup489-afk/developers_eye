"""One-shot, transactionally consistent vocabulary backfill/drift repair.

Run with indexing and crawler writers stopped for operational predictability:
    python -m indexer.vocabulary_rebuild

This is a CLI inside the existing indexer package, not another worker.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.session import SessionFactory
from backend.models.search_index import SearchIndex
from backend.models.search_terms import SearchTerm
from indexer.vocabulary import lock_vocabulary, vocabulary_terms

log = logging.getLogger(__name__)


async def rebuild_vocabulary(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    """Recount once per indexed document and atomically replace frequencies.

    Advisory lock serializes this rebuild with compliant indexer/crawler paths.
    All changes roll back on error. Avoid any concurrent manual SQL writes.
    """
    async with session_factory() as session:
        async with session.begin():
            await lock_vocabulary(session)
            query = select(
                func.tsvector_to_array(
                    SearchIndex.search_vector.op(
                        "||", return_type=SearchIndex.search_vector.type
                    )(SearchIndex.code_vector)
                )
            ).order_by(SearchIndex.document_id)
            counts: Counter[str] = Counter()
            documents = 0
            result = await session.stream(query)
            async for (lexemes,) in result:
                documents += 1
                counts.update(vocabulary_terms(lexemes or ()))

            await session.execute(delete(SearchTerm))
            sorted_terms = sorted(counts.items())
            for offset in range(0, len(sorted_terms), 500):
                rows = [
                    {"term": term, "document_frequency": frequency}
                    for term, frequency in sorted_terms[offset:offset + 500]
                ]
                await session.execute(insert(SearchTerm), rows)
            return documents, len(counts)


async def main() -> None:
    documents, terms = await rebuild_vocabulary(SessionFactory)
    log.info("Vocabulary rebuilt from %s indexed documents: %s terms", documents, terms)
    print(f"Rebuilt vocabulary: {documents} indexed documents; {terms} unique terms")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
