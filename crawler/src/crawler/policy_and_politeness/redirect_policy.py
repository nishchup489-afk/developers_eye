"""Redirect handling for the Developer's Eye HTTP(S) crawler.

This module *does not* fetch pages or approve redirect destinations. It only
validates and resolves Location headers, detects loops, and limits hop counts.

For EVERY URL returned by RedirectTracker.next_url(), the coordinator MUST
re-run host allowlist, DNS/IP safety, robots, and politeness checks, then fetch
through the IP-pinned safe transport. Disable automatic HTTP redirects.

The crawler is GET-only; this module does not implement method rewriting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

from crawler.frontier.urls import normalize_url


REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
DEFAULT_MAX_REDIRECTS = 5


class RedirectPolicyError(ValueError):
    """Base error for a rejected redirect or redirect chain."""


class InvalidRedirectError(RedirectPolicyError):
    """A Location header or destination URL is missing or malformed."""


class RedirectLoopError(RedirectPolicyError):
    """A redirect targets a URL that has already been visited."""


class RedirectLimitError(RedirectPolicyError):
    """A redirect would exceed the configured maximum number of hops."""


class RedirectDowngradeError(RedirectPolicyError):
    """An HTTPS URL redirects to an insecure HTTP URL."""


def is_redirect(status_code: int) -> bool:
    """True for the HTTP redirects that this GET-only crawler follows."""
    return status_code in REDIRECT_STATUS_CODES


def _check_chars(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise InvalidRedirectError(f"{name} must be a non-empty string")
    # urlsplit() can silently strip some controls; reject before parsing.
    if any(c == "\\" or c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise InvalidRedirectError(f"{name} contains unsafe characters")


def _check_absolute_http_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        # Accessing .port and .hostname can raise on malformed authorities.
        port = parts.port
        hostname = parts.hostname
        username = parts.username
        password = parts.password
    except ValueError as exc:
        raise InvalidRedirectError("Malformed URL authority or port") from exc

    if parts.scheme.lower() not in ("http", "https") or not parts.netloc or not hostname:
        raise InvalidRedirectError("Only absolute HTTP(S) URLs are permitted")
    if username is not None or password is not None:
        raise InvalidRedirectError("Credentials in URLs are prohibited")
    if "%" in hostname:
        raise InvalidRedirectError("Encoded or scoped hostnames are prohibited")
    if parts.netloc.endswith(":") or (port is not None and port == 0):
        raise InvalidRedirectError("Invalid URL port")


def validate_redirect_url(url: str) -> str:
    """Validate an absolute redirect destination and return its canonical URL.

    This is syntactic validation only. It does NOT validate allowed hosts or IPs.
    """
    _check_chars(url, "url")
    _check_absolute_http_url(url)
    try:
        canonical = normalize_url(url)
    except (TypeError, ValueError) as exc:
        raise InvalidRedirectError("URL normalization failed") from exc
    _check_chars(canonical, "normalized URL")
    _check_absolute_http_url(canonical)
    # Fragment identifiers never reach the HTTP server and should not defeat
    # loop detection, even if normalize_url happens to preserve them.
    return urldefrag(canonical).url


def resolve_redirect(current_url: str, location: str | None) -> str:
    """Resolve an HTTP Location header (absolute, relative, or //host/path).

    The returned URL is a *candidate*, not permission to fetch it.
    """
    current = validate_redirect_url(current_url)
    _check_chars(location, "Location")

    try:
        reference = urlsplit(location)
    except ValueError as exc:
        raise InvalidRedirectError("Malformed Location header") from exc

    # Reject malformed scheme-like references (e.g. https:/example.com),
    # rather than letting urljoin reinterpret them as relative paths.
    if reference.scheme and (
        reference.scheme.lower() not in ("http", "https") or not reference.netloc
    ):
        raise InvalidRedirectError("Unsupported or malformed Location scheme")

    return validate_redirect_url(urljoin(current, location))


@dataclass(slots=True)
class RedirectTracker:
    """Track one GET request's redirect chain; create one per initial URL.

    Call next_url() only after receiving a supported redirect response. Its
    returned URL must be approved by the policy coordinator before fetching.
    """

    start_url: str
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allow_https_downgrade: bool = False
    current_url: str = field(init=False)
    redirect_count: int = field(init=False, default=0)
    _visited: set[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_redirects, bool)
            or not isinstance(self.max_redirects, int)
            or self.max_redirects < 0
        ):
            raise ValueError("max_redirects must be a non-negative integer")
        if not isinstance(self.allow_https_downgrade, bool):
            raise ValueError("allow_https_downgrade must be a boolean")
        self.current_url = validate_redirect_url(self.start_url)
        self._visited = {self.current_url}

    def next_url(self, status_code: int, location: str | None) -> str:
        """Return and record the next redirect destination, or raise.

        Does NOT execute a request. Do not call this for a non-redirect response.
        """
        if not is_redirect(status_code):
            raise RedirectPolicyError(f"HTTP {status_code} is not a followed redirect")
        if self.redirect_count >= self.max_redirects:
            raise RedirectLimitError(f"Exceeded {self.max_redirects} redirects")

        candidate = resolve_redirect(self.current_url, location)
        previous_scheme = urlsplit(self.current_url).scheme.lower()
        candidate_scheme = urlsplit(candidate).scheme.lower()
        if (
            not self.allow_https_downgrade
            and previous_scheme == "https"
            and candidate_scheme == "http"
        ):
            raise RedirectDowngradeError("HTTPS to HTTP redirect is prohibited")
        if candidate in self._visited:
            raise RedirectLoopError(f"Redirect loop detected at {candidate}")

        self.redirect_count += 1
        self.current_url = candidate
        self._visited.add(candidate)
        return candidate
