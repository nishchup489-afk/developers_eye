r"""Run host-policy tests without pytest.

From the developers-eye repository root:
    $env:PYTHONPATH = (Resolve-Path '.\crawler\src').Path
    poetry -C crawler run python -m crawler.robot.tests.test_host_policy
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from colorama import Fore, Style, just_fix_windows_console

from crawler.policy_and_politeness.host_policy import (
    has_suspicious_characters,
    is_allowed_host,
    normalize_hostname,
)


HOSTS = ["docs.python.org"]

TestEntry = tuple[str, Callable[..., Any], tuple[Any, ...], Any]
TestGroup = tuple[str, list[TestEntry]]

TEST_GROUPS: list[TestGroup] = [
    (
        "Suspicious-character detection",
        [
            ("normal URL", has_suspicious_characters, ("https://docs.python.org/3/",), False),
            ("backslash", has_suspicious_characters, ("https://docs.python.org\\admin",), True),
            ("space", has_suspicious_characters, ("https://docs.python.org/ bad",), True),
            ("tab", has_suspicious_characters, ("https://docs.python.org/\tbad",), True),
            ("newline", has_suspicious_characters, ("https://docs.python.org/\nbad",), True),
            ("NUL control", has_suspicious_characters, ("foo\x00bar",), True),
            ("zero-width space", has_suspicious_characters, ("foo\u200bbar",), True),
            ("bidi override", has_suspicious_characters, ("foo\u202ebar",), True),
            ("percent-encoded space is not raw whitespace", has_suspicious_characters, ("/docs%20page",), False),
        ],
    ),
    (
        "Hostname normalization",
        [
            ("lowercase", normalize_hostname, ("DOCS.PYTHON.ORG",), "docs.python.org"),
            ("single trailing root dot", normalize_hostname, ("docs.python.org.",), "docs.python.org"),
            ("internationalized hostname", normalize_hostname, ("bücher.de",), "xn--bcher-kva.de"),
            ("IPv4 literal", normalize_hostname, ("8.8.8.8",), "8.8.8.8"),
            ("compressed IPv6 literal", normalize_hostname, ("2001:0db8:0000:0000:0000:0000:0000:0001",), "2001:db8::1"),
            ("empty hostname", normalize_hostname, ("",), None),
            ("root dot only", normalize_hostname, (".",), None),
            ("leading hyphen", normalize_hostname, ("-bad.example",), None),
            ("trailing hyphen", normalize_hostname, ("bad-.example",), None),
            ("underscore", normalize_hostname, ("bad_host.example",), None),
            ("empty DNS label", normalize_hostname, ("bad..example",), None),
            ("DNS label longer than 63", normalize_hostname, ("a" * 64 + ".com",), None),
            ("hostname longer than 253", normalize_hostname, ("a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 62 + ".com",), None),
            ("raw whitespace", normalize_hostname, ("docs .python.org",), None),
        ],
    ),
    (
        "Allowed-host URL validation",
        [
            ("approved HTTPS URL", is_allowed_host, ("https://docs.python.org/3/", HOSTS), True),
            ("approved HTTP URL", is_allowed_host, ("http://docs.python.org/3/", HOSTS), True),
            ("hostname case-insensitive", is_allowed_host, ("https://DOCS.PYTHON.ORG/3/", HOSTS), True),
            ("root dot", is_allowed_host, ("https://docs.python.org./3/", HOSTS), True),
            ("HTTPS port 443", is_allowed_host, ("https://docs.python.org:443/", HOSTS), True),
            ("HTTP port 80", is_allowed_host, ("http://docs.python.org:80/", HOSTS), True),
            ("normalized allowlist entries", is_allowed_host, ("https://docs.python.org/", ["DOCS.PYTHON.ORG."]), True),
            ("internationalized host matches IDNA allowlist", is_allowed_host, ("https://bücher.de/", ["xn--bcher-kva.de"]), True),
            ("IPv6 literal on explicit allowlist", is_allowed_host, ("http://[2001:db8::1]/", ["2001:db8::1"]), True),
            ("reject FTP", is_allowed_host, ("ftp://docs.python.org/", HOSTS), False),
            ("reject file scheme", is_allowed_host, ("file:///etc/passwd", HOSTS), False),
            ("reject missing scheme", is_allowed_host, ("docs.python.org/3/", HOSTS), False),
            ("reject empty URL", is_allowed_host, ("", HOSTS), False),
            ("reject non-string input", is_allowed_host, (None, HOSTS), False),
            ("reject missing hostname", is_allowed_host, ("https:///3/", HOSTS), False),
            ("reject unrelated host", is_allowed_host, ("https://evil.example/", HOSTS), False),
            ("reject deceptive suffix", is_allowed_host, ("https://docs.python.org.evil.example/", HOSTS), False),
            ("reject unlisted subdomain", is_allowed_host, ("https://sub.docs.python.org/", HOSTS), False),
            ("reject username", is_allowed_host, ("https://user@docs.python.org/", HOSTS), False),
            ("reject username and password", is_allowed_host, ("https://user:pass@docs.python.org/", HOSTS), False),
            ("reject empty username", is_allowed_host, ("https://@docs.python.org/", HOSTS), False),
            ("reject confusing userinfo", is_allowed_host, ("https://docs.python.org@evil.example/", HOSTS), False),
            ("reject unsupported port", is_allowed_host, ("https://docs.python.org:8443/", HOSTS), False),
            ("reject wrong default port", is_allowed_host, ("http://docs.python.org:443/", HOSTS), False),
            ("reject alphabetic port", is_allowed_host, ("https://docs.python.org:abc/", HOSTS), False),
            ("reject out-of-range port", is_allowed_host, ("https://docs.python.org:99999/", HOSTS), False),
            ("reject empty port", is_allowed_host, ("https://docs.python.org:/", HOSTS), False),
            ("reject malformed IPv6 bracket", is_allowed_host, ("http://[::1/", ["::1"]), False),
            ("reject raw backslash", is_allowed_host, ("https://docs.python.org\\admin", HOSTS), False),
            ("reject newline", is_allowed_host, ("https://docs.python.org/\nadmin", HOSTS), False),
            ("reject zero-width character", is_allowed_host, ("https://docs.python.org/\u200badmin", HOSTS), False),
            ("reject empty allowlist", is_allowed_host, ("https://docs.python.org/", []), False),
            ("ignore invalid allowlist entry", is_allowed_host, ("https://docs.python.org/", ["-bad.example", "docs.python.org"]), True),
        ],
    ),
]


def main() -> int:
    just_fix_windows_console()
    passed = 0
    failed = 0

    for title, tests in TEST_GROUPS:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        for name, function, args, expected in tests:
            try:
                actual = function(*args)
            except Exception as exc:
                failed += 1
                print(f"{Fore.RED}[FAIL]{Style.RESET_ALL} {name}: {type(exc).__name__}: {exc}")
                continue

            if actual != expected:
                failed += 1
                print(f"{Fore.RED}[FAIL]{Style.RESET_ALL} {name}: expected {expected!r}, got {actual!r}")
            else:
                passed += 1
                print(f"{Fore.GREEN}[PASS]{Style.RESET_ALL} {name}")

    color = Fore.GREEN if failed == 0 else Fore.RED
    print(f"\n{color}{passed} passed, {failed} failed{Style.RESET_ALL}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
