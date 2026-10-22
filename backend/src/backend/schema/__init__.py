"""Public Pydantic schemas for Developers Eye's backend."""

from .crawl_attempt import CrawlAttemptCreate, CrawlAttemptRead, CrawlAttemptUpdate
from .crawler_frontier import CrawlTargetCreate, CrawlTargetRead, CrawlTargetUpdate
from .documents import DocumentCreate, DocumentRead, DocumentUpdate
from .robot_cache import RobotsCacheCreate, RobotsCacheRead, RobotsCacheUpdate
from .search_index import SearchIndexCreate, SearchIndexRead, SearchIndexUpdate
from .source import SourceCreate, SourceRead, SourceUpdate

__all__ = [
    "CrawlAttemptCreate", "CrawlAttemptRead", "CrawlAttemptUpdate",
    "CrawlTargetCreate", "CrawlTargetRead", "CrawlTargetUpdate",
    "DocumentCreate", "DocumentRead", "DocumentUpdate",
    "RobotsCacheCreate", "RobotsCacheRead", "RobotsCacheUpdate",
    "SearchIndexCreate", "SearchIndexRead", "SearchIndexUpdate",
    "SourceCreate", "SourceRead", "SourceUpdate",
]
