"""Analyzer: immutable weighted fields; no database and no TSVECTOR building."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from indexer.analyzer import (
    AnalyzedDocument,
    AnalyzedField,
    _field,
    _join_items,
    analyze_index_document,
)
from indexer.errors import IndexDocumentError


def test_analyzer_separates_text_and_code(make_index_document, config):
    document = make_index_document()
    result = analyze_index_document(document, config=config)

    assert isinstance(result, AnalyzedDocument)
    assert result.document_id == document.document_id
    assert result.source_id == document.source_id
    assert result.source_updated_at == document.source_updated_at

    assert [(f.name, f.weight) for f in result.text_fields] == [
        ("title", "A"),
        ("tags", "A"),
        ("headings", "B"),
        ("description", "B"),
        ("body", "C"),
    ]
    assert [(f.name, f.weight) for f in result.code_fields] == [
        ("tags", "A"),
        ("title", "A"),
        ("code_blocks", "B"),
        ("headings", "B"),
        ("canonical_url", "D"),
    ]
    assert all(f.search_config == "english" for f in result.text_fields)
    assert all(f.search_config == "simple" for f in result.code_fields)


def test_analyzer_preserves_boundaries_and_code_whitespace(
    make_index_document, config
):
    document = make_index_document(
        headings=("Setup", "Installation"),
        code_blocks=("    def run():\n        pass", "    x = 1"),
        tags=("Python", "AsyncIO"),
    )
    result = analyze_index_document(document, config=config)
    text = {f.name: f.text for f in result.text_fields}
    code = {f.name: f.text for f in result.code_fields}

    assert text["headings"] == "Setup\n\nInstallation"
    assert text["tags"] == "Python\n\nAsyncIO"
    assert code["code_blocks"] == "    def run():\n        pass\n\n    x = 1"
    assert code["title"] == document.title


def test_analyzer_skips_optional_blank_fields(make_index_document, config):
    document = make_index_document(
        description=" ", headings=(), tags=(), code_blocks=()
    )
    result = analyze_index_document(document, config=config)
    assert [f.name for f in result.text_fields] == ["title", "body"]
    assert [f.name for f in result.code_fields] == ["title", "canonical_url"]


def test_analyzer_output_is_frozen(make_index_document, config):
    result = analyze_index_document(make_index_document(), config=config)
    assert isinstance(result.text_fields, tuple)
    assert isinstance(result.code_fields, tuple)
    assert isinstance(result.text_fields[0], AnalyzedField)
    with pytest.raises(FrozenInstanceError):
        result.document_id = 99
    with pytest.raises(FrozenInstanceError):
        result.text_fields[0].weight = "D"


def test_analyzer_is_deterministic(make_index_document, config):
    document = make_index_document()
    assert analyze_index_document(document, config=config) == analyze_index_document(
        document, config=config
    )


@pytest.mark.parametrize("wrong_value", [None, 123, ["text"]])
def test_field_rejects_non_strings(wrong_value):
    with pytest.raises(IndexDocumentError, match="title must be a string"):
        _field(
            name="title",
            text=wrong_value,
            weight="A",
            search_config="english",
            document_id=10,
        )


def test_field_rejects_nul():
    with pytest.raises(IndexDocumentError, match="NUL"):
        _field(
            name="body",
            text="hello\x00world",
            weight="C",
            search_config="english",
            document_id=10,
        )


def test_field_returns_none_for_whitespace_only():
    assert _field(
        name="description", text=" \n\t ", weight="B",
        search_config="english", document_id=10,
    ) is None


def test_join_items_does_not_change_indentation():
    assert _join_items(("  a", "", "  b"), name="code_blocks", document_id=10) == (
        "  a\n\n  b"
    )


def test_join_items_rejects_invalid_container_or_elements():
    for value in (["a"], ("ok", None), 3):
        with pytest.raises(IndexDocumentError, match="tuple of strings"):
            _join_items(value, name="code_blocks", document_id=10)


def test_analyzer_rejects_wrong_argument_types(make_index_document, config):
    with pytest.raises(TypeError, match="IndexDocument"):
        analyze_index_document(object(), config=config)
    with pytest.raises(TypeError, match="IndexerConfig"):
        analyze_index_document(make_index_document(), config=object())
