"""Explicit, bounded HTML crawl scope for one source."""
from dataclasses import dataclass
from posixpath import normpath
from urllib.parse import unquote, urlsplit

DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_PAGES = 10_000


def _path(value: str) -> str:
    return normpath('/' + unquote(value).lstrip('/'))


@dataclass(frozen=True, slots=True)
class CrawlScope:
    max_depth: int = DEFAULT_MAX_DEPTH
    max_pages: int = DEFAULT_MAX_PAGES
    allowed_path_prefixes: tuple[str, ...] = ('/',)

    @classmethod
    def from_config(cls, config: dict) -> 'CrawlScope':
        depth, pages = config.get('max_depth', DEFAULT_MAX_DEPTH), config.get('max_pages', DEFAULT_MAX_PAGES)
        if type(depth) is not int or not 0 <= depth <= 100:
            raise ValueError('max_depth must be an integer between 0 and 100')
        if type(pages) is not int or not 1 <= pages <= 1_000_000:
            raise ValueError('max_pages must be an integer between 1 and 1000000')
        prefixes = config.get('allowed_path_prefixes', ['/'])
        if not isinstance(prefixes, list) or not prefixes or any(
            not isinstance(p, str) or not p.startswith('/') or any(c in p for c in '?#\\')
            or any(c.isspace() or ord(c) < 32 for c in p) for p in prefixes
        ):
            raise ValueError('allowed_path_prefixes must contain absolute URL paths')
        return cls(depth, pages, tuple(_path(p) for p in prefixes))

    def allows(self, url: str, depth: int) -> bool:
        path = _path(urlsplit(url).path)
        return 0 <= depth <= self.max_depth and any(
            prefix == '/' or path == prefix or path.startswith(prefix.rstrip('/') + '/')
            for prefix in self.allowed_path_prefixes
        )
