"""Tests for indexer.vector: bound, typed PostgreSQL TSVECTOR expressions.

Run from crawler/:
    poetry run pytest src/indexer/tests/test_vector.py -v

Set TEST_DATABASE_URL to enable the optional PostgreSQL execution test.
The other tests compile SQL expressions without opening a database connection.
"""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError, replace
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql.elements import ColumnElement

from indexer.analyzer import AnalyzedDocument, AnalyzedField, analyze_index_document
from indexer.vector import (
    SearchVectors,
    _empty_vector,
    _validate_field,
    build_field_vector,
    build_search_vectors,
    combine_vectors,
)


def field(
    text: str = "Python Async Tutorial",
    *,
    name: str = "title",
    weight: str = "A",
    search_config: str = "english",
) -> AnalyzedField:
    return AnalyzedField(
        name=name,
        text=text,
        weight=weight,
        search_config=search_config,
    )


def compiled(expression: ColumnElement) -> tuple[str, dict[str, object]]:
    result = expression.compile(dialect=postgresql.dialect())
    return str(result), result.params


def analyzed_document(
    make_index_document, config, **overrides: object
) -> AnalyzedDocument:
    source = analyze_index_document(make_index_document(), config=config)
    return replace(source, **overrides)


def test_empty_vector_is_typed_and_parameterized():
    expression = _empty_vector()
    sql, params = compiled(expression)
    assert isinstance(expression.type, TSVECTOR)
    assert "CAST(" in sql.upper()
    assert "TSVECTOR" in sql.upper()
    assert list(params.values()) == [""]


def test_field_vector_compiles_as_weighted_tsvector():
    expression = build_field_vector(field())
    sql, params = compiled(expression)
    assert isinstance(expression.type, TSVECTOR)
    assert "setweight(" in sql.lower()
    assert "to_tsvector(" in sql.lower()
    assert "REGCONFIG" in sql.upper()
    assert "'A'" in sql
    assert "Python Async Tutorial" not in sql
    assert "Python Async Tutorial" in params.values()
    assert "english" in params.values()


@pytest.mark.parametrize("weight", ["A", "B", "C", "D"])
def test_all_supported_weights_are_compiled_as_literals(weight: str):
    sql, params = compiled(build_field_vector(field(weight=weight)))
    assert f"'{weight}'" in sql
    assert weight not in params.values()


def test_field_values_are_bound_and_not_interpolated_into_sql():
    payload = "Robert'); DROP TABLE search_index; --"
    expression = build_field_vector(field(payload, search_config="pg_catalog.english"))
    sql, params = compiled(expression)
    assert payload not in sql
    assert payload in params.values()
    assert "pg_catalog.english" not in sql
    assert "pg_catalog.english" in params.values()
    assert sql.lower().count("to_tsvector(") == 1


@pytest.mark.parametrize("value", ["", " ", "\n\t  "])
def test_blank_field_yields_empty_vector(value: str):
    sql, params = compiled(build_field_vector(field(value)))
    assert "to_tsvector(" not in sql.lower()
    assert "TSVECTOR" in sql.upper()
    assert list(params.values()) == [""]


@pytest.mark.parametrize("bad", [None, 3, object()])
def test_field_vector_rejects_non_fields(bad: object):
    with pytest.raises(TypeError, match="AnalyzedField"):
        build_field_vector(bad)


@pytest.mark.parametrize("bad", [None, 7, ["hello"]])
def test_field_vector_rejects_non_string_text(bad: object):
    with pytest.raises(ValueError, match="text must be a string"):
        build_field_vector(field(bad))


def test_field_vector_rejects_nul():
    with pytest.raises(ValueError, match="NUL"):
        build_field_vector(field("hello\x00world"))


@pytest.mark.parametrize("bad", ["Z", "a", "", "AA", 0, None])
def test_field_vector_rejects_invalid_weights(bad: object):
    with pytest.raises(ValueError, match="weight"):
        build_field_vector(field(weight=bad))


