"""Discover crawlable URL candidates from already-parsed HTML.

No HTTP requests, DNS lookups, database access, or mutations to the soup tree.
The parser discovers links; the Worker/Frontier decides which to enqueue.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from crawler.frontier.urls import normalize_url


DEFAULT_MAX_LINKS = 1_000


def _effective_base_url(soup: BeautifulSoup | Tag, page_url: str) -> str:
    """Use the first HTML <base href> if valid, otherwise use the page URL."""
    base_tag = soup.find("base", href=True)
    if not isinstance(base_tag, Tag):
        return page_url

    base_href = base_tag.get("href")
    if not isinstance(base_href, str) or not base_href.strip():
        return page_url

    try:
        return normalize_url(urljoin(page_url, base_href.strip()))
    except ValueError:
        # Invalid or unsupported <base> must not break discovery.
        return page_url


def extract_links(
    soup: BeautifulSoup | Tag,
    page_url: str,
    *,
    max_links: int = DEFAULT_MAX_LINKS,
) -> tuple[str, ...]:
    """Return unique, normalized, absolute HTTP(S) links in document order.

    - Resolve relative links against the document's first <base href> (if valid),
      or the fetched page URL when no valid <base> is present.
    - Ignore empty/fragment-only hrefs, non-HTTP(S) schemes, malformed URLs,
      and per-link rel="nofollow".
    - Remove URL fragments using the Frontier's existing normalizer.
    - Return candidates only; never enqueue them or check DNS/robots here.

    IMPORTANT: Worker/Frontier MUST apply the source's allowed_hosts and
    discovery scope before inserting any returned URL into crawl_target.
    PolicyCoordinator MUST check policies again before any actual fetch.
    """
    if not isinstance(soup, Tag):
        raise TypeError("soup must be a BeautifulSoup or Tag instance")
    if type(max_links) is not int or max_links <= 0:
        raise ValueError("max_links must be a positive integer")

    # The fetched page must be an absolute, supported URL.
    page_url = normalize_url(page_url)
    base_url = _effective_base_url(soup, page_url)

    found: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue

        href = href.strip()
        if not href or href.startswith("#"):
            continue

        # A site's rel="nofollow" is a request not to follow that link.
        rel = anchor.get("rel", ())
        if isinstance(rel, str):
            rel_tokens = rel.split()
        else:
            rel_tokens = rel or ()
        if any(str(token).casefold() == "nofollow" for token in rel_tokens):
            continue

        try:
            absolute = urljoin(base_url, href)
            normalized = normalize_url(absolute)
        except ValueError:
            # e.g. mailto:, javascript:, broken host/port/percent encoding
            continue

        if normalized in seen:
            continue
        seen.add(normalized)
        found.append(normalized)

        if len(found) >= max_links:
            break

    return tuple(found)
