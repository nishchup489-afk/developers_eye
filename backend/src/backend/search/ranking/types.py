
"""Data contracts for the BM25 ranking engine.

Defines ranking configuration, corpus statistics, document statistics,
and query-specific ranking inputs.

No database access, scoring calculations, or ranking orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Mapping


def _check_count(name: str, value: int) -> None:
    """Validate a non-negative integer."""
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _check_number(name: str, value: float) -> None:
    """Validate a finite numeric value, excluding booleans."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number")


def _freeze_frequencies(
    values: Mapping[str, int],
    *,
    name: str,
    maximum: int | None = None,
) -> Mapping[str, int]:
    """Validate and freeze a term-frequency mapping."""
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping")

    result: dict[str, int] = {}

    for term, frequency in values.items():
        if not isinstance(term, str) or not term.strip():
            raise ValueError(f"{name} contains an invalid term")

        _check_count(f"{name}[{term!r}]", frequency)

        if maximum is not None and frequency > maximum:
            raise ValueError(
                f"{name}[{term!r}] exceeds the allowed maximum"
            )

        result[term] = frequency

    return MappingProxyType(result)


@dataclass(frozen=True, slots=True, kw_only=True)
class BM25Parameters:
    """Parameters controlling BM25 saturation and length normalization."""

    k1: float = 1.2
    b: float = 0.75

    def __post_init__(self) -> None:
        _check_number("k1", self.k1)
        _check_number("b", self.b)

        if self.k1 <= 0:
            raise ValueError("k1 must be positive")

        if not 0 <= self.b <= 1:
            raise ValueError("b must be between 0 and 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class RankingConfig:
    """Configuration for combining text and code BM25 scores."""

    bm25: BM25Parameters = field(
        default_factory=BM25Parameters
    )

    text_weight: float = 1.0
    code_weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.bm25, BM25Parameters):
            raise TypeError("bm25 must be BM25Parameters")

        for name in ("text_weight", "code_weight"):
            value = getattr(self, name)
            _check_number(name, value)

            if value < 0:
                raise ValueError(f"{name} cannot be negative")

        if self.text_weight == 0 and self.code_weight == 0:
            raise ValueError(
                "At least one ranking channel must have positive weight"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusStatistics:
    """Collection-wide statistics for one search channel.

    document_count: N in the BM25 formula.
    average_document_length: avgdl in the BM25 formula.
    """

    document_count: int
    average_document_length: float

    def __post_init__(self) -> None:
        _check_count("document_count", self.document_count)
        _check_number(
            "average_document_length",
            self.average_document_length,
        )

        if self.average_document_length < 0:
            raise ValueError(
                "average_document_length cannot be negative"
            )

        if (
            self.document_count == 0
            and self.average_document_length != 0
        ):
            raise ValueError(
                "An empty corpus must have zero average length"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentStatistics:
    """BM25 statistics for one indexed document in one channel.

    document_length: number of indexed tokens.
    term_frequencies: query lexeme -> occurrences in this document.
    """

    document_id: int
    document_length: int
    term_frequencies: Mapping[str, int]

    def __post_init__(self) -> None:
        if type(self.document_id) is not int or self.document_id <= 0:
            raise ValueError("document_id must be a positive integer")

        _check_count("document_length", self.document_length)

        frozen = _freeze_frequencies(
            self.term_frequencies,
            name="term_frequencies",
            maximum=self.document_length,
        )

        object.__setattr__(self, "term_frequencies", frozen)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChannelStatistics:
    """Query-specific BM25 statistics for one retrieval channel.

    corpus: global corpus statistics.
    document_frequencies: query lexeme -> number of corpus documents
        containing that lexeme.
    documents: document ID -> document-specific statistics.

    Only candidate documents need to be included in documents.
    """

    corpus: CorpusStatistics
    document_frequencies: Mapping[str, int]
    documents: Mapping[int, DocumentStatistics]

    def __post_init__(self) -> None:
        if not isinstance(self.corpus, CorpusStatistics):
            raise TypeError("corpus must be CorpusStatistics")

        frequencies = _freeze_frequencies(
            self.document_frequencies,
            name="document_frequencies",
            maximum=self.corpus.document_count,
        )

        if not isinstance(self.documents, Mapping):
            raise TypeError("documents must be a mapping")

        documents: dict[int, DocumentStatistics] = {}

        for document_id, stats in self.documents.items():
            if not isinstance(stats, DocumentStatistics):
                raise TypeError(
                    "documents must contain DocumentStatistics"
                )

            if type(document_id) is not int or document_id <= 0:
                raise ValueError("Invalid document ID")

            if document_id != stats.document_id:
                raise ValueError(
                    "Document mapping key does not match document_id"
                )

            documents[document_id] = stats

        if len(documents) > self.corpus.document_count:
            raise ValueError(
                "Candidate count cannot exceed corpus document count"
            )

        if self.corpus.average_document_length == 0:
            if any(doc.document_length > 0 for doc in documents.values()):
                raise ValueError(
                    "A zero-average corpus cannot contain "
                    "a non-empty document"
                )

        object.__setattr__(
            self, "document_frequencies", frequencies
        )
        object.__setattr__(
            self, "documents", MappingProxyType(documents)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RankingStatistics:
    """BM25 statistics for the text and code search channels."""

    text: ChannelStatistics
    code: ChannelStatistics

    def __post_init__(self) -> None:
        if not isinstance(self.text, ChannelStatistics):
            raise TypeError("text must be ChannelStatistics")

        if not isinstance(self.code, ChannelStatistics):
            raise TypeError("code must be ChannelStatistics")
