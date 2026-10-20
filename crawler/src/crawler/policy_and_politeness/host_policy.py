# I suggest this order:
# 1. URL + host validation: Pure Python, no HTTP or database access.
# 2. DNS/IP validation: Reject unsafe destinations and choose a safe HTTP connection strategy.
# 3. Robots policy: Fetch, parse, cache, and evaluate robots rules.
# 4. Politeness: Implement host-specific concurrency and timing restrictions.
# 5. Redirect handling: Reapply security and access checks at each hop.
# 6. Policy coordinator: Bring everything together for the fetch worker.


import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit


ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}

HOST_LABEL = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


def has_suspicious_characters(value: str) -> bool:
    return any(
        char == "\\"
        or char.isspace()
        or unicodedata.category(char) in {"Cc", "Cf"}
        for char in value
    )


def normalize_hostname(hostname: str) -> str | None:
    if not hostname or has_suspicious_characters(hostname):
        return None

    host = hostname.removesuffix(".")

    if not host:
        return None

    # Normalize IPv4 and IPv6 literals.
    try:
        return ipaddress.ip_address(host).compressed.lower()
    except ValueError:
        pass

    # Convert internationalized domain names to ASCII.
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None

    if len(host) > 253:
        return None

    # Validate individual DNS labels.
    labels = host.split(".")

    if not all(HOST_LABEL.fullmatch(label) for label in labels):
        return None

    return host


def is_allowed_host(
    url: str,
    allowed_hosts: list[str],
) -> bool:

    # 1. Reject empty or malformed input.
    if not isinstance(url, str) or not url:
        return False

    # 2. Reject whitespace, controls and backslashes.
    if has_suspicious_characters(url):
        return False

    # 3. Parse the URL.
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False

    # 4. Accept HTTP and HTTPS only.
    scheme = parsed.scheme.lower()

    if scheme not in ALLOWED_SCHEMES:
        return False

    # 5. Reject embedded credentials.
    if parsed.username is not None:
        return False

    if parsed.password is not None:
        return False

    # 6. Require a valid hostname.
    if not parsed.hostname:
        return False

    host = normalize_hostname(parsed.hostname)

    if host is None:
        return False

    # 7. Check the port.
    try:
        port = parsed.port
    except ValueError:
        return False

    # A trailing colon without a port is malformed.
    if parsed.netloc.endswith(":"):
        return False

    if port is not None and port != DEFAULT_PORTS[scheme]:
        return False

    # 8. Normalize configured allowed hosts.
    normalized_allowed_hosts = {
        normalized
        for allowed in allowed_hosts
        if isinstance(allowed, str)
        if (normalized := normalize_hostname(allowed)) is not None
    }

    # 9. Require exact hostname matching.
    return host in normalized_allowed_hosts


