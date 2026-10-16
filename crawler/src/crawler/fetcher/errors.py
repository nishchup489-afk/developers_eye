"""Fetcher exceptions shared with PolicyCoordinator.

Import ResponseTooLargeError and FetcherSecurityError from this module inside
PolicyCoordinator; do not define second classes with the same names there.
"""


class ResponseTooLargeError(ValueError):
    """The response exceeds the authorized decoded-body size limit."""


class FetcherSecurityError(ValueError):
    """The requested transport, destination, or response encoding is unsafe."""