@pytest.mark.parametrize(
    "config_name",
    ["english", "simple", "pg_catalog.english", "search_custom", "_custom_1"],
)
def test_field_vector_accepts_configuration_name_syntax(config_name: str):
    sql, params = compiled(build_field_vector(field(search_config=config_name)))
    assert "REGCONFIG" in sql.upper()
    assert config_name in params.values()


@pytest.mark.parametrize(
    "bad",
    [
        None,
        100,
        "",
        "bad config",
        "3english",
        "english; DROP TABLE documents",
        "schema..config",
        "one.two.three",
        "x" * 128,
        '"english"',
    ],
)
def test_field_vector_rejects_invalid_config_names(bad: object):
    with pytest.raises(ValueError, match="configuration"):
        build_field_vector(field(search_config=bad))


def test_combining_zero_fields_produces_empty_tsvector():
    sql, params = compiled(combine_vectors(()))
    assert "to_tsvector(" not in sql.lower()
    assert "TSVECTOR" in sql.upper()
    assert list(params.values()) == [""]


def test_combining_one_field_has_no_concatenation():
    sql, params = compiled(combine_vectors((field(),)))
    assert sql.count(" || ") == 0
    assert sql.lower().count("to_tsvector(") == 1
    assert "Python Async Tutorial" in params.values()


def test_combining_three_fields_preserves_order_and_weights():
    fields = (
        field("unique_title", weight="A"),
        field("unique_heading", name="heading", weight="B"),
        field("unique_body", name="body", weight="C"),
    )
    expression = combine_vectors(fields)
    sql, params = compiled(expression)
    assert isinstance(expression.type, TSVECTOR)
    assert sql.count(" || ") == 2
    assert sql.lower().count("to_tsvector(") == 3
    assert "'A'" in sql and "'B'" in sql and "'C'" in sql
    values = list(params.values())
    assert values.index("unique_title") < values.index("unique_heading")
    assert values.index("unique_heading") < values.index("unique_body")


def test_combination_keeps_blank_field_as_valid_empty_expression():
    sql, params = compiled(combine_vectors((field(" "), field("real text"))))
    assert " || " in sql
    assert sql.lower().count("to_tsvector(") == 1
    assert "real text" in params.values()


@pytest.mark.parametrize("bad", [[], {}, None, "abc"])
def test_combination_rejects_non_tuple(bad: object):
    with pytest.raises(TypeError, match="tuple"):
        combine_vectors(bad)


def test_combination_rejects_invalid_later_fields():
    with pytest.raises(TypeError, match="AnalyzedField"):
        combine_vectors((field(), object()))


def test_search_vectors_from_real_analyzer_output(make_index_document, config):
    document = analyzed_document(make_index_document, config)
    vectors = build_search_vectors(document, config=config)

    assert isinstance(vectors, SearchVectors)
    assert vectors.document_id == document.document_id
    assert vectors.source_id == document.source_id
    assert vectors.source_updated_at == document.source_updated_at
    assert isinstance(vectors.text_vector.type, TSVECTOR)
    assert isinstance(vectors.code_vector.type, TSVECTOR)

    text_sql, text_params = compiled(vectors.text_vector)
    code_sql, code_params = compiled(vectors.code_vector)
    assert text_sql.lower().count("to_tsvector(") == len(document.text_fields)
    assert code_sql.lower().count("to_tsvector(") == len(document.code_fields)
    assert text_sql.count(" || ") == len(document.text_fields) - 1
    assert code_sql.count(" || ") == len(document.code_fields) - 1
    assert set(text_params.values()).issuperset({"english", document.text_fields[0].text})
    assert set(code_params.values()).issuperset({"simple", document.code_fields[0].text})


def test_search_vectors_does_not_mutate_analyzer_output(make_index_document, config):
    document = analyzed_document(make_index_document, config)
    original_text = document.text_fields
    original_code = document.code_fields
    build_search_vectors(document, config=config)
    assert document.text_fields == original_text
    assert document.code_fields == original_code


