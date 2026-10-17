
"""Exceptions raised by Developer's Eye content parsers."""


class ParserError(Exception):
    """Base exception for content parsing failures."""


class UnsupportedContentTypeError(ParserError):
    """The response content type has no supported parser."""


class ContentDecodeError(ParserError):
    """The response body could not be decoded correctly."""


class MalformedContentError(ParserError):
    """The response content is invalid or cannot be parsed."""
