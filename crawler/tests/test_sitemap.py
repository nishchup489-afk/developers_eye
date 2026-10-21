"""XML sitemap parser tests; no network or PostgreSQL required."""

import pytest
import gzip
from crawler.parser import sitemap

from crawler.parser.errors import MalformedContentError
from crawler.parser.sitemap import parse_sitemap


def test_namespaced_urlset():
    result = parse_sitemap(b"""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/docs/python</loc></url>
        <url><loc>https://example.com/docs/python</loc></url>
        <url><loc>https://example.com/docs/css</loc></url>
    </urlset>""")
    assert result.page_urls == (
        "https://example.com/docs/python",
        "https://example.com/docs/css",
    )
    assert result.sitemap_urls == ()


def test_sitemap_index():
    result = parse_sitemap(b"""<sitemapindex>
        <sitemap><loc>https://example.com/docs-1.xml</loc></sitemap>
    </sitemapindex>""")
    assert result.page_urls == ()
    assert result.sitemap_urls == ("https://example.com/docs-1.xml",)


def test_unsafe_urls_ignored():
    result = parse_sitemap(b"""<urlset>
        <url><loc>file:///etc/passwd</loc></url>
        <url><loc>https://example.com/safe</loc></url>
    </urlset>""")
    assert result.page_urls == ("https://example.com/safe",)


def test_malformed_xml_rejected():
    with pytest.raises(MalformedContentError):
        parse_sitemap(b"<urlset><url>")


def test_entity_expansion_rejected():
    with pytest.raises(MalformedContentError):
        parse_sitemap(
            b'<!DOCTYPE urlset [<!ENTITY x "oops">]>'
            b'<urlset><url><loc>&x;</loc></url></urlset>'
        )


def test_non_sitemap_root_rejected():
    with pytest.raises(MalformedContentError):
        parse_sitemap(b"<rss></rss>")


def test_entry_limit_counts_duplicates_and_invalid_entries(monkeypatch):
    monkeypatch.setattr(sitemap, "MAX_ENTRIES", 2)
    repeated = b"<url><loc>https://example.com/a</loc></url>"
    assert len(parse_sitemap(b"<urlset>" + repeated * 2 + b"</urlset>").page_urls) == 1
    for entry in [repeated, b"<url><loc>/invalid</loc></url>"]:
        with pytest.raises(MalformedContentError, match="Too many"):
            parse_sitemap(b"<urlset>" + entry * 3 + b"</urlset>")


def test_gzip_is_bounded_after_decompression(monkeypatch):
    xml = b"<urlset><url><loc>https://example.com/a</loc></url></urlset>"
    assert parse_sitemap(gzip.compress(xml)).page_urls == ("https://example.com/a",)
    monkeypatch.setattr(sitemap, "MAX_XML_BYTES", 100)
    with pytest.raises(MalformedContentError, match="Decompressed"):
        parse_sitemap(gzip.compress(b"<urlset>" + b" " * 200 + b"</urlset>"))


@pytest.mark.parametrize("xml", [b'<!DOCTYPE urlset><urlset/>', b'<urlset xmlns="urn:unrelated"/>', b'\x1f\x8btruncated'])
def test_invalid_documents_rejected(xml):
    with pytest.raises(MalformedContentError):
        parse_sitemap(xml)


def test_extension_namespace_does_not_supply_page_location():
    result = parse_sitemap(b'<urlset xmlns:image="urn:image"><url><image:loc>https://example.com/image</image:loc></url></urlset>')
    assert result.page_urls == ()


def test_corrupt_deflate_is_reported_as_malformed_xml():
    compressed = gzip.compress(b"<urlset/>")
    corrupt = compressed[:10] + b"\x06" + compressed[11:]
    with pytest.raises(MalformedContentError, match="gzip"):
        parse_sitemap(corrupt)
