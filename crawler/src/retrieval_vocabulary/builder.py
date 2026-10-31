
"""Build vocabulary documents from successfully indexed content.

The builder:
- Accepts SYNC candidates from the selector.
- Loads document content through repository.py.
- Rejects missing or stale indexed revisions.
- Validates and constructs VocabularyDocument objects.

No SQL queries or database writes are performed here.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from retrieval_vocabulary.errors import (
    VocabularyBuildError,
    VocabularyValidationError,
)
from retrieval_vocabulary.repository import fetch_indexed_document
from retrieval_vocabulary.schema import (
    VocabularyAction,
    VocabularyCandidate,
    VocabularyDocument,
)


def _text(value: object, field: str) -> str:
    """Convert nullable text fields to validated strings."""

    if value is None:
        return ""

    if not isinstance(value, str):
        raise VocabularyBuildError(
            f"{field} must be a string or None"
        )

    return value


def _text_tuple(
    value: object,
    field: str,
) -> tuple[str, ...]:
    """Validate arrays of text without silently dropping entries."""

    if value is None:
        return ()

    if not isinstance(value, (list, tuple)):
        raise VocabularyBuildError(
            f"{field} must be a list or tuple of strings"
        )

    if any(not isinstance(item, str) for item in value):
        raise VocabularyBuildError(
            f"{field} contains non-string entries"
        )

    return tuple(value)


async def build_vocabulary_document(
    candidate: VocabularyCandidate,
    session: AsyncSession,
) -> VocabularyDocument | None:
    """Build a validated vocabulary document.

    Returns None if the indexed revision is no longer current,
    or the document has disappeared or become unavailable.

    Raises VocabularyBuildError for malformed stored content.

    This function is read-only. The writer must revalidate the
    indexed revision before committing vocabulary changes.
    """

    if not isinstance(candidate, VocabularyCandidate):
        raise TypeError(
            "candidate must be a VocabularyCandidate"
        )

    if candidate.action != VocabularyAction.SYNC:
        raise VocabularyValidationError(
            "builder only accepts SYNC candidates"
        )

    if not candidate.indexed_hash:
        raise VocabularyValidationError(
            "SYNC candidate requires indexed_hash"
        )

    source = await fetch_indexed_document(
        session,
        document_id=candidate.document_id,
        indexed_hash=candidate.indexed_hash,
    )

    if source is None:
        return None

    try:
        return VocabularyDocument(
            document_id=source["document_id"],
            indexed_hash=source["indexed_hash"],
            title=_text(source["title"], "title"),
            description=_text(
                source["description"], "description"
            ),
            body=_text(source["body"], "body"),
            headings=_text_tuple(
                source["headings"], "headings"
            ),
            code_blocks=_text_tuple(
                source["code_blocks"], "code_blocks"
            ),
            tags=_text_tuple(source["tags"], "tags"),
        )

    except (ValidationError, ValueError, TypeError) as exc:
        raise VocabularyBuildError(
            f"Invalid vocabulary document "
            f"{candidate.document_id}: {exc}"
        ) from exc
