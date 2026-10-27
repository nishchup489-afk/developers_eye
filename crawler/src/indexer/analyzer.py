"""Prepare weighted search fields from a validated IndexDocument.

Pipeline:
    IndexDocument -> analyze_index_document -> AnalyzedDocument -> vector.py

This module performs no I/O, tokenization, stemming, SQL construction, or
TSVECTOR generation. PostgreSQL performs linguistic analysis in vector.py.

Field weights are part of the index format. Bump INDEXER_INDEX_VERSION when
changing fields, weights, or their search configurations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from indexer.config import IndexerConfig
from indexer.errors import IndexDocumentError
from indexer.schemas import IndexDocument

Weight = Literal["A", "B", "C", "D"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyzedField:
    """One source field that vector.py should convert with to_tsvector()."""

    name: str
    text: str
    weight: Weight
    search_config: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyzedDocument:
    """Immutable field groups for two independently searchable vectors."""

    document_id: int
    source_id: int
    source_updated_at: datetime
    text_fields: tuple[AnalyzedField, ...]
    code_fields: tuple[AnalyzedField, ...]


def _join_items(
    items: tuple[str, ...], *, name: str, document_id: int
) -> str:
    """Keep item boundaries visible without modifying code indentation."""
    if not isinstance(items, tuple) or not all(isinstance(x, str) for x in items):
        raise IndexDocumentError(
            f"{name} must be a tuple of strings", document_id=document_id
        )
    return "\n\n".join(item for item in items if item.strip())


def _field(
    *,
    name: str,
    text: str,
    weight: Weight,
    search_config: str,
    document_id: int,
) -> AnalyzedField | None:
    """Ignore blank fields and reject NUL, which PostgreSQL text disallows."""
    if not isinstance(text, str):
        raise IndexDocumentError(f"{name} must be a string", document_id=document_id)
    if "\x00" in text:
        raise IndexDocumentError(
            f"{name} contains a NUL character", document_id=document_id
        )
    if not text.strip():
        return None
    return AnalyzedField(
        name=name, text=text, weight=weight, search_config=search_config
    )


def analyze_index_document(
    document: IndexDocument, *, config: IndexerConfig
) -> AnalyzedDocument:
    """Arrange prepared content into weighted prose and code search fields.

    `text_fields` use the English-style text configuration; `code_fields`
    use the simple-style code configuration. Both vectors are created later.
    """
    if not isinstance(document, IndexDocument):
        raise TypeError("document must be an IndexDocument")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    document_id = document.document_id
    headings = _join_items(
        document.headings, name="headings", document_id=document_id
    )
    tags = _join_items(document.tags, name="tags", document_id=document_id)
    code_blocks = _join_items(
        document.code_blocks, name="code_blocks", document_id=document_id
    )

    prose_specs: tuple[tuple[str, str, Weight], ...] = (
        ("title", document.title, "A"),
        ("tags", tags, "A"),
        ("headings", headings, "B"),
        ("description", document.description, "B"),
        ("body", document.body, "C"),
    )

    # The separate code vector uses 'simple' (by default) to avoid English
    # stemming of API names, symbols, and code snippets.
    code_specs: tuple[tuple[str, str, Weight], ...] = (
        ("tags", tags, "A"),
        ("title", document.title, "A"),
        ("code_blocks", code_blocks, "B"),
        ("headings", headings, "B"),
        ("canonical_url", document.canonical_url, "D"),
    )

    def make_fields(
        specs: tuple[tuple[str, str, Weight], ...], *, search_config: str
    ) -> tuple[AnalyzedField, ...]:
        fields: list[AnalyzedField] = []
        for name, value, weight in specs:
            field = _field(
                name=name,
                text=value,
                weight=weight,
                search_config=search_config,
                document_id=document_id,
            )
            if field is not None:
                fields.append(field)
        return tuple(fields)

    text_fields = make_fields(
        prose_specs, search_config=config.text_search_config
    )
    code_fields = make_fields(
        code_specs, search_config=config.code_search_config
    )

    # A URL alone is not sufficient searchable content. The writer should
    # instead handle empty documents according to the worker's error policy.
    if not text_fields and not code_blocks:
        raise IndexDocumentError(
            "document has no indexable content", document_id=document_id
        )

    return AnalyzedDocument(
        document_id=document_id,
        source_id=document.source_id,
        source_updated_at=document.source_updated_at,
        text_fields=text_fields,
        code_fields=code_fields,
    )


__all__ = [
    "AnalyzedField",
    "AnalyzedDocument",
    "analyze_index_document",
]
