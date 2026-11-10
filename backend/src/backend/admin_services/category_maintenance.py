"""Offline, bounded repair of derived index categories. Caller owns transaction."""
from collections import Counter

from sqlalchemy import bindparam, select, update
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.search.categories import categorize


async def refresh_categories(session, *, apply=False, batch_size=1000):
    if type(batch_size) is not int or not 1 <= batch_size <= 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    cursor, scanned, changed, transitions = 0, 0, 0, Counter()
    table = SearchIndex.__table__
    while True:
        rows = (await session.execute(select(
            SearchIndex.document_id, SearchIndex.category,
            Document.canonical_url, Document.document_type,
        ).join(Document, Document.id == SearchIndex.document_id)
          .where(SearchIndex.document_id > cursor)
          .order_by(SearchIndex.document_id).limit(batch_size))).all()
        if not rows:
            break
        repairs = []
        for row in rows:
            wanted = categorize(row.canonical_url, row.document_type)
            if wanted != row.category:
                transitions[f"{row.category}->{wanted}"] += 1
                repairs.append({"target_id": row.document_id, "old_category": row.category, "new_category": wanted})
        if apply and repairs:
            # Guard against overwriting a concurrent indexer's newer category.
            await session.execute(update(table).where(table.c.document_id == bindparam("target_id"),
                                                      table.c.category == bindparam("old_category"))
                                  .values(category=bindparam("new_category")), repairs)
        scanned += len(rows)
        changed += len(repairs)
        cursor = rows[-1].document_id
    return {"scanned": scanned, "eligible_changes": changed,
            "transitions": dict(transitions), "mode": "apply" if apply else "dry-run"}
