"""Build weighted PostgreSQL full-text search expressions.

Pipeline:
    AnalyzedDocument -> SearchVectors -> writer.py

Pure SQL expression construction: no database connections, queries, writes,
commits, tokenization, stemming, or Python-side vector calculation.

The writer must still recheck source freshness within its transaction before
executing these expressions and persisting the resulting TSVECTOR values.
Changing field weights, text-search settings, or vector construction rules
requires incrementing INDEXER_INDEX_VERSION.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Text, cast, func, literal, literal_column
from sqlalchemy.dialects.postgresql import REGCONFIG, TSVECTOR
from sqlalchemy.sql.elements import ColumnElement

from indexer.analyzer import AnalyzedDocument, AnalyzedField
from indexer.config import IndexerConfig

# Valid unquoted PostgreSQL configuration identifiers, optionally schema-qualified.
# The name is *also* bound as data, never interpolated into raw SQL.
_CONFIG_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)?\Z")

# SQL literal syntax is safe here because every possible value is hard-coded.
# PostgreSQL's setweight(tsvector, "char") accepts untyped SQL string literals;
# binding a VARCHAR instead may fail PostgreSQL function overload resolution.
_WEIGHT_SQL = {"A": "'A'", "B": "'B'", "C": "'C'", "D": "'D'"}


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchVectors:
    """Expressions the writer can use in an INSERT/UPDATE statement."""

    document_id: int
    source_id: int
    source_updated_at: datetime
    text_vector: ColumnElement[Any]
    code_vector: ColumnElement[Any]


def _empty_vector() -> ColumnElement[Any]:
    return cast(
        literal("", type_=Text()),
        TSVECTOR()
    )


def _validate_field(field: AnalyzedField) -> None:
    """Validate values even when the caller bypasses analyzer.py."""
    if not isinstance(field, AnalyzedField):
        raise TypeError("field must be an AnalyzedField")
    if not isinstance(field.text, str):
        raise ValueError(f"{field.name}: text must be a string")
    if "\x00" in field.text:
        raise ValueError(f"{field.name}: text contains a NUL character")
    if not isinstance(field.weight, str) or field.weight not in _WEIGHT_SQL:
        raise ValueError(f"{field.name}: weight must be A, B, C, or D")
    if (
        not isinstance(field.search_config, str)
        or len(field.search_config) > 127
        or _CONFIG_NAME.fullmatch(field.search_config) is None
    ):
        raise ValueError(f"{field.name}: invalid PostgreSQL search configuration")


def build_field_vector(field: AnalyzedField) -> ColumnElement[Any]:
    """Create setweight(to_tsvector(config, text), weight) as typed SQL."""
    _validate_field(field)

    if not field.text.strip():
        return _empty_vector()

    # Never interpolate document text or configuration into a SQL string.
    config_arg = cast(literal(field.search_config, type_=Text()), REGCONFIG())
    text_arg = literal(field.text, type_=Text())
    vector = func.to_tsvector(config_arg, text_arg, type_=TSVECTOR())

    # Only a validated, hard-coded A/B/C/D token can become a SQL literal.
    weight_arg = literal_column(_WEIGHT_SQL[field.weight])
    return func.setweight(vector, weight_arg, type_=TSVECTOR())


def combine_vectors(fields: tuple[AnalyzedField, ...]) -> ColumnElement[Any]:
    """Combine weighted field expressions, preserving input order."""
    if not isinstance(fields, tuple):
        raise TypeError("fields must be a tuple of AnalyzedField objects")
    if not fields:
        return _empty_vector()

    combined = build_field_vector(fields[0])
    for field in fields[1:]:
        combined = combined.op("||", return_type=TSVECTOR())(
            build_field_vector(field)
        )
    return combined


def build_search_vectors(
    document: AnalyzedDocument, *, config: IndexerConfig
) -> SearchVectors:
    """Build text/code TSVECTOR expressions for one analyzed document."""
    if not isinstance(document, AnalyzedDocument):
        raise TypeError("document must be an AnalyzedDocument")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")
    if type(document.document_id) is not int or document.document_id <= 0:
        raise ValueError("document_id must be a positive integer")
    if type(document.source_id) is not int or document.source_id <= 0:
        raise ValueError("source_id must be a positive integer")
    if not isinstance(document.source_updated_at, datetime):
        raise ValueError("source_updated_at must be a datetime")

    for fields, expected_config, group in (
        (document.text_fields, config.text_search_config, "text_fields"),
        (document.code_fields, config.code_search_config, "code_fields"),
    ):
        if not isinstance(fields, tuple):
            raise TypeError(f"{group} must be a tuple")
        for field in fields:
            _validate_field(field)
            if field.search_config != expected_config:
                raise ValueError(
                    f"{group}.{field.name}: expected search_config="
                    f"{expected_config!r}, got {field.search_config!r}"
                )

    return SearchVectors(
        document_id=document.document_id,
        source_id=document.source_id,
        source_updated_at=document.source_updated_at,
        text_vector=combine_vectors(document.text_fields),
        code_vector=combine_vectors(document.code_fields),
    )


__all__ = [
    "SearchVectors",
    "build_field_vector",
    "combine_vectors",
    "build_search_vectors",
]
