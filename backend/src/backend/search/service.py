"""Online search orchestration for Developer's Eye.

Analyzer -> selector -> text/code retrieval -> merge -> BM25 ->
metadata filtering -> pagination -> snippets -> public result objects.

CorpusStatistics come from a snapshot that main.py refreshes in the background,
never from a scan per query. A snapshot trails the index slightly, and
load_channel_statistics keeps it consistent with live counts. This remains
approximate candidate-set BM25 ranking.

Fuzzy query correction is deliberately not silently applied. The current
fuzzy candidate lookup/correction must be repaired and its suggestion
exposed through an explicit API contract before enabling that feature.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.schema.search import SearchFilter, SearchResultOut
from backend.search.categories import categories_for_filter, categorize
from backend.search.config import SearchConfig
from backend.search.merge import merge_hits
from backend.search.pagination import paginate_hits
from backend.search.query_analyzer.analyzer import analyze_query
from backend.search.query_selector.planner import SearchMode, select_query_plan
from backend.search.ranking.orchestrator import rank_candidates
from backend.search.ranking.statistics import DocumentFrequencyCache
from backend.search.ranking.types import CorpusStatistics
from backend.search.retrieval.code import search_code
from backend.search.retrieval.fts import search_text
from backend.search.snippets.snippets import generate_snippet
from backend.search.snippets.code import code_excerpt
from backend.search.types import RankedHit, RetrievalHit
from backend.search.presentation import prefer_language, result_identity, variant_counts, LANGUAGE_TAG

CANDIDATES_PER_CHANNEL = 100  # ranker hard limit: 200 unique IDs
MAX_SNIPPET_SOURCE_CHARS = 12_000

# Per-worker, immutable snapshots; installed and refreshed by main.py.
@dataclass(frozen=True, slots=True)
class _CorpusSnapshots:
    text: CorpusStatistics
    code: CorpusStatistics


_corpus_snapshots: _CorpusSnapshots | None = None
_corpus_loaded_at: datetime | None = None
_df_cache = DocumentFrequencyCache()


def set_corpus_statistics(text: CorpusStatistics, code: CorpusStatistics) -> None:
    """Install a precomputed per-channel corpus snapshot."""
    if not isinstance(text, CorpusStatistics) or not isinstance(code, CorpusStatistics):
        raise TypeError("text and code must be CorpusStatistics")
    global _corpus_snapshots, _corpus_loaded_at
    _corpus_snapshots = _CorpusSnapshots(text=text, code=code)
    _corpus_loaded_at = datetime.now(timezone.utc)


def clear_corpus_statistics() -> None:
    """Discard the cached snapshot on application shutdown."""
    global _corpus_snapshots
    _corpus_snapshots = None
    _df_cache.clear()


def corpus_snapshot_info() -> dict | None:
    """This process's BM25 snapshot, for the admin dashboard."""
    snapshot = _corpus_snapshots
    if snapshot is None:
        return None
    return dict(documents=snapshot.text.document_count, loaded_at=_corpus_loaded_at,
                average_text_length=round(snapshot.text.average_document_length, 1),
                average_code_length=round(snapshot.code.average_document_length, 1))


def _valid_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except (TypeError, ValueError):
        return False


def _tags(metadata: object) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    tags = metadata.get("tags")
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str) and tag][:8]


def _snippet_terms(query: str) -> tuple[str, ...]:
    """Use surface words for highlights, not PostgreSQL's stemmed lexemes."""
    terms: list[str] = []
    seen: set[str] = set()
    for term in re.findall(r"[A-Za-z_][A-Za-z0-9_+#.-]*", query):
        folded = term.casefold()
        if folded in {"and", "or", "not"} or folded in seen:
            continue
        if len(term) > 128:
            continue
        seen.add(folded)
        terms.append(term)
        if len(terms) == 32:
            break
    return tuple(terms)


async def _retrieve_candidates(
    session: AsyncSession,
    query: str,
    mode: SearchMode,
    categories: tuple[str, ...] | None = None,
) -> list[RetrievalHit]:
    """Run retrieval paths sequentially on one SQLAlchemy AsyncSession."""
    groups: list[list[RetrievalHit]] = []
    if mode in (SearchMode.ALL, SearchMode.TEXT):
        groups.append(await search_text(session, query, limit=CANDIDATES_PER_CHANNEL, categories=categories))
    if mode in (SearchMode.ALL, SearchMode.CODE):
        code_hits = await search_code(session, query, limit=CANDIDATES_PER_CHANNEL, categories=categories)
        groups.append([
            RetrievalHit(document_id=hit.document_id, code_rank=hit.score)
            for hit in code_hits
        ])
    return merge_hits(*groups)


