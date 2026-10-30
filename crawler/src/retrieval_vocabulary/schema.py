
"""Validated data contracts for the Developer's Eye vocabulary engine.

These schemas represent vocabulary processing inputs and results.
They are not SQLAlchemy database models.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


MAX_TERM_CHARS = 128


class VocabularySchema(BaseModel):
    """Base configuration for immutable vocabulary data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class VocabularyAction(StrEnum):
    """Operations performed on indexed documents."""

    SYNC = "sync"
    REMOVE = "remove"


class VocabularyStatus(StrEnum):
    """Possible vocabulary processing outcomes."""

    SYNCED = "synced"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    STALE = "stale"
    SKIPPED = "skipped"
    FAILED = "failed"


class VocabularyCandidate(VocabularySchema):
    """A document selected for vocabulary processing.

    indexed_hash identifies the expected search-index revision.
    Removal candidates do not require a revision.
    """

    document_id: int = Field(gt=0)
    action: VocabularyAction
    indexed_hash: str | None = None

    @model_validator(mode="after")
    def validate_action(self) -> VocabularyCandidate:
        if self.action == VocabularyAction.SYNC:
            if not self.indexed_hash:
                raise ValueError(
                    "SYNC candidates require indexed_hash"
                )

        if self.action == VocabularyAction.REMOVE:
            if self.indexed_hash is not None:
                raise ValueError(
                    "REMOVE candidates must not carry indexed_hash"
                )

        return self


class VocabularyDocument(VocabularySchema):
    """Content snapshot of a successfully indexed document."""

    document_id: int = Field(gt=0)
    indexed_hash: str = Field(min_length=1)

    title: str = ""
    description: str = ""
    body: str = ""

    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class VocabularyTermSet(VocabularySchema):
    """Unique normalized terms extracted from one document.

    Each term contributes at most one to document frequency.
    """

    document_id: int = Field(gt=0)
    indexed_hash: str = Field(min_length=1)
    terms: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("terms")
    @classmethod
    def validate_terms(
        cls,
        terms: frozenset[str],
    ) -> frozenset[str]:
        for term in terms:
            if not term or len(term) > MAX_TERM_CHARS:
                raise ValueError(
                    "term length must be between 1 and 128"
                )

            if term != term.strip():
                raise ValueError(
                    "terms must not contain surrounding whitespace"
                )

            if any(char.isspace() for char in term):
                raise ValueError(
                    "terms must not contain whitespace"
                )

            if term != term.casefold():
                raise ValueError(
                    "terms must be case-normalized"
                )

        return terms


class TermFrequency(VocabularySchema):
    """Absolute number of indexed documents containing a term."""

    term: str = Field(min_length=1, max_length=MAX_TERM_CHARS)
    document_frequency: int = Field(ge=0)

    @field_validator("term")
    @classmethod
    def validate_term(cls, term: str) -> str:
        if term != term.strip() or term != term.casefold():
            raise ValueError(
                "term must be trimmed and case-normalized"
            )

        if any(char.isspace() for char in term):
            raise ValueError(
                "term must not contain whitespace"
            )

        return term


class VocabularyResult(VocabularySchema):
    """Outcome of processing one indexed document."""

    document_id: int = Field(gt=0)
    status: VocabularyStatus

    added_terms: int = Field(default=0, ge=0)
    removed_terms: int = Field(default=0, ge=0)
    retained_terms: int = Field(default=0, ge=0)

    error: str | None = None


class VocabularyBatchReport(VocabularySchema):
    """Statistics produced by one vocabulary worker batch."""

    selected: int = Field(default=0, ge=0)
    synced: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)
    removed: int = Field(default=0, ge=0)
    stale: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)

    elapsed_seconds: float = Field(default=0.0, ge=0)
