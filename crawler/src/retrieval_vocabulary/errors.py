
"""Exceptions for the Developer's Eye retrieval vocabulary engine."""


class VocabularyError(Exception):
    """Base exception for vocabulary engine failures."""


class VocabularyConfigError(VocabularyError, ValueError):
    """Invalid worker configuration or environment settings."""


class VocabularyValidationError(VocabularyError, ValueError):
    """Invalid vocabulary input, token, or document data."""


class VocabularyBuildError(VocabularyError):
    """Failed to construct vocabulary terms from indexed content."""


class VocabularySelectionError(VocabularyError):
    """Failed to select documents requiring vocabulary processing."""


class VocabularyWriteError(VocabularyError):
    """Failed to persist vocabulary changes."""


class VocabularyStateError(VocabularyError):
    """Vocabulary state violates an expected consistency invariant."""
