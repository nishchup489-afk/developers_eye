# Convert the scheme (HTTPS) to lowercase.
# Convert the hostname (EXAMPLE.COM) to lowercase.
# Remove URL fragments (#section).
# Remove default ports (:443 for HTTPS, :80 for HTTP).
# Preserve the path and query parameters.

# ===========================================================



import re

from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit


_HOST_LABEL = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)

_INVALID_PERCENT = re.compile(r"%(?![0-9a-fA-F]{2})")


def normalize_url(url: str) -> str:
    """Normalize an absolute HTTP(S) URL for deduplication."""

    # 1. Validate input
    if not isinstance(url, str) or not url:
        raise ValueError("URL must be a non-empty string")

    if any(
        char.isspace() or ord(char) < 32 or ord(char) == 127
        for char in url
    ) or "\\" in url:
        raise ValueError("URL contains invalid characters")

    # 2. Split URL
    try:
        parts = urlsplit(url)

        scheme = parts.scheme.lower()
        hostname = parts.hostname
        port = parts.port

    except ValueError as exc:
        raise ValueError("Malformed URL") from exc

    # 3. Validate scheme
    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS are supported")

    # 4. Validate hostname and credentials
    if not hostname:
        raise ValueError("URL must contain a hostname")

    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not allowed")

    if "%" in hostname:
        raise ValueError("Encoded hostnames or IPv6 zones are not supported")

    # 5. Normalize hostname
    try:
        ip = ip_address(hostname)
    except ValueError:
        try:
            host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("Invalid hostname") from exc

        if (
            not host
            or len(host) > 253
            or any(not _HOST_LABEL.fullmatch(label) for label in host.split("."))
        ):
            raise ValueError("Invalid hostname")
    else:
        host = (
            f"[{ip.compressed}]"
            if ip.version == 6
            else ip.compressed
        )

    # 6. Remove default ports
    if port == 0:
        raise ValueError("Invalid port")

    is_default_port = (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    )

    netloc = host

    if port is not None and not is_default_port:
        netloc = f"{host}:{port}"

    # 7. Normalize path
    path = parts.path or "/"

    # 8. Preserve query parameters
    query = parts.query

    if _INVALID_PERCENT.search(path) or _INVALID_PERCENT.search(query):
        raise ValueError("Invalid percent encoding")

    # 9. Reconstruct URL without fragment
    return urlunsplit((
        scheme,
        netloc,
        path,
        query,
        "",
    ))
