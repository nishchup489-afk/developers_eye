"""PostgreSQL-backed statistics for Developer's Eye BM25 ranking.

Current storage: search_index(search_vector, code_vector).

All position counts are approximate: PostgreSQL TSVECTOR can truncate
positions and combine fields. For exact BM25 and high QPS, write
per-document TF/length and per-channel DF/corpus counts during indexing.

Production usage:
    1. Compute/load CorpusStatistics separately from the query path.
    2. Pass a consistent corpus snapshot to load_channel_statistics().
    3. Score candidates with bm25.py; this module never calculates BM25.
"""

### This version reduces the database query from 607 round trips to 2

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, cast as type_cast

from sqlalchemy import cast, func, literal, select, true, union_all
from sqlalchemy.dialects.postgresql import JSONB , TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_index import SearchIndex
from backend.search.ranking.types import (
    ChannelStatistics,
    CorpusStatistics,
    DocumentStatistics,
)

RankMode = Literal["TEXT", "CODE"]
MAX_CANDIDATES = 200
MAX_QUERY_TERMS = 32
MAX_TERM_LENGTH = 256


def _normalize_mode(mode: str) -> RankMode:
    if not isinstance(mode, str):
        raise TypeError("mode must be a string")
    normalized = mode.upper()
    if normalized not in ("TEXT", "CODE"):
        raise ValueError("mode must be TEXT or CODE")
    return type_cast(RankMode, normalized)


def _get_vector(mode: str):
    """Return the TSVECTOR column matching the retrieval channel."""
    return (
        SearchIndex.search_vector
        if _normalize_mode(mode) == "TEXT"
        else SearchIndex.code_vector
    )


def _search_config(mode: str) -> str:
    return "english" if _normalize_mode(mode) == "TEXT" else "simple"


def _validate_document_id(document_id: int) -> None:
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")


def _validate_term(term: str) -> str:
    """Accept one already-normalized lexeme (not a raw search query)."""
    if not isinstance(term, str):
        raise TypeError("term must be a string")
    if not term or term != term.strip() or len(term) > MAX_TERM_LENGTH:
        raise ValueError("term must be a nonempty normalized lexeme")
    if any(ch.isspace() or ord(ch) < 32 for ch in term):
        raise ValueError("term must contain one lexeme, not whitespace")
    return term


def _validate_terms(terms: Iterable[str]) -> tuple[str, ...]:
    if isinstance(terms, str):
        raise TypeError("terms must be an iterable of individual lexemes")
    unique = tuple(dict.fromkeys(_validate_term(term) for term in terms))
    if len(unique) > MAX_QUERY_TERMS:
        raise ValueError(f"at most {MAX_QUERY_TERMS} terms are supported")
    return unique


def _validate_ids(document_ids: Iterable[int]) -> tuple[int, ...]:
    if isinstance(document_ids, (str, bytes)):
        raise TypeError("document_ids must be an iterable of integers")
    unique = tuple(dict.fromkeys(document_ids))
    if len(unique) > MAX_CANDIDATES:
        raise ValueError(f"at most {MAX_CANDIDATES} candidates are supported")
    for document_id in unique:
        _validate_document_id(document_id)
    return unique


def _lexemes(vector):
    """Expand one TSVECTOR to (lexeme, positions, weights) rows."""
    return (
        func.unnest(vector)
        .table_valued("lexeme", "positions", "weights")
        .render_derived(name="t")
        .lateral()
    )


async def _get_total_number_of_indexed_document(
    session: AsyncSession,
) -> int:
    stmt = select(func.count()).select_from(SearchIndex)
    return int(await session.scalar(stmt) or 0)

def _exact_lexeme_query(term: str):
    """Convert an indexed lexeme into a TSQUERY without stemming."""
    escaped = term.replace("\\", "\\\\").replace("'", "''")
    return cast(literal(f"'{escaped}'"), TSQUERY)


async def _get_document_frequencies(
    session: AsyncSession,
    terms: Iterable[str],
    mode: str,
) -> dict[str, int]:
    """Count documents containing each exact indexed lexeme."""
    lexemes = _validate_terms(terms)
    vector = _get_vector(mode)

    if not lexemes:
        return {}

    queries = [
        select(
            literal(term).label("term"),
            func.count().label("document_frequency"),
        )
        .select_from(SearchIndex)
        .where(
            vector.bool_op("@@")(
                _exact_lexeme_query(term)
            )
        )
        for term in lexemes
    ]

    stmt = (
        queries[0]
        if len(queries) == 1
        else union_all(*queries)
    )

    rows = (await session.execute(stmt)).all()

    return {
        str(term): int(count)
        for term, count in rows
    }


