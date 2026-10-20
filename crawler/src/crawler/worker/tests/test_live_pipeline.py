"""Live, rollback-only HTML crawl test for Developer's Eye.

Exercises:
    PolicyCoordinator -> HTTPXHopFetcher -> HTML parser -> processor

Intentionally bypasses:
    Seed discovery, scheduler, frontier enqueue, database writer, indexer.

Requires the project's backend DATABASE_URL because robots_policy uses its
PostgreSQL robots_cache. All changes in this runner's session are rolled back.
No crawled document, frontier target, crawl attempt, or search index is stored.

Run from repository root (crawler package and backend package must be importable):
    python -m crawler.worker.tests.test_live_pipeline

For a custom, explicitly approved source:
    python -m crawler.worker.tests.test_live_pipeline \
        --allow-host docs.python.org \
        --url https://docs.python.org/3/tutorial/
"""

from __future__ import annotations

import argparse
import asyncio
import re
import time
import traceback
from dataclasses import dataclass
from dataclasses import replace
from collections.abc import Mapping

from colorama import Fore, Style, init as colorama_init

from backend.db.session import SessionFactory, engine
from crawler.fetcher.fetch import HTTPXHopFetcher
from crawler.parser.errors import ParserError
from crawler.parser.parser import parse
from crawler.parser.schemas import ParseResult
from crawler.policy_and_politeness.policy_coordinator import PolicyCoordinator
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision, USER_AGENT
from crawler.processing.processing import process


# Explicitly approved, real example URLs. No links found on these pages
# will be followed or added to the frontier.
DEFAULT_URLS = (
    "https://docs.python.org/3/",
    "https://docs.python.org/3/tutorial/",
    "https://docs.python.org/3/library/",
    "https://docs.python.org/3/reference/",
    "https://docs.python.org/3/howto/",
)
DEFAULT_ALLOWED_HOSTS = ("docs.python.org",)
MAX_BODY_BYTES = 2_000_000
TIMEOUT_SECONDS = 15.0
BODY_PREVIEW_CHARS = 250
LINK_PREVIEW_COUNT = 5


@dataclass(slots=True)
class CrawlStats:
    tested: int = 0
    allowed: int = 0
    denied: int = 0
    deferred: int = 0
    non_html_or_http_error: int = 0
    parsed_pages: int = 0
    accepted_documents: int = 0
    skipped_documents: int = 0
    discovered_links: int = 0
    errors: int = 0