def test_search_vectors_result_is_frozen(make_index_document, config):
    result = build_search_vectors(
        analyzed_document(make_index_document, config), config=config
    )
    with pytest.raises(FrozenInstanceError):
        result.document_id = 100


def test_search_vectors_are_deterministic(make_index_document, config):
    document = analyzed_document(make_index_document, config)
    first = build_search_vectors(document, config=config)
    second = build_search_vectors(document, config=config)
    for attr in ("text_vector", "code_vector"):
        assert compiled(getattr(first, attr)) == compiled(getattr(second, attr))


def test_search_vectors_allow_empty_field_groups(make_index_document, config):
    document = analyzed_document(
        make_index_document, config, text_fields=(), code_fields=()
    )
    result = build_search_vectors(document, config=config)
    for expression in (result.text_vector, result.code_vector):
        sql, params = compiled(expression)
        assert "TSVECTOR" in sql.upper()
        assert list(params.values()) == [""]


@pytest.mark.parametrize("bad", [None, object(), "not an analyzed document"])
def test_search_vectors_reject_invalid_document_type(config, bad):
    with pytest.raises(TypeError, match="AnalyzedDocument"):
        build_search_vectors(bad, config=config)


def test_search_vectors_reject_invalid_config_type(make_index_document, config):
    document = analyzed_document(make_index_document, config)
    with pytest.raises(TypeError, match="IndexerConfig"):
        build_search_vectors(document, config=None)


@pytest.mark.parametrize("attr", ["document_id", "source_id"])
@pytest.mark.parametrize("bad", [0, -1, True, "5"])
def test_search_vectors_reject_invalid_ids(make_index_document, config, attr, bad):
    document = analyzed_document(make_index_document, config, **{attr: bad})
    with pytest.raises(ValueError, match=attr):
        build_search_vectors(document, config=config)


@pytest.mark.parametrize("bad", [None, "2026-10-27", 1])
def test_search_vectors_reject_invalid_timestamp(make_index_document, config, bad):
    document = analyzed_document(make_index_document, config, source_updated_at=bad)
    with pytest.raises(ValueError, match="source_updated_at"):
        build_search_vectors(document, config=config)


@pytest.mark.parametrize(
    ("group", "search_config"),
    [("text_fields", "simple"), ("code_fields", "english")],
)
def test_search_vectors_reject_config_mismatch(
    make_index_document, config, group, search_config
):
    document = analyzed_document(make_index_document, config)
    replaced_fields = (replace(getattr(document, group)[0], search_config=search_config),)
    mismatched = replace(document, **{group: replaced_fields})
    with pytest.raises(ValueError, match="expected search_config"):
        build_search_vectors(mismatched, config=config)


@pytest.mark.parametrize("group", ["text_fields", "code_fields"])
def test_search_vectors_reject_non_tuple_field_group(make_index_document, config, group):
    document = analyzed_document(make_index_document, config, **{group: []})
    with pytest.raises(TypeError, match="tuple"):
        build_search_vectors(document, config=config)


@pytest.mark.asyncio
async def test_postgresql_executes_weighted_text_and_code_vectors(config):
    """Optional end-to-end expression execution; requires a test PostgreSQL DB."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to enable PostgreSQL execution")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.skip("TEST_DATABASE_URL must use the asyncpg SQLAlchemy driver")

    from sqlalchemy.ext.asyncio import create_async_engine

    document = AnalyzedDocument(
        document_id=10,
        source_id=2,
        source_updated_at=datetime(2026, 10, 27),
        text_fields=(field("Running basics", weight="A"),),
        code_fields=(
            field("running", name="code_blocks", weight="B", search_config="simple"),
        ),
    )
    result = build_search_vectors(document, config=config)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(
                        result.text_vector.label("text_vector"),
                        result.code_vector.label("code_vector"),
                    )
                )
            ).one()
        # English stemming versus 'simple' processing, plus weights.
        assert "'run':1A" in str(row.text_vector)
        assert "'running':1B" in str(row.code_vector)
    finally:
        await engine.dispose()
