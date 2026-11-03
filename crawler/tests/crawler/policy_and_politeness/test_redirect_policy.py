"""Unit tests for Developer's Eye redirect_policy.py.

Run from the crawler project (after installing it into the environment):
    poetry run pytest tests/test_redirect_policy.py -v

These are pure unit tests: no database or real HTTP requests are needed.
"""

import pytest

from crawler.policy_and_politeness.redirect_policy import (
    DEFAULT_MAX_REDIRECTS,
    InvalidRedirectError,
    RedirectDowngradeError,
    RedirectLimitError,
    RedirectLoopError,
    RedirectPolicyError,
    RedirectTracker,
    is_redirect,
    resolve_redirect,
    validate_redirect_url,
)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_supported_redirect_status(status: int) -> None:
    assert is_redirect(status) is True


@pytest.mark.parametrize("status", [200, 204, 300, 304, 305, 306, 3070, 400, 429, 500])
def test_non_redirect_status(status: int) -> None:
    assert is_redirect(status) is False


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("/docs", "https://example.com/docs"),
        ("../new", "https://example.com/new"),
        ("child", "https://example.com/a/child"),
        ("?page=2", "https://example.com/a/b?page=2"),
        ("#section", "https://example.com/a/b"),
        ("/docs#intro", "https://example.com/docs"),
        ("//docs.example.com/start", "https://docs.example.com/start"),
        ("https://another.example.com/guide", "https://another.example.com/guide"),
    ],
)
def test_resolve_location_header(location: str, expected: str) -> None:
    assert resolve_redirect("https://example.com/a/b", location) == expected


def test_url_normalization() -> None:
    result = validate_redirect_url("HTTPS://EXAMPLE.COM:443/Docs#section")
    assert result == "https://example.com/Docs"


def test_query_string_preserved() -> None:
    assert (
        validate_redirect_url("https://example.com/search?q=python#top")
        == "https://example.com/search?q=python"
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        " ",
        "https://",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "http://user:pass@example.com/path",
        "https://@example.com/path",
        "https://example.com:bad/path",
        "https://example.com:65536/path",
        "https://example.com:0/path",
        "https://example.com:/path",
        "https://[::1/path",
        "https://[fe80::1%25eth0]/path",
        "https://example.com/has space",
        "https://example.com/has\t tab",
        "https://example.com/\nheader",
        "https://example.com\\@malicious.example/path",
    ],
)
def test_reject_unsafe_absolute_urls(url: str) -> None:
    with pytest.raises(InvalidRedirectError):
        validate_redirect_url(url)


@pytest.mark.parametrize(
    "location",
    [
        None,
        "",
        "javascript:alert(1)",
        "data:text/plain,hello",
        "ftp://example.com/file",
        "http:/example.com/path",
        "https:example.com/path",
        "https://user:pass@example.com/path",
        "https://example.com:99999/path",
        "/unsafe path",
        "/unsafe\nheader",
        "\\evil.example/path",
    ],
)
def test_reject_invalid_location_header(location: str | None) -> None:
    with pytest.raises(InvalidRedirectError):
        resolve_redirect("https://example.com/docs", location)


def test_default_limit_is_five_hops() -> None:
    assert DEFAULT_MAX_REDIRECTS == 5
    tracker = RedirectTracker("https://example.com/start")

    for hop in range(1, 6):
        assert tracker.next_url(302, f"/page{hop}") == f"https://example.com/page{hop}"

    with pytest.raises(RedirectLimitError):
        tracker.next_url(302, "/page6")

    assert tracker.redirect_count == 5
    assert tracker.current_url == "https://example.com/page5"


def test_custom_redirect_limit() -> None:
    tracker = RedirectTracker("https://example.com/start", max_redirects=1)
    assert tracker.next_url(301, "/next") == "https://example.com/next"

    with pytest.raises(RedirectLimitError):
        tracker.next_url(301, "/last")

    assert tracker.redirect_count == 1


