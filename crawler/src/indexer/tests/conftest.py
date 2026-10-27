"""Shared fixtures for Developer's Eye indexer tests.

Run from crawler/: poetry run pytest src/indexer/tests -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Support both `poetry install` and running tests against the source checkout.
SRC = Path(__file__).resolve().parents[2]
if SRC.name != "src":
    SRC = SRC / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.models.documents import Document
from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate, IndexDocument

SOURCE_UPDATED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
CONTENT_HASH = "a" * 64


@pytest.fixture
def config() -> IndexerConfig:
    return IndexerConfig(
        batch_size=10,
        index_version=1,
        max_document_chars=100_000,
        text_search_config="english",
        code_search_config="simple",
    )


@pytest.fixture
def make_document():
    def factory(**overrides: object) -> Document:
        values: dict[str, object] = {
            "id": 10,
            "source_id": 2,
            "canonical_url": "https://docs.python.org/3/tutorial/",
            "document_type": "documentation",
            "title": "Python Async Tutorial",
            "description": "Learn asynchronous Python",
            "body": "Use async and await in Python.",
            "metadata_": {
                "headings": ["Async Functions", "Event Loop"],
                "code_blocks": ["async def main():\n    await run()"],
                "tags": ["Python", "asyncio"],
            },
            "content_hash": CONTENT_HASH,
            "updated_at": SOURCE_UPDATED_AT,
            "is_available": True,
        }
        values.update(overrides)
        return Document(**values)

    return factory


@pytest.fixture
def make_index_document():
    def factory(**overrides: object) -> IndexDocument:
        values: dict[str, object] = {
            "document_id": 10,
            "source_id": 2,
            "canonical_url": "https://docs.python.org/3/tutorial/",
            "document_type": "documentation",
            "title": "Python Async Tutorial",
            "description": "Learn asynchronous Python",
            "body": "Use async and await in Python.",
            "headings": ("Async Functions", "Event Loop"),
            "code_blocks": ("async def main():\n    await run()",),
            "tags": ("Python", "asyncio"),
            "content_hash": CONTENT_HASH,
            "source_updated_at": SOURCE_UPDATED_AT,
        }
        values.update(overrides)
        return IndexDocument(**values)

    return factory


@pytest.fixture
def candidate() -> IndexCandidate:
    return IndexCandidate(document_id=10, source_updated_at=SOURCE_UPDATED_AT)
