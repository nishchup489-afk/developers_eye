"""Rule-based document classification for Developer's Eye.

Input:  NormalizedDocument from the processing normalizer.
Output: ClassificationResult from processing.schemas.

This module only classifies. It never fetches URLs, writes to the database,
modifies the input document, or authorizes a URL for crawling.

Confidence values are heuristic scores, NOT calibrated probabilities.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from crawler.processing.schemas import (
    ClassificationResult,
    DocumentType,
    NormalizedDocument,
)
from .utility import _metadata_string, _on_domain, _topic_tags

from .patterns import _TOPIC_PATTERNS
from .title import _DOCUMENTATION_TITLE , _TUTORIAL_TITLE

# Restrict topic tags to explicitly recognized developer technologies.
# Expand this small vocabulary as your index grows.





def classify_document(document: NormalizedDocument) -> ClassificationResult:
    """Classify one normalized document using conservative, deterministic rules.

    Strong signals (known URL structures) take priority over weak ones
    (title and metadata). Unknown pages become OTHER instead of a guess.

    The caller should handle noindex/empty documents before classification.
    """
    if not isinstance(document, NormalizedDocument):
        raise TypeError("document must be a NormalizedDocument")

    try:
        parsed_url = urlsplit(document.canonical_url)
        host = (parsed_url.hostname or "").lower().removeprefix("www.")
    except ValueError as exc:
        raise ValueError("document has an invalid canonical_url") from exc

    if parsed_url.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("document.canonical_url must be an absolute HTTP(S) URL")

    path = parsed_url.path.lower()
    segments = tuple(segment for segment in path.split("/") if segment)
    title = document.title or ""
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    tags = _topic_tags(document)

    def found(kind: DocumentType,
               score: float,
                 rule: str) -> ClassificationResult:
        return ClassificationResult(
            document_type=kind,
            confidence=score,
            tags=tags,
            method=f"rules:{rule}",
        )

    # 1. Explicit patterns for developer platforms: high-confidence signals.
    if _on_domain(host, "github.com"):
        if (len(segments) >= 4 and segments[2] == "issues"
                and segments[3].isdigit()):
            return found(DocumentType.ISSUE, 0.99, "github_issue")
        if (len(segments) >= 4 and segments[2] == "discussions"
                and segments[3].isdigit()):
            return found(DocumentType.DISCUSSION, 0.99, "github_discussion")
        # A two-segment GitHub URL generally identifies an owner/repository.
        # Exclude known site-wide routes before making that assumption.
        reserved = {
            "about", "apps", "collections", "enterprise", "explore",
            "features", "issues", "login", "marketplace", "notifications",
            "orgs", "pricing", "pulls", "search", "security", "settings",
            "signup", "site", "sponsors", "topics", "trending", "users",
        }
        if len(segments) == 2 and segments[0] not in reserved:
            return found(DocumentType.REPOSITORY, 0.97, "github_repository")

    if _on_domain(host, "gitlab.com"):
        if (len(segments) >= 5 and segments[-3] == "-"
                and segments[-2] == "issues" and segments[-1].isdigit()):
            return found(DocumentType.ISSUE, 0.98, "gitlab_issue")

    qa_host = (
        _on_domain(host, "stackoverflow.com")
        or _on_domain(host, "stackexchange.com")
        or _on_domain(host, "serverfault.com")
        or _on_domain(host, "superuser.com")
        or _on_domain(host, "askubuntu.com")
    )
    if qa_host and len(segments) >= 2 and segments[0] in {"q", "questions"} and segments[1].isdigit():
        return found(DocumentType.QUESTION, 0.99, "qa_question")

    if _on_domain(host, "reddit.com") and (
        len(segments) >= 4 and segments[0] == "r" and segments[2] == "comments"
    ):
        return found(DocumentType.DISCUSSION, 0.98, "reddit_discussion")

    # 2. Explicit tutorial URL paths can occur on documentation sites.
    if any(part in {"tutorial", "tutorials"} for part in segments):
        return found(DocumentType.TUTORIAL, 0.93, "tutorial_path")

    # 3. Documentation: dedicated, known documentation hosts or URL paths.
    documentation_host = (
        host.startswith("docs.")
        or _on_domain(host, "readthedocs.io")
        or _on_domain(host, "developer.mozilla.org")
        or _on_domain(host, "learn.microsoft.com")
        or _on_domain(host, "docs.rs")
    )
    if documentation_host:
        return found(DocumentType.DOCUMENTATION, 0.95, "documentation_host")

    if any(part in {"docs", "documentation", "reference", "api-reference"} for part in segments):
        return found(DocumentType.DOCUMENTATION, 0.88, "documentation_path")

    # 4. Events / hackathons. Exclude non-event Devpost project submissions.
    event_host = (
        _on_domain(host, "eventbrite.com")
        or _on_domain(host, "meetup.com")
    )
    if event_host and any(part in {"events", "event"} for part in segments):
        return found(DocumentType.EVENT, 0.93, "events_platform")
    if _on_domain(host, "devpost.com") and "hackathons" in segments:
        return found(DocumentType.EVENT, 0.95, "devpost_hackathon")
    if any(part in {"hackathon", "hackathons", "events"} for part in segments):
        return found(DocumentType.EVENT, 0.83, "event_path")

    # 5. Blog articles and tutorial guides.
    if any(part in {"blog", "blogs", "posts", "articles"} for part in segments):
        return found(DocumentType.BLOG, 0.89, "blog_path")
    if host.startswith("blog.") or _on_domain(host, "dev.to") or _on_domain(host, "medium.com"):
        return found(DocumentType.BLOG, 0.86, "blog_platform")
    if any(part in {"guide", "guides", "how-to"} for part in segments):
        return found(DocumentType.TUTORIAL, 0.77, "guide_path")

    # 6. Weak textual signals, used only after strong URL evidence.
    if _TUTORIAL_TITLE.search(title):
        return found(DocumentType.TUTORIAL, 0.72, "tutorial_title")
    if _DOCUMENTATION_TITLE.search(title):
        return found(DocumentType.DOCUMENTATION, 0.68, "documentation_title")

    og_type = _metadata_string(metadata, "og:type", "og_type")
    if og_type.casefold() == "article" or _metadata_string(
        metadata, "article:published_time", "published_time"
    ):
        return found(DocumentType.BLOG, 0.64, "article_metadata")

    # 7. Don't invent a category if the evidence is insufficient.
    return found(DocumentType.OTHER, 0.0, "no_match")


__all__ = ["classify_document"]
