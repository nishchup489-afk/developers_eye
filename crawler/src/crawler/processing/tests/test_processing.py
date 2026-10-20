"""Offline Colorama test suite for Developer's Eye's content processing.

Tests:
    ParsedDocument -> normalize -> classify -> fingerprint -> ProcessingResult

No HTTP requests, DNS lookups, PostgreSQL connections, or crawler workers.

Run from the developers-eye project root:
    python -m unittest discover -s crawler/src/crawler/processing/tests \
        -p "test_processing.py" -v

Or run this file directly:
    python crawler/src/crawler/processing/tests/test_processing.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import re
import sys
import unittest
from unittest.mock import patch

from colorama import Fore, Style, init

from crawler.parser.schemas import ParsedDocument, ParseResult
from crawler.parser.schemas import ParsedDocument, ParseResult

from crawler.processing.normalize.normalize import normalize_document
from crawler.processing.classifier.classify import classify_document
from crawler.processing.fingerprint import fingerprint_document

from crawler.processing.schemas import (
    ClassificationResult,
    DocumentType,
    NormalizedDocument,
    ProcessedDocument,
    ProcessingResult,
    SkipReason,
    SkippedDocument,
)
from crawler.processing.processing import process, process_document


# ============================================================
# 1. TEST FIXTURES
# ============================================================

PAGE_URL = "https://docs.example.org/python/tutorial"


def parsed_doc(**overrides: object) -> ParsedDocument:
    """Make a fresh ParsedDocument; override only the fields under test."""
    values: dict[str, object] = {
        "url": PAGE_URL,
        "title": "Python Tutorial",
        "description": "Learn Python and FastAPI",
        "body": "Build a Python backend with FastAPI.",
        "author": "Example Author",
        "headings": ("Getting Started",),
        "code_blocks": (),
        "metadata": {"keywords": ["python", "fastapi"]},
    }
    values.update(overrides)
    return ParsedDocument(**values)


def normalized_doc(**overrides: object) -> NormalizedDocument:
    """Make a fresh normalized document for classifier/hash unit tests."""
    values: dict[str, object] = {
        "url": PAGE_URL,
        "canonical_url": PAGE_URL,
        "title": "Python Tutorial",
        "description": "Learn Python and FastAPI",
        "body": "Build a Python backend with FastAPI.",
        "headings": ("Getting Started",),
        "code_blocks": (),
        "metadata": {"keywords": ["python", "fastapi"]},
    }
    values.update(overrides)
    return NormalizedDocument(**values)


def parse_result(*documents: ParsedDocument) -> ParseResult:
    return ParseResult(
        source_url="https://docs.example.org/feed",
        content_type="text/html",
        documents=documents,
    )


# ============================================================
# 2. NORMALIZATION
# ============================================================

class Test01Normalization(unittest.TestCase):

    def test_cleans_short_fields(self) -> None:
        doc = parsed_doc(
            title="  Python    Tutorial  ",
            description=" Learn\tPython   and FastAPI ",
            author="  Jane   Doe  ",
        )
        actual = normalize_document(doc)
        self.assertEqual(actual.title, "Python Tutorial")
        self.assertEqual(actual.description, "Learn Python and FastAPI")
        self.assertEqual(actual.author, "Jane Doe")

    def test_cleans_body_and_blank_lines(self) -> None:
        doc = parsed_doc(body=" Hello    world. \r\n\r\n\r\n Next    line. ")
        self.assertEqual(
            normalize_document(doc).body,
            "Hello world.\n\nNext line.",
        )

    def test_preserves_code_indentation(self) -> None:
        code = "if True:\n    print('ok')"
        doc = parsed_doc(
            body=f"Example:\n{code}\nDone.",
            code_blocks=(code,),
        )
        actual = normalize_document(doc)
        self.assertIn(code, actual.body)
        self.assertEqual(actual.code_blocks, (code,))

    def test_cleans_headings_and_code_blocks(self) -> None:
        actual = normalize_document(parsed_doc(
            headings=(" Intro   to   Python ", "", "  "),
            code_blocks=("\n    print('hello')\n", "\n"),
        ))
        self.assertEqual(actual.headings, ("Intro to Python",))
        self.assertEqual(actual.code_blocks, ("    print('hello')",))

    def test_normalizes_unicode_nfc(self) -> None:
        actual = normalize_document(parsed_doc(title="Cafe\u0301 Tutorial"))
        self.assertEqual(actual.title, "Caf\u00e9 Tutorial")

    def test_removes_fragment_from_url(self) -> None:
        actual = normalize_document(parsed_doc(
            url="https://docs.example.org/python/tutorial#intro"
        ))
        self.assertEqual(actual.url, PAGE_URL)

    def test_accepts_same_host_canonical_hint(self) -> None:
        actual = normalize_document(parsed_doc(
            canonical_url_hint="/python/reference#top"
        ))
        self.assertEqual(
            actual.canonical_url, "https://docs.example.org/python/reference"
        )

    def test_rejects_external_canonical_hint(self) -> None:
        actual = normalize_document(parsed_doc(
            canonical_url_hint="https://outside.example.net/copy"
        ))
        self.assertEqual(actual.canonical_url, PAGE_URL)

    def test_rejects_https_downgrade_hint(self) -> None:
        actual = normalize_document(parsed_doc(
            canonical_url_hint="http://docs.example.org/python/tutorial"
        ))
        self.assertEqual(actual.canonical_url, PAGE_URL)

    def test_rejects_bad_canonical_hint_without_failing(self) -> None:
        actual = normalize_document(parsed_doc(
            canonical_url_hint="javascript:alert(1)"
        ))
        self.assertEqual(actual.canonical_url, PAGE_URL)

    def test_does_not_mutate_source_metadata(self) -> None:
        source = parsed_doc(metadata={"keywords": ["python"], "extra": {"v": 1}})
        normalized = normalize_document(source)
        normalized.metadata["keywords"].append("docker")
        normalized.metadata["extra"]["v"] = 2
        self.assertEqual(source.metadata, {"keywords": ["python"], "extra": {"v": 1}})

    def test_rejects_invalid_source_urls(self) -> None:
        for url in (
            "ftp://example.org/a",
            "https://user:pass@example.org/a",
            "https://example.org/space here",
            "/relative/path",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    normalize_document(parsed_doc(url=url))

    def test_rejects_wrong_input_type(self) -> None:
        with self.assertRaises(TypeError):
            normalize_document("not a parsed document")  # type: ignore[arg-type]

    def test_rejects_bad_code_block_types(self) -> None:
        with self.assertRaises(TypeError):
            normalize_document(parsed_doc(code_blocks=(123,)))


# ============================================================
# 3. CLASSIFICATION
# ============================================================

class Test02Classification(unittest.TestCase):

    def check_type(self, url: str, expected: DocumentType) -> ClassificationResult:
        result = classify_document(normalized_doc(
            url=url, canonical_url=url,
            title="Unrelated page", description="", metadata={},
        ))
        self.assertEqual(result.document_type, expected)
        self.assertTrue(result.method.startswith("rules:"))
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        return result

    def test_github_issue(self) -> None:
        result = self.check_type(
            "https://github.com/tiangolo/fastapi/issues/123", DocumentType.ISSUE
        )
        self.assertEqual(result.method, "rules:github_issue")

    def test_github_repository(self) -> None:
        self.check_type("https://github.com/tiangolo/fastapi", DocumentType.REPOSITORY)

    def test_github_discussion(self) -> None:
        self.check_type(
            "https://github.com/owner/repo/discussions/42", DocumentType.DISCUSSION
        )

    def test_gitlab_issue(self) -> None:
        self.check_type(
            "https://gitlab.com/group/repo/-/issues/5", DocumentType.ISSUE
        )

    def test_stackoverflow_question_not_help_page(self) -> None:
        self.check_type(
            "https://stackoverflow.com/questions/12345/python", DocumentType.QUESTION
        )
        self.check_type("https://stackoverflow.com/help", DocumentType.OTHER)

    def test_reddit_discussion(self) -> None:
        self.check_type(
            "https://www.reddit.com/r/Python/comments/abc123/topic",
            DocumentType.DISCUSSION,
        )

    def test_docs_host(self) -> None:
        self.check_type(
            "https://docs.python.org/3/library/asyncio.html",
            DocumentType.DOCUMENTATION,
        )

    def test_tutorial_path_overrides_documentation_host(self) -> None:
        self.check_type("https://docs.python.org/3/tutorial/", DocumentType.TUTORIAL)

    def test_blog_platform(self) -> None:
        self.check_type("https://dev.to/author/a-post", DocumentType.BLOG)

    def test_event_platform(self) -> None:
        self.check_type(
            "https://www.meetup.com/python/events/1234", DocumentType.EVENT
        )

    def test_title_fallback(self) -> None:
        actual = classify_document(normalized_doc(
            url="https://example.org/a", canonical_url="https://example.org/a",
            title="Getting Started with Docker", metadata={}, description="",
        ))
        self.assertEqual(actual.document_type, DocumentType.TUTORIAL)
        self.assertIn("docker", actual.tags)

    def test_article_metadata_fallback(self) -> None:
        actual = classify_document(normalized_doc(
            url="https://example.org/a", canonical_url="https://example.org/a",
            title="Untitled", description="", metadata={"og:type": "article"},
        ))
        self.assertEqual(actual.document_type, DocumentType.BLOG)

    def test_unknown_page_falls_back_to_other(self) -> None:
        result = self.check_type("https://example.org/random", DocumentType.OTHER)
        self.assertEqual(result.confidence, 0.0)

    def test_does_not_match_fake_github_domain(self) -> None:
        self.check_type("https://notgithub.com/owner/repo", DocumentType.OTHER)

    def test_tags_from_short_fields_not_body(self) -> None:
        actual = classify_document(normalized_doc(
            canonical_url="https://example.org/a",
            title="Python and FastAPI",
            description="PostgreSQL with Docker",
            body="This also mentions Rust and Kubernetes.",
            metadata={},
        ))
        self.assertEqual(actual.tags, ("python", "fastapi", "postgresql", "docker"))

    def test_rejects_bad_document_type(self) -> None:
        with self.assertRaises(TypeError):
            classify_document("https://example.org")  # type: ignore[arg-type]

    def test_rejects_non_http_canonical_url(self) -> None:
        with self.assertRaises(ValueError):
            classify_document(normalized_doc(canonical_url="ftp://example.org/a"))


# ============================================================
# 4. FINGERPRINTING
# ============================================================

class Test03Fingerprint(unittest.TestCase):

    def test_sha256_is_lowercase_hex(self) -> None:
        digest = fingerprint_document(normalized_doc())
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_same_document_same_hash(self) -> None:
        doc = normalized_doc()
        self.assertEqual(fingerprint_document(doc), fingerprint_document(doc))

    def test_url_author_and_metadata_do_not_change_hash(self) -> None:
        original = normalized_doc()
        changed = replace(
            original,
            url="https://mirror.example.org/a",
            canonical_url="https://mirror.example.org/a",
            author="Different person",
            metadata={"keywords": ["rust"]},
            published_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        )
        self.assertEqual(fingerprint_document(original), fingerprint_document(changed))

    def test_body_change_changes_hash(self) -> None:
        doc = normalized_doc()
        self.assertNotEqual(
            fingerprint_document(doc),
            fingerprint_document(replace(doc, body=doc.body + " Updated.")),
        )

    def test_title_and_description_change_hash(self) -> None:
        doc = normalized_doc()
        self.assertNotEqual(
            fingerprint_document(doc),
            fingerprint_document(replace(doc, title="Different title")),
        )
        self.assertNotEqual(
            fingerprint_document(doc),
            fingerprint_document(replace(doc, description="Different description")),
        )

    def test_headings_and_code_blocks_change_hash(self) -> None:
        doc = normalized_doc()
        self.assertNotEqual(
            fingerprint_document(doc),
            fingerprint_document(replace(doc, headings=("Changed",))),
        )
        self.assertNotEqual(
            fingerprint_document(doc),
            fingerprint_document(replace(doc, code_blocks=("print('ok')",))),
        )

    def test_different_field_boundaries_do_not_collide(self) -> None:
        first = normalized_doc(title="ab", description="c")
        second = normalized_doc(title="a", description="bc")
        self.assertNotEqual(fingerprint_document(first), fingerprint_document(second))

    def test_rejects_wrong_input(self) -> None:
        with self.assertRaises(TypeError):
            fingerprint_document("hello")  # type: ignore[arg-type]

    def test_rejects_invalid_code_blocks(self) -> None:
        with self.assertRaises(TypeError):
            fingerprint_document(normalized_doc(code_blocks=(123,)))


# ============================================================
# 5. COMPLETE PROCESSING PIPELINE
# ============================================================

class Test04Processor(unittest.TestCase):

    def test_one_document_end_to_end(self) -> None:
        result = process(parse_result(parsed_doc(title="  Python    Tutorial  ")))
        self.assertIsInstance(result, ProcessingResult)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(len(result.skipped), 0)

        doc = result.documents[0]
        self.assertIsInstance(doc, ProcessedDocument)
        self.assertEqual(doc.title, "Python Tutorial")
        self.assertEqual(doc.document_type, DocumentType.TUTORIAL)
        self.assertIn("python", doc.tags)
        self.assertRegex(doc.content_hash, r"^[0-9a-f]{64}$")

    
    def test_missing_title_uses_heading(self):
        document = parsed_doc(
            title=None,
            headings=("Python Asyncio Documentation",),
        )

        result = process_document(document)

        self.assertIsInstance(result, ProcessedDocument)
        self.assertEqual(
            result.title,
            "Python Asyncio Documentation",
        )
        self.assertTrue(result.metadata["generated_title"])


    def test_missing_title_uses_url(self):
        document = parsed_doc(
            title=None,
            headings=(),
        )

        result = process_document(document)

        self.assertIsInstance(result, ProcessedDocument)
        self.assertEqual(result.title, "tutorial")
        self.assertTrue(result.metadata["generated_title"])


    def test_noindex_string_skips_document(self) -> None:
        result = process_document(parsed_doc(metadata={
            "robots_directives": "NOINDEX, FOLLOW"
        }))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.NOINDEX)

    def test_none_directive_skips_document(self) -> None:
        result = process_document(parsed_doc(metadata={
            "robots_directives": ["index", " NoNe "]
        }))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.NOINDEX)

    def test_nofollow_alone_does_not_prevent_indexing(self) -> None:
        result = process_document(parsed_doc(metadata={
            "robots_directives": ["nofollow"]
        }))
        self.assertIsInstance(result, ProcessedDocument)

    def test_empty_body_is_skipped(self) -> None:
        result = process_document(parsed_doc(body="", code_blocks=()))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.EMPTY_CONTENT)

    def test_whitespace_only_body_is_skipped(self) -> None:
        result = process_document(parsed_doc(body="  \n\t ", code_blocks=()))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.EMPTY_CONTENT)

    def test_code_only_page_is_accepted(self) -> None:
        result = process_document(parsed_doc(
            body="", code_blocks=("print('hello')",)
        ))
        self.assertIsInstance(result, ProcessedDocument)

    def test_invalid_url_becomes_skipped_document(self) -> None:
        result = process_document(parsed_doc(url="file:///etc/passwd"))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.INVALID_URL)

    def test_malformed_body_becomes_processing_error(self) -> None:
        result = process_document(parsed_doc(body=123))
        self.assertIsInstance(result, SkippedDocument)
        self.assertEqual(result.reason, SkipReason.PROCESSING_ERROR)

    def test_processes_multiple_documents_independently(self) -> None:
        batch = parse_result(
            parsed_doc(),
            parsed_doc(url="https://example.org/blocked", metadata={
                "robots_directives": ("noindex",)
            }),
            parsed_doc(url="https://example.org/blank", body=""),
            parsed_doc(url="https://github.com/owner/repo/issues/99", title="Issue"),
        )
        result = process(batch)
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(len(result.skipped), 2)
        self.assertEqual(
            {skipped.reason for skipped in result.skipped},
            {SkipReason.NOINDEX, SkipReason.EMPTY_CONTENT},
        )
        self.assertEqual(result.documents[1].document_type, DocumentType.ISSUE)

    def test_empty_parse_result_is_valid(self) -> None:
        result = process(parse_result())
        self.assertEqual(result.documents, ())
        self.assertEqual(result.skipped, ())

    def test_source_url_is_preserved(self) -> None:
        result = process(parse_result(parsed_doc()))
        self.assertEqual(result.source_url, "https://docs.example.org/feed")

    def test_classification_metadata_is_preserved(self) -> None:
        original = parsed_doc(metadata={"keywords": ["python"]})
        result = process_document(original)
        self.assertIsInstance(result, ProcessedDocument)
        self.assertEqual(result.metadata["keywords"], ["python"])
        self.assertIn("method", result.metadata["classification"])
        self.assertIn("confidence", result.metadata["classification"])
        self.assertNotIn("classification", original.metadata)

    def test_noindex_short_circuits_classification(self) -> None:
        with patch(
            "crawler.processing.processing.classify_document",
            side_effect=AssertionError("Should not classify a noindex document"),
        ):
                    result = process_document(parsed_doc(metadata={
                "robots_directives": ["noindex"]
            }))
        self.assertEqual(result.reason, SkipReason.NOINDEX)

    def test_different_urls_same_content_not_deduped_here(self) -> None:
        a = parsed_doc(url="https://example.org/one")
        b = parsed_doc(url="https://example.org/two")
        result = process(parse_result(a, b))
        self.assertEqual(len(result.documents), 2)
        self.assertEqual(
            result.documents[0].content_hash,
            result.documents[1].content_hash,
        )

    def test_wrong_processor_inputs_raise_type_error(self) -> None:
        with self.assertRaises(TypeError):
            process_document("not a document")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            process("not a parse result")  # type: ignore[arg-type]


# ============================================================
# 6. COLORAMA RUNNER
# ============================================================

class ColorResult(unittest.TextTestResult):
    """Color pass/fail/error/skip status while preserving unittest tracebacks."""

    def startTest(self, test: unittest.case.TestCase) -> None:
        category = type(test).__name__
        if getattr(self, "_last_category", None) != category:
            self.stream.writeln(
                f"\n{Fore.CYAN}{Style.BRIGHT}== {category} =={Style.RESET_ALL}"
            )
            self._last_category = category
        super().startTest(test)

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self.stream.writeln(f"{Fore.GREEN}[PASS]{Style.RESET_ALL} {test._testMethodName}")

    def addFailure(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addFailure(test, err)
        self.stream.writeln(f"{Fore.RED}[FAIL]{Style.RESET_ALL} {test._testMethodName}")

    def addError(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addError(test, err)
        self.stream.writeln(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {test._testMethodName}")

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.stream.writeln(
            f"{Fore.YELLOW}[SKIP]{Style.RESET_ALL} {test._testMethodName}: {reason}"
        )


class ColorRunner(unittest.TextTestRunner):
    resultclass = ColorResult

    def run(self, test: unittest.suite.TestSuite) -> unittest.TestResult:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}DEVELOPER'S EYE | PROCESSING TESTS{Style.RESET_ALL}")
        print(f"{Fore.CYAN}normalize -> classify -> fingerprint -> processor{Style.RESET_ALL}")
        result = super().run(test)
        passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        print(f"\n{Style.BRIGHT}SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Passed: {passed}{Style.RESET_ALL}  "
              f"{Fore.RED}Failed: {len(result.failures)}{Style.RESET_ALL}  "
              f"{Fore.RED}Errors: {len(result.errors)}{Style.RESET_ALL}  "
              f"{Fore.YELLOW}Skipped: {len(result.skipped)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN if result.wasSuccessful() else Fore.RED}"
              f"{'ALL TESTS PASSED' if result.wasSuccessful() else 'TESTS FAILED'}"
              f"{Style.RESET_ALL}")
        return result


# Run directly for colored results, or use unittest discovery.
if __name__ == "__main__":
    init(autoreset=True)
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    results = ColorRunner(stream=sys.stdout, verbosity=0).run(suite)
    raise SystemExit(0 if results.wasSuccessful() else 1)
