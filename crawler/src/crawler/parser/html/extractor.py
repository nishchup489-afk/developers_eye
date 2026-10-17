"""Extract readable main content from an already-parsed HTML document.

No HTTP requests, database access, or mutations of the caller's soup tree.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re

from bs4 import BeautifulSoup, Comment, Declaration, Doctype, NavigableString, Tag


_REMOVE_TAGS = frozenset({
    "head", "script", "style", "noscript", "template", "nav", "footer", "aside",
    "form", "button", "input", "select", "textarea", "dialog", "iframe",
    "canvas", "svg", "menu",
})
_BLOCK_TAGS = frozenset({
    "address", "article", "blockquote", "dd", "div", "dl", "dt", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "ol", "p",
    "section", "table", "tbody", "tfoot", "th", "thead", "tr", "ul",
})
_NOISE_MARKERS = frozenset({
    "ad-banner", "advert", "advertisement", "breadcrumb", "breadcrumbs",
    "cookie-banner", "cookie-consent", "cookie-notice", "nav", "navbar",
    "navigation", "pagination", "related-posts", "share-buttons", "side-nav",
    "sidebar", "site-footer", "site-header", "site-nav", "skip-link",
    "social-share", "table-of-contents", "toc",
})
_NOISE_ROLES = frozenset({"navigation", "complementary", "contentinfo", "search"})
_HIDDEN_STYLE = re.compile(
    r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*"
    r"(?:!important)?\s*(?:;|$)",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    body: str
    headings: tuple[str, ...]
    code_blocks: tuple[str, ...]


def _is_noise(tag: Tag) -> bool:
    if tag.name in _REMOVE_TAGS:
        return True
    if tag.has_attr("hidden") or tag.has_attr("inert"):
        return True
    if str(tag.get("aria-hidden", "")).casefold() == "true":
        return True
    if str(tag.get("role", "")).casefold() in _NOISE_ROLES:
        return True
    if _HIDDEN_STYLE.search(str(tag.get("style", ""))):
        return True

    markers = [str(tag.get("id", "")).casefold()]
    markers.extend(str(name).casefold() for name in tag.get("class", []))
    return any(marker in _NOISE_MARKERS for marker in markers)


class _TextCollector:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.fragments: list[str] = []
        self.code_blocks: list[str] = []

    def _line_break(self) -> None:
        text = "".join(self.fragments)
        self.fragments.clear()
        text = _WHITESPACE.sub(" ", text).strip()
        if text:
            self.lines.append(text)

    def walk(self, node: Tag | NavigableString) -> None:
        if isinstance(node, (Comment, Declaration, Doctype)):
            return
        if isinstance(node, NavigableString):
            self.fragments.append(_WHITESPACE.sub(" ", str(node)))
            return
        if not isinstance(node, Tag):
            return
        if node.name == "br":
            self._line_break()
            return
        if node.name == "pre":
            self._line_break()
            code = node.get_text("", strip=False).replace("\r\n", "\n").replace("\r", "\n").strip("\n")
            if code.strip():
                self.code_blocks.append(code)
                self.lines.append(code)
            return

        is_block = node.name in _BLOCK_TAGS
        if is_block:
            self._line_break()
        if node.name in {"td", "th"} and node.find_previous_sibling(["td", "th"]) is not None:
            self.fragments.append(" | ")

        for child in node.children:
            self.walk(child)

        if is_block:
            self._line_break()

    def result(self, root: Tag) -> ExtractedContent:
        self.walk(root)
        self._line_break()
        headings = tuple(
            text
            for heading in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            if (text := _WHITESPACE.sub(" ", heading.get_text(" ", strip=True)).strip())
        )
        return ExtractedContent(
            body="\n".join(self.lines),
            headings=headings,
            code_blocks=tuple(self.code_blocks),
        )


def extract_main_content(soup: BeautifulSoup | Tag) -> ExtractedContent:
    """Return cleaned body text, headings and code blocks without changing soup."""
    if not isinstance(soup, Tag):
        raise TypeError("soup must be a BeautifulSoup or Tag instance")

    candidates = (
        soup.find("main"),
        soup.find(attrs={"role": "main"}),
        soup.find("article"),
        soup.body if isinstance(soup, BeautifulSoup) else None,
        soup,
    )
    for candidate in candidates:
        if not isinstance(candidate, Tag):
            continue
        working = deepcopy(candidate)
        for tag in list(working.find_all(True)):
            if tag.parent is not None and _is_noise(tag):
                tag.decompose()
        if _is_noise(working):
            continue
        extracted = _TextCollector().result(working)
        if extracted.body:
            return extracted

    return ExtractedContent(body="", headings=(), code_blocks=())
