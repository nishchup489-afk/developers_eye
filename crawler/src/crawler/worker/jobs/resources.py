"""Resource-type dispatch and fetch outcomes; no database or network operations."""
from dataclasses import dataclass, replace

from crawler.parser.schemas import DiscoveredLink
from crawler.policy_and_politeness.host_policy import is_allowed_host
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.worker.jobs.constants import _HTML_MEDIA_TYPES
from crawler.worker.jobs.schemas import JobOutcome, TargetAction
from crawler.worker.jobs.utility import _add_x_robots, _x_robots_directives


@dataclass(frozen=True, slots=True)
class ResponsePlan:
    action: TargetAction
    outcome: JobOutcome
    message: str
    parseable: bool = False


def plan_response(fetched, *, kind, allowed_hosts, scope, depth):
    status = fetched.status_code
    if fetched.decision == RobotsDecision.DENY:
        return ResponsePlan("block", "blocked", fetched.reason)
    if fetched.decision == RobotsDecision.DEFER:
        return ResponsePlan("retry", "failed", fetched.reason)
    if fetched.decision != RobotsDecision.ALLOW:
        raise RuntimeError(f"Unexpected policy decision: {fetched.decision!r}")
    if status == 304:
        return ResponsePlan("complete", "not_modified", fetched.reason)
    if status in (401, 403):
        return ResponsePlan("block", "blocked", fetched.reason)
    if status in (204, 205):
        return ResponsePlan("complete", "success", f"HTTP {status}: no content")
    if status in (404, 410):
        return ResponsePlan("complete", "failed", f"HTTP {status}: resource unavailable")
    if status != 200:
        return ResponsePlan("retry", "failed", f"Unhandled HTTP status: {status}")
    mime_type = next((value for key, value in fetched.headers.items() if key.lower() == "content-type"), "").split(";", 1)[0].strip().casefold()
    if not is_allowed_host(fetched.final_url, list(allowed_hosts)) or (kind == "page" and not scope.allows(fetched.final_url, depth)):
        return ResponsePlan("block", "blocked", "Final URL exceeds the source host or path scope")
    if kind == "page" and mime_type not in _HTML_MEDIA_TYPES:
        return ResponsePlan("complete", "success", f"Skipped unsupported MIME: {mime_type or '(none)'}")
    if not fetched.body:
        return ResponsePlan("retry", "failed", "HTTP 200 response had empty body")
    return ResponsePlan("complete", "success", fetched.reason, True)


def parse_resource(*, parser, kind, fetched, content_type, allowed_hosts, scope,
                   api_options, follow_entry_links, discover_sitemaps):
    parsed = parser(url=fetched.final_url, content=fetched.body, content_type=content_type,
                    **({"options": api_options} if kind == "api" else {}))
    if kind in {"rss", "api"}:
        parsed = replace(parsed,
            documents=tuple(d for d in parsed.documents if is_allowed_host(d.url, list(allowed_hosts)) and scope.allows(d.url, 0)),
            discovered_links=tuple(link for link in parsed.discovered_links if link.kind != "page" or follow_entry_links))
    parsed = _add_x_robots(parsed, fetched.headers)
    if discover_sitemaps:
        parsed = replace(parsed, discovered_links=tuple(
            DiscoveredLink(url=value, kind="sitemap") for value in fetched.sitemap_urls
        ) + parsed.discovered_links)
    if set(_x_robots_directives(fetched.headers)) & {"nofollow", "none"}:
        parsed = replace(parsed, discovered_links=())
    return parsed
