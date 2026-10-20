"""Offline regression tests for Developer's Eye HTML parser.

No network, PolicyCoordinator, PostgreSQL, or worker required.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from crawler.parser.errors import (
    ContentDecodeError,
    MalformedContentError,
    ParserError,
    UnsupportedContentTypeError,
)
from crawler.parser.html.extractor import extract_main_content
from crawler.parser.html.links import extract_links
from crawler.parser.html.metadata import extract_metadata
from crawler.parser.parser import parse
from crawler.parser.schemas import ParseResult, ParsedDocument


PAGE_URL = "https://docs.example.org/guides/asyncio"

HTML_FIXTURE = b"""<!doctype html>
<html lang="en">
  <head>
    <title>Fallback title</title>
    <meta property="og:title" content="AsyncIO Developer Guide">
    <meta name="description" content="Learn asynchronous Python programming.">
    <meta name="author" content="Example Author">
    <meta property="article:published_time" content="2026-10-17T12:30:00Z">
    <meta name="robots" content="noindex, nofollow">
    <meta name="keywords" content="python, asyncio">
    <link rel="canonical" href="/guides/asyncio#top">
  </head>
  <body>
    <nav>Navigation should not appear in the main body</nav>
    <main>
      <h1>AsyncIO Tutorial</h1>
      <p>Use asyncio for concurrent tasks.</p>
      <h2>Code sample</h2>
      <pre><code>async def main():
    await asyncio.sleep(1)</code></pre>
      <a href="/reference/asyncio#overview">API Reference</a>
      <a href="/reference/asyncio#different-fragment">Duplicate</a>
      <a href="https://other.example.net/guide" rel="nofollow external">External guide</a>
    </main>
    <footer>Footer should not appear in the main body</footer>
  </body>