async def _metadata_for_candidates(
    session: AsyncSession,
    ranked: list[RankedHit],
    categories: tuple[str, ...] | None,
) -> tuple[list[RankedHit], dict[int, object]]:
    """Filter available, URL-valid and category-compatible documents before paging."""
    if not ranked:
        return [], {}
    ids = [hit.document_id for hit in ranked]
    result = await session.execute(
        select(
            Document.id,
            Document.canonical_url,
            Document.document_type,
            Document.title,
            Document.description,
            func.jsonb_build_object("tags", Document.metadata_["tags"],
                                   "language", Document.metadata_["language"]).label("metadata_"),
            Document.content_hash,
        ).where(Document.id.in_(ids), Document.is_available.is_(True))
    )
    meta = {int(row.id): row for row in result.all()}
    eligible = [
        hit for hit in ranked
        if hit.document_id in meta
        and _valid_url(meta[hit.document_id].canonical_url)
        and (
            categories is None
            or categorize(
                meta[hit.document_id].canonical_url,
                meta[hit.document_id].document_type,
            ) in categories
        )
    ]
    return eligible, meta


async def search_documents(
    session: AsyncSession,
    query: str,
    *,
    category: SearchFilter | None = None,
    limit: int = 20,
    page: int = 1,
    mode: SearchMode | str = SearchMode.ALL,
    language: str | None = None,
) -> list[SearchResultOut]:
    """Return one page of BM25-ranked results with plain-text snippets.

    Session ownership remains with the API. Metadata filtering happens before
    paging, and document bodies are loaded only for the selected page.
    """
    settings = SearchConfig()
    if language is not None and not LANGUAGE_TAG.fullmatch(language):
        raise ValueError("language must be a language tag")
    if type(limit) is not int or not 1 <= limit <= settings.max_limit:
        raise ValueError(f"limit must be between 1 and {settings.max_limit}")
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer")
    if (page - 1) * limit > settings.max_offset:
        raise ValueError(f"offset cannot exceed {settings.max_offset}")

    normalized = analyze_query(query, config=settings)
    plan = select_query_plan(normalized, mode=mode)
    categories = categories_for_filter(category)
    candidates = await _retrieve_candidates(session, plan.query, plan.mode, categories)
    if not candidates:
        return []

    snapshot = _corpus_snapshots
    if snapshot is None:
        raise RuntimeError("BM25 corpus statistics not initialized; run app lifespan")

    ranked = await rank_candidates(
        session,
        plan.query,
        candidates,
        mode=plan.mode,
        text_corpus=snapshot.text,
        code_corpus=snapshot.code,
        tokenizer_config=settings,
        df_cache=_df_cache,
    )
    eligible, metadata = await _metadata_for_candidates(session, ranked, categories)
    eligible = prefer_language(eligible, metadata, language)
    variants_by_id = variant_counts(eligible, metadata)
    page_result = paginate_hits(eligible, page=page, limit=limit, config=settings)
    if not page_result.hits:
        return []

    ids = tuple(hit.document_id for hit in page_result.hits)
    body_query = select(
        Document.id,
        func.left(Document.body, MAX_SNIPPET_SOURCE_CHARS).label("body"),
        Document.metadata_["code_blocks"].label("code_blocks"),
        Document.last_seen_at,
    ).where(Document.id.in_(ids), Document.is_available.is_(True))
    bodies = {
        int(row.id): row
        for row in (await session.execute(body_query)).all()
    }

    terms = _snippet_terms(plan.query)
    results: list[SearchResultOut] = []
    for hit in page_result.hits:
        record = metadata[hit.document_id]
        if hit.document_id not in bodies:
            continue  # Deleted/disabled between metadata and body queries.
        body_record = bodies[hit.document_id]
        snippet_source = body_record.body or ""
        preserve_code = plan.mode is SearchMode.CODE
        code_source = ""
        if preserve_code:
            code_source = code_excerpt(body_record.code_blocks, terms, max_chars=MAX_SNIPPET_SOURCE_CHARS)
            snippet_source = code_source or snippet_source
        snippet = generate_snippet(
            snippet_source,
            terms,
            description=record.description,
            max_chars=settings.snippet_length,
            preserve_code=preserve_code,
        )
        declared_language, version, _ = result_identity(record.canonical_url, record.metadata_)
        results.append(
            SearchResultOut(
                title=record.title,
                source=categorize(record.canonical_url, record.document_type),
                url=record.canonical_url,
                snippet=snippet.text,
                score=round(hit.score, 6),
                tags=_tags(record.metadata_),
                type=record.document_type,
                language=declared_language,
                version=version,
                last_seen_at=getattr(body_record, "last_seen_at", None),
                related_variants=variants_by_id[hit.document_id] or None,
                snippet_is_code=bool(code_source),
            )
        )
    return results


__all__ = ["categorize", "search_documents", "set_corpus_statistics", "clear_corpus_statistics"]
