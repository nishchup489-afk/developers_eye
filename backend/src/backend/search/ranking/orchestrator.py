"""Orchestrate BM25 ranking of merged Developer's Eye retrieval hits.

Retrieval enforces PostgreSQL TSQUERY matching semantics. This module only
reranks the already-retrieved candidate set; it never expands that set.

CorpusStatistics must come from a separately maintained/refreshed snapshot.
Do not invoke full-corpus scans on the request path.
"""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite

from sqlalchemy.ext.asyncio import AsyncSession

from backend.search.config import SearchConfig
from backend.search.merge import merge_hits
from backend.search.query_selector.planner import SearchMode
from backend.search.ranking.bm25 import apply_BM25
from backend.search.ranking.statistics import DocumentFrequencyCache, MAX_CANDIDATES, load_channel_statistics
from backend.search.ranking.types import CorpusStatistics, RankingConfig
from backend.search.tokenizer import tokenize_query
from backend.search.types import RankedHit, RetrievalHit


def _parse_mode(mode: SearchMode | str) -> SearchMode:
    """Normalize a public search mode; statistics accepts TEXT/CODE only."""
    if isinstance(mode, SearchMode):
        return mode
    if not isinstance(mode, str):
        raise TypeError("mode must be a SearchMode or string")
    try:
        return SearchMode(mode.strip().lower())
    except ValueError as exc:
        raise ValueError("mode must be all, text, or code") from exc


def _required_corpus(
    corpus: CorpusStatistics | None,
    *,
    name: str,
) -> CorpusStatistics:
    if not isinstance(corpus, CorpusStatistics):
        raise ValueError(f"{name} must be a precomputed CorpusStatistics")
    return corpus


async def rank_candidates(
    session: AsyncSession,
    query: str,
    hits: Iterable[RetrievalHit],
    *,
    mode: SearchMode | str = SearchMode.ALL,
    config: RankingConfig | None = None,
    text_corpus: CorpusStatistics | None = None,
    code_corpus: CorpusStatistics | None = None,
    df_cache: DocumentFrequencyCache | None = None,
    tokenizer_config: SearchConfig | None = None,
) -> list[RankedHit]:
    """Score and sort existing retrieval candidates with channel-aware BM25.

    - Deduplicates candidates using merge_hits (max preliminary score/channel).
    - Tokenizes once with PostgreSQL English and Simple query configurations.
    - Loads DF/TF/DL in batches for each active, positively weighted channel.
    - Leaves retrieval scores available on RankedHit for diagnostics.
    - Excludes documents that disappeared from search_index before scoring.
    - Uses document_id ascending as a stable score tie-breaker.

    A query with no positive terms in the selected channels has no BM25
    representation, so it returns no ranked hits. Retrieval still owns
    matching, including OR, phrase, and exclusion semantics.
    """
    selected_mode = _parse_mode(mode)

    if config is None:
        config = RankingConfig()
    elif not isinstance(config, RankingConfig):
        raise TypeError("config must be RankingConfig")

    if tokenizer_config is not None and not isinstance(tokenizer_config, SearchConfig):
        raise TypeError("tokenizer_config must be SearchConfig or None")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if isinstance(hits, (str, bytes)) or not isinstance(hits, Iterable):
        raise TypeError("hits must be an iterable of RetrievalHit")

    # Treat single-channel mode as unweighted BM25. Channel weights affect
    # score fusion only in ALL mode.
    do_text = selected_mode is SearchMode.TEXT or (
        selected_mode is SearchMode.ALL and config.text_weight > 0
    )
    do_code = selected_mode is SearchMode.CODE or (
        selected_mode is SearchMode.ALL and config.code_weight > 0
    )

    candidates = merge_hits(hits)
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"at most {MAX_CANDIDATES} unique candidates are supported")
    if not candidates:
        return []

    if do_text:
        text_corpus = _required_corpus(text_corpus, name="text_corpus")
    if do_code:
        code_corpus = _required_corpus(code_corpus, name="code_corpus")

    text_terms, code_terms = await tokenize_query(
        session, query, config=tokenizer_config
    )
    if not ((do_text and text_terms) or (do_code and code_terms)):
        return []

    document_ids = tuple(hit.document_id for hit in candidates)
    cache = {"df_cache": df_cache} if df_cache is not None else {}
    text_scores: dict[int, float] = {}
    code_scores: dict[int, float] = {}
    indexed_ids: set[int] = set()

    if do_text and text_terms:
        text_stats = await load_channel_statistics(
            session,
            document_ids,
            text_terms,
            "TEXT",
            corpus=text_corpus,
            **cache,
        )
        text_scores = apply_BM25(text_stats, text_terms, config.bm25)
        indexed_ids.update(text_stats.documents)

    if do_code and code_terms:
        code_stats = await load_channel_statistics(
            session,
            document_ids,
            code_terms,
            "CODE",
            corpus=code_corpus,
            **cache,
        )
        code_scores = apply_BM25(code_stats, code_terms, config.bm25)
        indexed_ids.update(code_stats.documents)

    results: list[RankedHit] = []
    for hit in candidates:
        if hit.document_id not in indexed_ids:
            continue

        text_score = text_scores.get(hit.document_id, 0.0)
        code_score = code_scores.get(hit.document_id, 0.0)

        if selected_mode is SearchMode.TEXT:
            final_score = text_score
        elif selected_mode is SearchMode.CODE:
            final_score = code_score
        else:
            final_score = (
                config.text_weight * text_score
                + config.code_weight * code_score
            )

        if not isfinite(final_score) or final_score < 0:
            raise ValueError("BM25 produced an invalid combined score")

        results.append(
            RankedHit(
                document_id=hit.document_id,
                score=final_score,
                # Preserve preliminary PostgreSQL scores, not BM25 components.
                search_rank=hit.search_rank,
                code_rank=hit.code_rank,
            )
        )

    results.sort(key=lambda item: (-item.score, item.document_id))
    return results


__all__ = ["rank_candidates"]
