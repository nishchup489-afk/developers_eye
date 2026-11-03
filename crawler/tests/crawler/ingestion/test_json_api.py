import json

import pytest

from crawler.parser.api import parse_json_api
from crawler.parser.api import json_parser as api
from crawler.parser.errors import MalformedContentError


def parse(value, options=None):
    return parse_json_api(url="https://example.com/api/items", content=json.dumps(value).encode(),
        content_type="application/json", options=options)


@pytest.mark.parametrize("wrap", [lambda x: [x], lambda x: x, lambda x: {"items": [x]}])
def test_default_array_single_object_and_items_container(wrap):
    result = parse(wrap({"url": "/docs/a", "title": "Python", "body": "Useful Python documentation.", "author": "Nish", "published_at": "2026-10-20T10:00:00Z"}))
    document, = result.documents
    assert document.url == "https://example.com/docs/a"
    assert document.author == "Nish"
    assert document.published_at.utcoffset().total_seconds() == 0
    assert document.metadata["ingestion_format"] == "json_api"


def test_custom_nested_fields_html_and_body_pagination():
    result = parse({"data": {"results": [{"html_url": "/docs/a", "name": "Guide", "content": "<p>Useful guide.</p><script>secret()</script>", "user": {"login": "Nish"}}]}, "paging": {"next": "?page=2"}},
        {"items_path": "data.results", "next_path": "paging.next", "body_format": "html",
         "fields": {"url": "html_url", "title": "name", "body": "content", "author": "user.login"}})
    assert result.documents[0].author == "Nish"
    assert result.documents[0].body == "Useful guide."
    assert result.discovered_links[-1].url == "https://example.com/api/items?page=2"
    assert result.discovered_links[-1].kind == "api"


def test_invalid_entries_duplicate_urls_and_field_types():
    result = parse([None, 2, {"url": "javascript:alert(1)"}, {"url": "/docs/a", "body": "First"},
        {"url": "/docs/a", "body": "Second"}, {"url": "/docs/b", "body": {}, "author": ["Nish"]}])
    assert [d.url for d in result.documents] == ["https://example.com/docs/a", "https://example.com/docs/b"]
    assert result.documents[0].body == "First"
    assert result.documents[1].body == ""
    assert result.documents[1].author is None


@pytest.mark.parametrize("options", [{"items_path": "missing"}, {"items_path": "data.records"}])
def test_missing_items_path_is_not_a_successful_empty_import(options):
    with pytest.raises(MalformedContentError): parse({"data": {}}, options)


@pytest.mark.parametrize("options", [{"unknown": 1}, {"fields": {"body": None}}, {"fields": {"secret": "value"}},
    {"items_path": 1}, {"next_path": ""}, {"body_format": "markdown"}, {"body_format": []}])
def test_invalid_mapping_is_rejected(options):
    with pytest.raises(ValueError): parse([], options)


@pytest.mark.parametrize("content", [b'{"items": [], "items": []}', b'{"value": NaN}', b'{"value": 1e400}', b'{bad}', b'\xff'])
def test_invalid_json_and_ambiguous_objects_are_rejected(content):
    with pytest.raises(MalformedContentError):
        parse_json_api(url="https://example.com/api", content=content, content_type="application/json")


def test_json_limits_apply_before_filtering(monkeypatch):
    monkeypatch.setattr(api, "MAX_JSON_ENTRIES", 1)
    with pytest.raises(MalformedContentError, match="Too many"):
        parse([{}, {}])
    monkeypatch.setattr(api, "MAX_JSON_BYTES", 1)
    with pytest.raises(MalformedContentError, match="oversized"):
        parse([])


def test_path_lookup_can_select_array_element_and_empty_collection_is_valid():
    assert parse({"data": [[]]}, {"items_path": "data.0"}).documents == ()
    assert parse({"url": "/docs/a", "body": "Text"}, {"items_path": ""}).documents[0].body == "Text"
