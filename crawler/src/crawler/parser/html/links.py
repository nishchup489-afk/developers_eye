
"""Discover URL candidates from already-parsed HTML.

No HTTP requests, DNS lookups, database access, or mutations to the soup tree.
The parser discovers links; the Worker/Frontier decides which to enqueue.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from crawler.frontier.urls import normalize_url
from crawler.parser.schemas import DiscoveredLink


DEFAULT_MAX_LINKS = 1_000


def _effective_base_url(
    soup: BeautifulSoup | Tag,
    page_url: str,
) -> str:
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
        return page_url


def extract_links(
    soup: BeautifulSoup | Tag,
    page_url: str,
    *,
    max_links: int = DEFAULT_MAX_LINKS,
) -> tuple[DiscoveredLink, ...]:
    """Return unique, normalized HTTP(S) link candidates.

    - Resolve relative links against the effective base URL.
    - Ignore empty, fragment-only, unsupported and malformed URLs.
    - Preserve rel="nofollow" as metadata.
    - Remove fragments using the Frontier's URL normalizer.
    - Never authorize, fetch, or enqueue discovered URLs.
    """

    if not isinstance(soup, Tag):
        raise TypeError("soup must be a BeautifulSoup or Tag instance")

    if type(max_links) is not int or max_links <= 0:
        raise ValueError("max_links must be a positive integer")

    page_url = normalize_url(page_url)
    base_url = _effective_base_url(soup, page_url)

    found: list[DiscoveredLink] = []
    seen: set[str] = set()

    for anchor in soup.find_all(["a", "area"], href=True):

        href = anchor.get("href")

        if not isinstance(href, str):
            continue

        href = href.strip()

        if not href or href.startswith("#"):
            continue

        # Extract link relationship attributes.
        raw_rel = anchor.get("rel", ())

        if isinstance(raw_rel, str):
            rel_tokens = raw_rel.split()

        elif isinstance(raw_rel, (list, tuple)):
            rel_tokens = raw_rel

        else:
            rel_tokens = ()

        rel = tuple(
            dict.fromkeys(
                str(token).casefold()
                for token in rel_tokens
                if token
            )
        )

        nofollow = "nofollow" in rel

        # Resolve and normalize the destination URL.
        try:
            absolute = urljoin(base_url, href)
            normalized = normalize_url(absolute)

        except ValueError:
            continue

        # Prevent duplicate URLs.
        if normalized in seen:
            continue

        seen.add(normalized)

        # Extract visible anchor text.
        anchor_text = " ".join(
            anchor.get_text(" ", strip=True).split()
        )[:300]

        # Preserve the URL and its metadata.
        link = DiscoveredLink(
            url=normalized,
            anchor_text=anchor_text,
            rel=rel,
            nofollow=nofollow,
        )

        found.append(link)

        if len(found) >= max_links:
            break

    return tuple(found)