async def _number_of_document_containing_term_t(
    session: AsyncSession,
    term: str,
    mode: str,
) -> int:
    """DF: count indexed documents matching one normalized query lexeme."""
    frequencies = await _get_document_frequencies(session, (term,), mode)
    return frequencies[term]


async def _get_candidate_documents(
    session: AsyncSession,
    document_ids: Iterable[int],
    terms: Iterable[str],
    mode: str,
) -> dict[int, DocumentStatistics]:
    """Batch-load approximate DL and TF in ONE database round trip."""
    ids = _validate_ids(document_ids)
    lexemes = _validate_terms(terms)
    vector = _get_vector(mode)
    if not ids:
        return {}

    t = _lexemes(vector)
    dl = func.coalesce(
        func.sum(func.cardinality(t.c.positions)), 0
    ).label("document_length")

    if lexemes:
        tf_object = func.coalesce(
            func.jsonb_object_agg(
                t.c.lexeme,
                func.cardinality(t.c.positions),
            ).filter(t.c.lexeme.in_(lexemes)),
            cast(literal("{}"), JSONB),
        ).label("term_frequencies")
    else:
        tf_object = cast(literal("{}"), JSONB).label("term_frequencies")

    stmt = (
        select(SearchIndex.document_id, dl, tf_object)
        .select_from(SearchIndex)
        .outerjoin(t, true())
        .where(SearchIndex.document_id.in_(ids))
        .group_by(SearchIndex.document_id)
    )
    rows = (await session.execute(stmt)).all()

    return {
        int(row.document_id): DocumentStatistics(
            document_id=int(row.document_id),
            document_length=int(row.document_length),
            term_frequencies={
                term: int(frequency)
                for term, frequency in (row.term_frequencies or {}).items()
            },
        )
        for row in rows
    }


async def _get_term_frequency(
    session: AsyncSession,
    document_id: int,
    term: str,
    mode: str,
) -> int | None:
    """TF for one indexed document, or None if it is not indexed."""
    docs = await _get_candidate_documents(session, (document_id,), (term,), mode)
    stats = docs.get(document_id)
    return None if stats is None else stats.term_frequencies.get(term, 0)


async def _get_document_length(
    session: AsyncSession,
    document_id: int,
    mode: str,
) -> int | None:
    """Approximate indexed token length, or None if not indexed."""
    docs = await _get_candidate_documents(session, (document_id,), (), mode)
    stats = docs.get(document_id)
    return None if stats is None else stats.document_length


async def get_corpus_statistics(
    session: AsyncSession,
    mode: str,
) -> CorpusStatistics:
    """FULL-CORPUS SCAN. Compute periodically, not for every user query."""
    vector = _get_vector(mode)
    t = _lexemes(vector)
    lengths = (
        select(
            SearchIndex.document_id,
            func.coalesce(
                func.sum(func.cardinality(t.c.positions)), 0
            ).label("document_length"),
        )
        .select_from(SearchIndex)
        .outerjoin(t, true())
        .group_by(SearchIndex.document_id)
        .subquery()
    )
    stmt = select(
        func.count(lengths.c.document_id),
        func.coalesce(func.avg(lengths.c.document_length), 0.0),
    ).select_from(lengths)
    total, average = (await session.execute(stmt)).one()
    return CorpusStatistics(
        document_count=int(total),
        average_document_length=float(average),
    )


async def _get_average_document_length(
    session: AsyncSession,
    mode: str,
) -> float:
    """Full-scan avgdl helper; do not invoke on the hot query path."""
    return (await get_corpus_statistics(session, mode)).average_document_length


async def load_channel_statistics(
    session: AsyncSession,
    document_ids: Iterable[int],
    terms: Iterable[str],
    mode: str,
    *,
    corpus: CorpusStatistics,
) -> ChannelStatistics:
    """Batch-load DF and candidate TF/DL from a supplied corpus snapshot.

    The caller must supply corpus statistics calculated/cached outside the
    latency-sensitive search path. DF uses indexed lookups; TF and DL are
    fetched together for all candidates.
    """
    if not isinstance(corpus, CorpusStatistics):
        raise TypeError("corpus must be CorpusStatistics")
    ids = _validate_ids(document_ids)
    lexemes = _validate_terms(terms)
    _normalize_mode(mode)

    if not ids:
        return ChannelStatistics(
            corpus=corpus,
            document_frequencies={},
            documents={},
        )

    frequencies = await _get_document_frequencies(session, lexemes, mode)
    documents = await _get_candidate_documents(session, ids, lexemes, mode)
    return ChannelStatistics(
        corpus=corpus,
        document_frequencies=frequencies,
        documents=documents,
    )
