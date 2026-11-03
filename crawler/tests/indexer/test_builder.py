"""Builder: validation, stale candidate detection and deterministic hashing."""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from indexer.builder import (
    build_index_document,
    calculate_index_hash,
    prepare_index_document,
)
from indexer.errors import (
    IndexDocumentError,
    IndexDocumentTooLargeError,
    StaleIndexSourceError,
)


def test_prepare_normalizes_text_and_metadata(make_document, config):
    document = make_document(
        title="  Cafe\u0301\r\nTutorial  ",
        body="  first\rsecond\r\nthird  ",
        metadata_={
            "headings": ["  Introduction  ", "  ", "Details"],
            "code_blocks": ["    if ready:\r\n        run()\r\n", "  "],
            "tags": ["Python", "python", "AsyncIO", "asyncio", ""],
        },
    )

    result = prepare_index_document(document, config=config)

    assert result.document_id == 10
    assert result.title == "Caf\u00e9\nTutorial"
    assert result.body == "first\nsecond\nthird"
    assert result.headings == ("Introduction", "Details")
    assert result.code_blocks == ("    if ready:\n        run()\n",)
    assert result.tags == ("Python", "AsyncIO")
    assert result.source_updated_at == document.updated_at
    with pytest.raises(FrozenInstanceError):
        result.title = "changed"


def test_prepare_does_not_mutate_crawler_metadata(make_document, config):
    metadata = {
        "headings": ["  One  "],
        "code_blocks": ["  print(1)\r\n"],
        "tags": ["Python", "python"],
    }
    document = make_document(metadata_=metadata)
    prepare_index_document(document, config=config)
    assert metadata == {
        "headings": ["  One  "],
        "code_blocks": ["  print(1)\r\n"],
        "tags": ["Python", "python"],
    }


@pytest.mark.parametrize("bad_id", [0, -1, "10", True])
def test_prepare_rejects_invalid_document_id(make_document, config, bad_id):
    with pytest.raises(IndexDocumentError, match="invalid document ID"):
        prepare_index_document(make_document(id=bad_id), config=config)


def test_prepare_rejects_unavailable_document(make_document, config):
    with pytest.raises(StaleIndexSourceError, match="unavailable"):
        prepare_index_document(make_document(is_available=False), config=config)


@pytest.mark.parametrize(
    ("metadata", "error"),
    [
        (None, "metadata must be a JSON object"),
        ({"tags": "Python"}, "metadata.tags must be a list"),
        ({"headings": [123]}, r"metadata.headings\[0\] must be a string"),
        ({"code_blocks": [None]}, r"metadata.code_blocks\[0\] must be a string"),
    ],
)
def test_prepare_rejects_invalid_metadata(make_document, config, metadata, error):
    with pytest.raises(IndexDocumentError, match=error):
        prepare_index_document(make_document(metadata_=metadata), config=config)


def test_prepare_enforces_total_character_limit(make_document, config):
    small_limit = replace(config, max_document_chars=128)
    document = make_document(body="z" * 500)
    with pytest.raises(IndexDocumentTooLargeError, match="maximum"):
        prepare_index_document(document, config=small_limit)


@pytest.mark.asyncio
async def test_build_reloads_document_and_prepares(make_document, candidate, config):
    document = make_document()
    session = AsyncMock(spec=AsyncSession)
    session.scalar.return_value = document

    result = await build_index_document(session, candidate, config=config)

    session.scalar.assert_awaited_once()
    assert result.document_id == candidate.document_id
    assert result.source_updated_at == candidate.source_updated_at
    assert result.title == "Python Async Tutorial"
    assert "FROM" in str(session.scalar.await_args.args[0]).upper()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["missing", "unavailable", "updated"])
async def test_build_rejects_stale_candidate(
    make_document, candidate, config, reason
):
    session = AsyncMock(spec=AsyncSession)
    if reason == "missing":
        session.scalar.return_value = None
    elif reason == "unavailable":
        session.scalar.return_value = make_document(is_available=False)
    else:
        session.scalar.return_value = make_document(
            updated_at=candidate.source_updated_at + timedelta(seconds=1)
        )

    with pytest.raises(StaleIndexSourceError):
        await build_index_document(session, candidate, config=config)
    session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_propagates_database_failure(candidate, config):
    session = AsyncMock(spec=AsyncSession)
    session.scalar.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await build_index_document(session, candidate, config=config)


def test_hash_is_stable_and_version_prefixed(make_index_document, config):
    document = make_index_document()
    first = calculate_index_hash(document, config=config)
    second = calculate_index_hash(document, config=config)
    assert first == second
    assert first.startswith(config.index_hash_prefix)
    assert re.fullmatch(r"[0-9a-f]{64}", first[len(config.index_hash_prefix):])


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("title", "AsyncIO Reference"),
        ("description", "New description"),
        ("body", "New body"),
        ("headings", ("New Heading",)),
        ("code_blocks", ("await different()",)),
        ("tags", ("async",)),
        ("canonical_url", "https://docs.python.org/3/library/asyncio.html"),
        ("content_hash", "b" * 64),
    ],
)
def test_hash_changes_for_index_relevant_fields(
    make_index_document, config, field, new_value
):
    original = make_index_document()
    changed = replace(original, **{field: new_value})
    assert calculate_index_hash(changed, config=config) != calculate_index_hash(
        original, config=config
    )


def test_hash_changes_when_index_version_changes(make_index_document, config):
    document = make_index_document()
    next_config = replace(config, index_version=config.index_version + 1)
    assert calculate_index_hash(document, config=config) != calculate_index_hash(
        document, config=next_config
    )


def test_hash_excludes_source_timestamp(make_index_document, config):
    original = make_index_document()
    recrawled = replace(
        original, source_updated_at=original.source_updated_at + timedelta(days=1)
    )
    assert calculate_index_hash(original, config=config) == calculate_index_hash(
        recrawled, config=config
    )
