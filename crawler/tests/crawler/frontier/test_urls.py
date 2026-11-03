
import pytest

from crawler.frontier.urls import normalize_url


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        (
            "HTTPS://EXAMPLE.COM:443/docs?lang=en#intro",
            "https://example.com/docs?lang=en",
        ),
        (
            "http://EXAMPLE.com:80",
            "http://example.com/",
        ),
        (
            "https://example.com:8443/docs",
            "https://example.com:8443/docs",
        ),
        (
            "https://example.com/docs#section",
            "https://example.com/docs",
        ),
        (
            "https://example.com/?page=2&sort=new",
            "https://example.com/?page=2&sort=new",
        ),
        (
            "https://[2001:db8::1]:443/docs",
            "https://[2001:db8::1]/docs",
        ),
    ],
)
def test_normalize_url(original: str, expected: str) -> None:
    assert normalize_url(original) == expected


@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "javascript:alert(1)",
        "ftp://example.com",
        "https://",
        "https://user:password@example.com",
        "https://example.com:invalid/",
        "https://example.com:99999/",
        "https://example.com:0/",
        "https://example.com/%ZZ",
    ],
)
def test_invalid_url(invalid_url: str) -> None:
    with pytest.raises(ValueError):
        normalize_url(invalid_url)


def test_idempotency() -> None:
    url = "HTTPS://EXAMPLE.COM:443/docs#intro"

    once = normalize_url(url)
    twice = normalize_url(once)

    assert once == twice