def test_zero_redirect_limit() -> None:
    tracker = RedirectTracker("https://example.com/start", max_redirects=0)
    with pytest.raises(RedirectLimitError):
        tracker.next_url(301, "/next")


def test_self_redirect_is_loop() -> None:
    tracker = RedirectTracker("https://example.com/start")
    with pytest.raises(RedirectLoopError):
        tracker.next_url(301, "/start")
    assert tracker.current_url == "https://example.com/start"
    assert tracker.redirect_count == 0


def test_fragment_cannot_hide_redirect_loop() -> None:
    tracker = RedirectTracker("https://example.com/start")
    with pytest.raises(RedirectLoopError):
        tracker.next_url(302, "/start#different-fragment")
    assert tracker.redirect_count == 0


def test_multi_hop_redirect_loop() -> None:
    tracker = RedirectTracker("https://example.com/a")
    tracker.next_url(301, "/b")
    tracker.next_url(302, "/c")

    with pytest.raises(RedirectLoopError):
        tracker.next_url(307, "/a")

    assert tracker.redirect_count == 2
    assert tracker.current_url == "https://example.com/c"


def test_https_to_http_downgrade_rejected() -> None:
    tracker = RedirectTracker("https://example.com/start")
    with pytest.raises(RedirectDowngradeError):
        tracker.next_url(301, "http://example.com/destination")
    assert tracker.redirect_count == 0
    assert tracker.current_url == "https://example.com/start"


def test_explicitly_allow_https_downgrade() -> None:
    tracker = RedirectTracker(
        "https://example.com/start",
        allow_https_downgrade=True,
    )
    assert tracker.next_url(301, "http://example.com/destination") == (
        "http://example.com/destination"
    )


def test_http_to_https_upgrade_is_allowed() -> None:
    tracker = RedirectTracker("http://example.com/start")
    assert tracker.next_url(308, "https://example.com/destination") == (
        "https://example.com/destination"
    )


def test_https_to_https_cross_host_is_syntactically_allowed() -> None:
    tracker = RedirectTracker("https://example.com/start")
    assert tracker.next_url(302, "https://docs.example.com/next") == (
        "https://docs.example.com/next"
    )
    # Cross-host permissions must still be enforced by Policy Coordinator.


def test_private_ip_is_not_rejected_by_syntax_validation() -> None:
    assert resolve_redirect(
        "https://example.com/start", "http://127.0.0.1/admin"
    ) == "http://127.0.0.1/admin"
    # DNS/IP Policy, NOT Redirect Policy, must reject the private destination.


def test_non_redirect_status_does_not_change_tracker_state() -> None:
    tracker = RedirectTracker("https://example.com/start")
    with pytest.raises(RedirectPolicyError):
        tracker.next_url(200, "/new")
    assert tracker.redirect_count == 0
    assert tracker.current_url == "https://example.com/start"


def test_bad_location_does_not_change_tracker_state() -> None:
    tracker = RedirectTracker("https://example.com/start")
    with pytest.raises(InvalidRedirectError):
        tracker.next_url(302, "javascript:alert(1)")
    assert tracker.redirect_count == 0
    assert tracker.current_url == "https://example.com/start"


@pytest.mark.parametrize("invalid", [-1, 1.5, True, None])
def test_invalid_max_redirects(invalid: object) -> None:
    with pytest.raises(ValueError):
        RedirectTracker("https://example.com/start", max_redirects=invalid)


@pytest.mark.parametrize("invalid", [0, 1, "false", None])
def test_invalid_https_downgrade_setting(invalid: object) -> None:
    with pytest.raises(ValueError):
        RedirectTracker(
            "https://example.com/start",
            allow_https_downgrade=invalid,
        )


def test_trackers_are_independent() -> None:
    first = RedirectTracker("https://example.com/start")
    second = RedirectTracker("https://example.com/start")
    first.next_url(301, "/other")
    assert first.redirect_count == 1
    assert second.redirect_count == 0
    assert second.current_url == "https://example.com/start"
