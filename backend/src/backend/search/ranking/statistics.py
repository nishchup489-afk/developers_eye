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

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from time import monotonic
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
CORPUS_SAMPLE_DOCUMENTS = 20_000
MAX_TERM_LENGTH = 256


class DocumentFrequencyCache:
    """Small in-process TTL cache of (channel, term) -> document frequency."""

    def __init__(self, ttl_seconds: float = 600.0, max_entries: int = 50_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[tuple[str, str], tuple[float, int]] = {}

    def __bool__(self) -> bool:
        return True

    def get_many(self, mode: str, terms: Iterable[str]) -> dict[str, int]:
        now = monotonic()
        found = {}
        for term in terms:
            entry = self._entries.get((mode, term))
            if entry is not None and entry[0] > now:
                found[term] = entry[1]
        return found

    def put_many(self, mode: str, frequencies: dict[str, int]) -> None:
        if len(self._entries) + len(frequencies) > self.max_entries:
            self._entries.clear()
        expires = monotonic() + self.ttl_seconds
        for term, frequency in frequencies.items():
            self._entries[(mode, term)] = (expires, frequency)

    def clear(self) -> None:
        self._entries.clear()


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


@asynccontextmanager
async def _gin_only_plans(session: AsyncSession) -> AsyncIterator[None]:
    """Keep the planner on GIN bitmap scans for the statements inside.

    A sequential scan evaluates @@ against every row, which detoasts every
    TSVECTOR in the table. For a common lexeme the planner still prefers that
    scan because it does not cost detoasting, and at 100k documents one count
    read 340k buffers and took over a second (EXP-0016). The GIN bitmap answers
    a single-lexeme match exactly, so the heap pages it visits are never
    detoasted. The previous setting is restored for the rest of the transaction.
    """
    previous = await session.scalar(select(func.current_setting("enable_seqscan")))
    await session.execute(select(func.set_config("enable_seqscan", "off", True)))
    yield
    # Not in a finally: after a failed statement the transaction is aborted,
    # and its rollback discards this transaction-local setting anyway.
    await session.execute(
        select(func.set_config("enable_seqscan", str(previous or "on"), True))
    )


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

    async with _gin_only_plans(session):
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
    *,
    sample_size: int = CORPUS_SAMPLE_DOCUMENTS,
) -> CorpusStatistics:
    """N is exact; avgdl comes from a page sample once the index is large.

    Unnesting every TSVECTOR takes minutes at millions of documents. avgdl only
    needs to be close, and a sample of about 20,000 documents gets there in a
    fraction of a second. Run this on a schedule, not for each query.
    """
    vector = _get_vector(mode)
    total = int(await session.scalar(select(func.count()).select_from(SearchIndex)) or 0)
    if total == 0:
        return CorpusStatistics(document_count=0, average_document_length=0.0)

    table = SearchIndex.__table__
    sampled = (
        table if total <= sample_size
        else table.tablesample(func.system(100.0 * sample_size / total))
    )
    t = _lexemes(sampled.c[vector.key])
    lengths = (
        select(
            sampled.c.document_id,
            func.coalesce(func.sum(func.cardinality(t.c.positions)), 0).label("document_length"),
        )
        .select_from(sampled)
        .outerjoin(t, true())
        .group_by(sampled.c.document_id)
        .subquery()
    )
    average = await session.scalar(select(func.coalesce(func.avg(lengths.c.document_length), 0.0)))
    return CorpusStatistics(
        document_count=total,
        average_document_length=float(average),
    )


def _consistent_corpus(
    corpus: CorpusStatistics,
    frequencies: dict[str, int],
    documents: dict[int, DocumentStatistics],
) -> CorpusStatistics:
    """Keep a periodic snapshot valid while the index grows between refreshes.

    Live DF can exceed a slightly old N. That is normal, not a user error, so N
    is raised just enough for BM25's inputs to stay consistent.
    """
    count = max(corpus.document_count, len(documents), *frequencies.values(), 0)
    average = corpus.average_document_length
    if average == 0 and documents:
        average = sum(d.document_length for d in documents.values()) / len(documents)
    if count == corpus.document_count and average == corpus.average_document_length:
        return corpus
    return CorpusStatistics(document_count=count, average_document_length=average)


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
    df_cache: DocumentFrequencyCache | None = None,
) -> ChannelStatistics:
    """Batch-load DF and candidate TF/DL from a supplied corpus snapshot.

    The caller must supply corpus statistics calculated/cached outside the
    latency-sensitive search path. DF uses indexed lookups; a common term can
    match much of the index, so df_cache keeps recent counts between queries.
    TF and DL are fetched together for all candidates.
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

    frequencies = dict(df_cache.get_many(mode, lexemes)) if df_cache else {}
    missing = tuple(term for term in lexemes if term not in frequencies)
    if missing:
        fetched = await _get_document_frequencies(session, missing, mode)
        frequencies.update(fetched)
        if df_cache:
            df_cache.put_many(mode, fetched)
    documents = await _get_candidate_documents(session, ids, lexemes, mode)
    return ChannelStatistics(
        corpus=_consistent_corpus(corpus, frequencies, documents),
        document_frequencies=frequencies,
        documents=documents,
    )
