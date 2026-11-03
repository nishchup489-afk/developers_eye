from datetime import datetime, timezone

import pytest

from crawler.parser.feeds import parser as feeds
from crawler.parser.errors import MalformedContentError
from crawler.parser.feeds import parse_feed
from crawler.parser.structured import parse_record_date


def parse(xml):
    return parse_feed(url="https://example.com/feed.xml", content=xml, content_type="application/xml")


def test_rss_content_extensions_dates_and_invalid_records():
    result = parse(b'''<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
    <item><title>Python update</title><link>/docs/new</link><description>Short summary</description>
    <content:encoded><![CDATA[<p>Full Python documentation.</p><script>secret()</script>]]></content:encoded>
    <dc:creator>Nish</dc:creator><pubDate>Tue, 20 Oct 2026 10:00:00 +0000</pubDate></item>
    <item><link>javascript:bad()</link></item><item><guid isPermaLink="false">opaque-id</guid></item>
    <item><link>/docs/new</link><description>Duplicate</description></item></channel></rss>''')
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.url == "https://example.com/docs/new"
    assert document.title == "Python update"
    assert document.body == "Full Python documentation."
    assert document.description == "Short summary"
    assert document.author == "Nish"
    assert document.published_at == datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def test_atom_bases_text_html_xhtml_author_and_pagination():
    result = parse(b'''<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://example.com/docs/">
    <author><name>Nish</name></author><link rel="next" href="../feed.xml?page=2"/>
    <entry xml:base="python/"><title>Use &lt;button&gt;</title><link href="new"/><updated>2026-10-20T10:00:00Z</updated>
    <content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Useful Python content.</p><script>secret()</script></div></content></entry>
    <entry><id>urn:uuid:123</id><summary>Opaque identity</summary></entry></feed>''')
    document, = result.documents
    assert document.url == "https://example.com/docs/python/new"
    assert document.title == "Use <button>"
    assert document.body == "Useful Python content."
    assert document.author == "Nish"
    assert result.discovered_links[-1].url == "https://example.com/feed.xml?page=2"
    assert result.discovered_links[-1].kind == "rss"


@pytest.mark.parametrize("xml", [b"<rss/>", b"<html/>", b"<rss>", b'<!DOCTYPE rss><rss><channel/></rss>', b""])
def test_bad_feeds_fail(xml):
    with pytest.raises(MalformedContentError): parse(xml)


def test_feed_limits_count_all_items(monkeypatch):
    monkeypatch.setattr(feeds, "MAX_FEED_ENTRIES", 1)
    with pytest.raises(MalformedContentError, match="Too many"):
        parse(b"<rss><channel><item/><item/></channel></rss>")
    monkeypatch.setattr(feeds, "MAX_FEED_BYTES", 10)
    with pytest.raises(MalformedContentError, match="oversized"):
        parse(b"<rss><channel/></rss>")


def test_bad_date_does_not_drop_valid_entry_and_guid_must_be_a_url():
    result = parse(b"<rss><channel><item><guid>https://example.com/a</guid><pubDate>not a date</pubDate><description>Useful content</description></item><item><guid>opaque</guid></item></channel></rss>")
    assert len(result.documents) == 1
    assert result.documents[0].published_at is None
    assert parse_record_date("0001-01-01T00:00:00+01:00") is None