def _print(message: str, color: str = "") -> None:
    print(f"{color}{message}{Style.RESET_ALL}")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Read HTTP headers case-insensitively (including plain dictionaries)."""
    name = name.casefold()
    for key, value in headers.items():
        if key.casefold() == name:
            return value
    return None


def _applicable_x_robots(value: str | None) -> tuple[str, ...]:
    """Extract basic unscoped / own-bot X-Robots-Tag directives.

    This intentionally does not claim to implement every X-Robots-Tag syntax.
    In particular, a directive scoped to a different bot must not be applied.
    """
    if not value:
        return ()

    current_agent = USER_AGENT.split("/", 1)[0].casefold()
    tokens: list[str] = []
    for part in value.split(","):
        part = part.strip().casefold()
        if not part:
            continue
        if ":" in part:
            scope, part = part.split(":", 1)
            if scope.strip() not in (current_agent, "*"):
                continue
        tokens.extend(re.split(r"[;\s]+", part.strip()))
    return tuple(token for token in tokens if token)


def _add_response_robots(parsed: ParseResult, headers: Mapping[str, str]) -> ParseResult:
    """Copy header-level directives into the schema the processor already uses.

    Never mutate the original ParsedDocument or its metadata dictionary.
    """
    extra = _applicable_x_robots(_header(headers, "x-robots-tag"))
    if not extra:
        return parsed

    documents = []
    for doc in parsed.documents:
        metadata = dict(doc.metadata)
        existing = metadata.get("robots_directives", ())
        if isinstance(existing, str):
            previous = [existing]
        elif isinstance(existing, (list, tuple, set, frozenset)):
            previous = [x for x in existing if isinstance(x, str)]
        else:
            previous = []
        metadata["robots_directives"] = [*previous, *extra]
        documents.append(replace(doc, metadata=metadata))
    return replace(parsed, documents=tuple(documents))


async def crawl_one(coordinator: PolicyCoordinator, session, url: str, stats: CrawlStats) -> None:
    stats.tested += 1
    started = time.perf_counter()
    _print("\n" + "=" * 76, Fore.CYAN)
    _print(f"[{stats.tested:02}] {url}", Fore.CYAN)

    try:
        fetched = await coordinator.fetch(session=session, url=url)
        elapsed = time.perf_counter() - started

        _print(f"Policy: {fetched.decision.value.upper()} | {fetched.reason}")
        _print(f"Final URL: {fetched.final_url}")
        _print(f"HTTP status: {fetched.status_code} | bytes: {len(fetched.body)}")
        _print(f"Fetch + policies: {elapsed:.2f}s")
        if len(fetched.redirect_chain) > 1:
            _print("Redirect chain: " + " -> ".join(fetched.redirect_chain))

        if fetched.decision == RobotsDecision.DENY:
            stats.denied += 1
            _print("[DENIED] Not attempting to parse.", Fore.YELLOW)
            return
        if fetched.decision == RobotsDecision.DEFER:
            stats.deferred += 1
            _print(
                f"[DEFERRED] Retry after: {fetched.retry_after_seconds}s (no automatic retry)",
                Fore.YELLOW,
            )
            return
        if fetched.decision != RobotsDecision.ALLOW:
            raise RuntimeError(f"Unexpected policy decision: {fetched.decision!r}")
        stats.allowed += 1

        content_type = _header(fetched.headers, "content-type") or ""
        mime_type = content_type.split(";", 1)[0].strip().casefold()
        if fetched.status_code != 200 or mime_type not in ("text/html", "application/xhtml+xml") or not fetched.body:
            stats.non_html_or_http_error += 1
            _print(f"[SKIP PARSE] HTTP={fetched.status_code}, MIME={mime_type or '(missing)'}, body={len(fetched.body)}", Fore.YELLOW)
            return

        # Parse the actual fetched response, not a hardcoded HTML fixture.
        parsed = parse(url=fetched.final_url, content=fetched.body, content_type=content_type)
        parsed = _add_response_robots(parsed, fetched.headers)
        stats.parsed_pages += 1
        stats.discovered_links += len(parsed.discovered_links)
        _print(f"[PARSED] documents={len(parsed.documents)} | discovered links={len(parsed.discovered_links)}", Fore.GREEN)

        # Synchronous CPU/data processing. No persistence is called.
        processed = process(parsed)
        stats.accepted_documents += len(processed.documents)
        stats.skipped_documents += len(processed.skipped)

        for index, doc in enumerate(processed.documents, 1):
            _print(f"\n[ACCEPTED DOCUMENT {index}]", Fore.GREEN)
            _print(f"Title: {doc.title or '(none)'}")
            _print(f"Canonical URL: {doc.canonical_url}")
            _print(f"Type: {doc.document_type.value} | tags: {', '.join(doc.tags) or '(none)'}")
            _print(f"Headings: {len(doc.headings)} | code blocks: {len(doc.code_blocks)}")
            _print(f"SHA-256: {doc.content_hash}")
            snippet = " ".join(doc.body.split())[:BODY_PREVIEW_CHARS]
            _print(f"Body preview: {snippet}{'...' if len(doc.body) > BODY_PREVIEW_CHARS else ''}")

        for skipped in processed.skipped:
            _print(f"[SKIPPED] {skipped.reason.value}: {skipped.details or '(no details)'}", Fore.YELLOW)

        if parsed.discovered_links:
            _print("Discovered links (display only, never enqueued):", Fore.CYAN)
            for link in parsed.discovered_links[:LINK_PREVIEW_COUNT]:
                _print(f"  - {link.url} | nofollow={link.nofollow}")
            if len(parsed.discovered_links) > LINK_PREVIEW_COUNT:
                _print(f"  ... {len(parsed.discovered_links) - LINK_PREVIEW_COUNT} more")

    except ParserError as exc:
        stats.errors += 1
        _print(f"[PARSER ERROR] {type(exc).__name__}: {exc}", Fore.RED)
    except Exception as exc:
        # Print unexpected integration bugs rather than silently skipping them.
        stats.errors += 1
        _print(f"[INTEGRATION ERROR] {type(exc).__name__}: {exc}", Fore.RED)
        traceback.print_exc()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Developer's Eye: live fetch -> parse -> process, no committed DB writes")
    parser.add_argument("--url", action="append", help="Exact URL to test; repeat to test multiple URLs")
    parser.add_argument("--allow-host", action="append", help="Explicit allowed hostname; repeat for multiple hosts")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    urls = tuple(args.url) if args.url else DEFAULT_URLS
    allowed_hosts = tuple(args.allow_host) if args.allow_host else DEFAULT_ALLOWED_HOSTS

    colorama_init(autoreset=True)
    _print("DEVELOPER'S EYE | LIVE HTML PIPELINE TEST", Fore.CYAN)
    _print("PolicyCoordinator -> HTTPXHopFetcher -> Parser -> Processor")
    _print("DRY RUN: no document/index/frontier writes; robots-cache transaction rolls back.", Fore.YELLOW)
    _print(f"URLs: {len(urls)} | Allowed hosts: {', '.join(allowed_hosts)}")

    coordinator = PolicyCoordinator(
        allowed_hosts=allowed_hosts,
        fetcher=HTTPXHopFetcher(),
        politeness_manager=PolitenessManager(
            max_concurrent_per_host=1,
            min_interval_seconds=2.0,
        ),
        max_body_bytes=MAX_BODY_BYTES,
        timeout_seconds=TIMEOUT_SECONDS,
        user_agent=USER_AGENT,
    )

    stats = CrawlStats()
    try:
        async with SessionFactory() as session:
            try:
                for url in urls:
                    await crawl_one(coordinator, session, url, stats)
            finally:
                # robots_policy may execute UPSERTs; NEVER commit this session.
                await session.rollback()
    finally:
        await engine.dispose()

    _print("\n" + "=" * 76, Fore.CYAN)
    _print("SUMMARY", Fore.CYAN)
    for key in stats.__dataclass_fields__:
        _print(f"  {key}: {getattr(stats, key)}")
    _print("Persisted documents: 0 | Enqueued links: 0 | Committed transactions: 0", Fore.YELLOW)
    return 0 if stats.accepted_documents > 0 and stats.errors == 0 else 1


if __name__ == "__main__":
    import sys
    import selectors

    if sys.platform == "win32":
        result = asyncio.run(
            main(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    else:
        result = asyncio.run(main())

    raise SystemExit(result)