</html>
"""


def soup_of(html: str | bytes) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestParserIntegration(unittest.TestCase):
    def test_complete_html_pipeline(self) -> None:
        result = parse(
            url=PAGE_URL,
            content=HTML_FIXTURE,
            content_type="text/html; charset=utf-8",
        )

        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.source_url, PAGE_URL)
        self.assertEqual(result.content_type, "text/html")
        self.assertEqual(len(result.documents), 1)

        doc = result.documents[0]
        self.assertIsInstance(doc, ParsedDocument)
        self.assertEqual(doc.url, PAGE_URL)
        self.assertEqual(doc.title, "AsyncIO Developer Guide")
        self.assertEqual(doc.description, "Learn asynchronous Python programming.")
        self.assertEqual(doc.author, "Example Author")
        self.assertEqual(doc.canonical_url_hint, "https://docs.example.org/guides/asyncio")
        self.assertEqual(doc.published_at, datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(doc.headings, ("AsyncIO Tutorial", "Code sample"))
        self.assertIn("Use asyncio for concurrent tasks.", doc.body)
        self.assertIn("    await asyncio.sleep(1)", doc.code_blocks[0])
        self.assertNotIn("Navigation should not appear", doc.body)
        self.assertNotIn("Footer should not appear", doc.body)
        self.assertEqual(doc.metadata["language"], "en")
        self.assertEqual(doc.metadata["robots_directives"], ["noindex", "nofollow"])
        self.assertEqual(doc.metadata["keywords"], ["python", "asyncio"])

        self.assertEqual(len(result.discovered_links), 2)
        self.assertEqual(
            result.discovered_links[0].url,
            "https://docs.example.org/reference/asyncio",
        )
        self.assertEqual(result.discovered_links[0].anchor_text, "API Reference")
        self.assertTrue(result.discovered_links[1].nofollow)

    def test_xhtml_supported(self) -> None:
        result = parse(
            url=PAGE_URL,
            content=b"<html><body><main><p>Content</p></main></body></html>",
            content_type="application/xhtml+xml",
        )
        self.assertEqual(result.content_type, "application/xhtml+xml")
        self.assertEqual(result.documents[0].body, "Content")

    def test_header_charset_decodes_text(self) -> None:
        content = "<html><body><main><p>café</p></main></body></html>".encode("iso-8859-1")
        result = parse(url=PAGE_URL, content=content, content_type="text/html; charset=iso-8859-1")
        self.assertIn("café", result.documents[0].body)

    def test_title_falls_back_to_h1(self) -> None:
        result = parse(
            url=PAGE_URL,
            content=b"<html><body><main><h1>Fallback heading</h1></main></body></html>",
            content_type="text/html",
        )
        self.assertEqual(result.documents[0].title, "Fallback heading")

    def test_unsupported_or_missing_content_type(self) -> None:
        for content_type in (None, "", "application/json", "application/rss+xml", "image/png"):
            with self.subTest(content_type=content_type):
                with self.assertRaises(UnsupportedContentTypeError):
                    parse(url=PAGE_URL, content=b"<html></html>", content_type=content_type)

    def test_invalid_charset(self) -> None:
        with self.assertRaises(ContentDecodeError):
            parse(url=PAGE_URL, content=b"<html></html>", content_type="text/html; charset=not-real-charset-999")

    def test_empty_html_body(self) -> None:
        for body in (b"", b"  \n\t  "):
            with self.subTest(body=body):
                with self.assertRaises(MalformedContentError):
                    parse(url=PAGE_URL, content=body, content_type="text/html")

    def test_body_requires_bytes(self) -> None:
        with self.assertRaises(TypeError):
            parse(url=PAGE_URL, content="<html></html>", content_type="text/html")  # type: ignore[arg-type]

    def test_invalid_page_urls(self) -> None:
        urls = (
            "/relative",
            "ftp://example.com/file",
            "https://user:pass@example.com/docs",
            "https://example.com:abc/docs",
            "https://example.com:0/docs",
            "https://example.com/page name",
        )
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ParserError):
                    parse(url=url, content=b"<html></html>", content_type="text/html")

    def test_empty_document_still_has_result(self) -> None:
        result = parse(url=PAGE_URL, content=b"<html><body></body></html>", content_type="text/html")
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].body, "")
        self.assertEqual(result.discovered_links, ())


class TestMainContentExtractor(unittest.TestCase):
    def test_main_content_over_navigation_and_footer(self) -> None:
        soup = soup_of(HTML_FIXTURE)
        original_html = str(soup)
        extracted = extract_main_content(soup)
        self.assertEqual(extracted.headings, ("AsyncIO Tutorial", "Code sample"))
        self.assertIn("Use asyncio for concurrent tasks.", extracted.body)
        self.assertNotIn("Navigation should not appear", extracted.body)
        self.assertNotIn("Footer should not appear", extracted.body)
        self.assertEqual(str(soup), original_html, "Extractor must not mutate the original HTML tree")

    def test_preserves_code_indentation(self) -> None:
        soup = soup_of("<main><pre><code>if True:\n    print('ok')\n</code></pre></main>")
        result = extract_main_content(soup)
        self.assertEqual(result.code_blocks, ("if True:\n    print('ok')",))
        self.assertIn("    print('ok')", result.body)

    def test_falls_back_to_article(self) -> None:
        soup = soup_of("<body><nav>Menu</nav><article><h1>Article</h1><p>Story</p></article></body>")
        result = extract_main_content(soup)
        self.assertEqual(result.headings, ("Article",))
        self.assertIn("Story", result.body)
        self.assertNotIn("Menu", result.body)

    def test_falls_back_to_body(self) -> None:
        soup = soup_of("<body><p>Body fallback text.</p></body>")
        self.assertEqual(extract_main_content(soup).body, "Body fallback text.")

    def test_excludes_hidden_and_noise(self) -> None:
        soup = soup_of("""
        <main>
          <p>Keep this.</p>
          <div hidden>Hidden</div>
          <div aria-hidden="true">Invisible</div>
          <div class="cookie-banner">Cookies</div>
          <p style="display:none">Not visible</p>
        </main>
        """)
        result = extract_main_content(soup)
        self.assertIn("Keep this.", result.body)
        for excluded in ("Hidden", "Invisible", "Cookies", "Not visible"):
            self.assertNotIn(excluded, result.body)

    def test_invalid_input(self) -> None:
        with self.assertRaises(TypeError):
            extract_main_content("<main>Not a Soup object</main>")  # type: ignore[arg-type]


class TestMetadataExtraction(unittest.TestCase):
    def test_extracts_metadata_without_mutating_soup(self) -> None:
        soup = soup_of(HTML_FIXTURE)
        snapshot = str(soup)
        meta = extract_metadata(soup, page_url=PAGE_URL)
        self.assertEqual(meta.title, "AsyncIO Developer Guide")
        self.assertEqual(meta.description, "Learn asynchronous Python programming.")
        self.assertEqual(meta.author, "Example Author")
        self.assertEqual(meta.published_at.tzinfo, timezone.utc)
        self.assertEqual(meta.metadata["robots_directives"], ["noindex", "nofollow"])
        self.assertEqual(str(soup), snapshot)

    def test_canonical_is_only_a_hint(self) -> None:
        soup = soup_of('<head><link rel="canonical" href="https://other.example.net/article#intro"></head>')
        meta = extract_metadata(soup, page_url=PAGE_URL)
        self.assertEqual(meta.canonical_url_hint, "https://other.example.net/article")

    def test_invalid_canonical_falls_back_to_og_url(self) -> None:
        soup = soup_of('''<head>
          <link rel="canonical" href="javascript:alert(1)">
          <meta property="og:url" content="/valid#frag">
        </head>''')
        meta = extract_metadata(soup, page_url=PAGE_URL)
        self.assertEqual(meta.canonical_url_hint, "https://docs.example.org/valid")

    def test_missing_optional_metadata(self) -> None:
        meta = extract_metadata(soup_of("<html><body><p>Hello</p></body></html>"), page_url=PAGE_URL)
        self.assertIsNone(meta.title)
        self.assertIsNone(meta.description)
        self.assertIsNone(meta.canonical_url_hint)
        self.assertIsNone(meta.published_at)

    def test_invalid_page_url(self) -> None:
        with self.assertRaises(ValueError):
            extract_metadata(soup_of("<html></html>"), page_url="/relative")


class TestLinkExtraction(unittest.TestCase):
    def test_relative_links_fragments_and_duplicates(self) -> None:
        soup = soup_of('''<main>
            <a href="/docs#one">First</a>
            <a href="/docs#two">Duplicate</a>
            <a href="next">Next</a>
            <a href="#part">Skip fragment-only</a>
        </main>''')
        links = extract_links(soup, PAGE_URL)
        self.assertEqual([link.url for link in links], [
            "https://docs.example.org/docs",
            "https://docs.example.org/guides/next",
        ])
        self.assertEqual(links[0].anchor_text, "First")

    def test_base_href(self) -> None:
        soup = soup_of('''<html><head><base href="https://cdn.example.org/reference/"></head>
        <body><a href="topic">Topic</a></body></html>''')
        links = extract_links(soup, PAGE_URL)
        self.assertEqual(links[0].url, "https://cdn.example.org/reference/topic")

    def test_rejects_non_http_and_malformed_destinations(self) -> None:
        soup = soup_of('''<main>
            <a href="mailto:person@example.org">Email</a>
            <a href="javascript:alert(1)">JS</a>
            <a href="data:text/plain,test">Data</a>
            <a href="https://user:pass@example.net/private">Credentials</a>
            <a href="https://example.net:abc/a">Bad port</a>
            <a href="/valid">Good</a>
        </main>''')
        links = extract_links(soup, PAGE_URL)
        self.assertEqual([link.url for link in links], ["https://docs.example.org/valid"])

    def test_cross_host_link_is_discovered_but_not_authorized(self) -> None:
        links = extract_links(soup_of('<a href="https://external.example.net/x">Outside</a>'), PAGE_URL)
        self.assertEqual(links[0].url, "https://external.example.net/x")
        # Authorization is the responsibility of the frontier/coordinator.

    def test_nofollow_and_rel(self) -> None:
        links = extract_links(soup_of('<a href="/x" rel="nofollow external">Read</a>'), PAGE_URL)
        self.assertEqual(links[0].rel, ("nofollow", "external"))
        self.assertTrue(links[0].nofollow)

    def test_max_links(self) -> None:
        soup = soup_of('<main><a href="/a">A</a><a href="/b">B</a></main>')
        links = extract_links(soup, PAGE_URL, max_links=1)
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].url.endswith("/a"))

    def test_invalid_inputs(self) -> None:
        soup = soup_of("<html></html>")
        with self.assertRaises(TypeError):
            extract_links("not a soup", PAGE_URL)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            extract_links(soup, PAGE_URL, max_links=0)
        with self.assertRaises(ValueError):
            extract_links(soup, "/relative")


if __name__ == "__main__":
    unittest.main(verbosity=2)
