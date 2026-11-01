"""Read-only PostgreSQL vocabulary reporting for the admin control center.

Describes the `search_terms` projection that the indexer maintains from
`search_index` lexemes. It never writes, locks, or rebuilds the vocabulary.
Frequencies count documents containing a term, not occurrences.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select

from backend.models.search_index import SearchIndex
from backend.models.search_terms import SearchTerm
from backend.services.crawler_reporting import _percentage, _utc

LIST_LIMIT = 30
# Inclusive lower bounds; the last bucket is open-ended.
BUCKETS = ((1, 1), (2, 4), (5, 19), (20, 99), (100, None))


def _bucket_label(low: int, high: int | None) -> str:
    if high is None:
        return f"{low}+"
    return str(low) if low == high else f"{low}-{high}"


async def build_vocabulary_report(session, *, query: str | None = None):
    now = datetime.now(timezone.utc)
    df = SearchTerm.document_frequency
    indexed_documents = (await session.execute(select(func.count(SearchIndex.document_id)))).scalar_one()

    summary = dict((await session.execute(select(
        func.count(SearchTerm.term).label("total_terms"),
        func.count(SearchTerm.term).filter(df == 0).label("zero_frequency_terms"),
        func.count(SearchTerm.term).filter(df == 1).label("singleton_terms"),
        # A term cannot appear in more documents than are indexed; any hit means drift.
        func.count(SearchTerm.term).filter(df > indexed_documents).label("overcounted_terms"),
        func.coalesce(func.max(df), 0).label("max_document_frequency"),
        func.coalesce(func.sum(df), 0).label("total_postings"),
    ))).mappings().one())
    summary["indexed_documents"] = indexed_documents
    summary["average_terms_per_document"] = (
        round(summary["total_postings"] / indexed_documents, 2) if indexed_documents else None)
    summary["singleton_percent"] = _percentage(summary["singleton_terms"], summary["total_terms"])

    distribution = []
    for low, high in BUCKETS:
        condition = df >= low if high is None else df.between(low, high)
        terms = (await session.execute(select(func.count()).select_from(SearchTerm).where(condition))).scalar_one()
        distribution.append(dict(label=_bucket_label(low, high), min=low, max=high, terms=terms))

    def rows(statement):
        return statement.order_by(df.desc(), SearchTerm.term).limit(LIST_LIMIT)

    top = (await session.execute(rows(select(SearchTerm.term, df)))).all()
    matches = None
    if query:
        needle = query.casefold()
        similarity = func.similarity(SearchTerm.term, needle)
        found = (await session.execute(
            select(SearchTerm.term, df, similarity.label("similarity"))
            .where((SearchTerm.term.op("%")(needle)) | SearchTerm.term.startswith(needle, autoescape=True))
            .order_by(similarity.desc(), df.desc(), SearchTerm.term).limit(LIST_LIMIT))).all()
        matches = [dict(term=term, document_frequency=freq, similarity=round(float(score), 3),
                        document_percent=_percentage(freq, indexed_documents)) for term, freq, score in found]

    return dict(
        version=1, generated_at=_utc(now), query=query or None, summary=summary, distribution=distribution,
        top_terms=[dict(term=term, document_frequency=freq, document_percent=_percentage(freq, indexed_documents))
                   for term, freq in top],
        matches=matches,
    )
