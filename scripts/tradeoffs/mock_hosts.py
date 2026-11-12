"""A local stand-in for many documentation hosts, for crawler load tests.

  python scripts/tradeoffs/mock_hosts.py --port 80 --capacity 24

Every hostname ending in .bench is served by this one process (the crawler
benchmark points DNS for *.bench at 127.0.0.1). It behaves like a modest
real site, so overload shows up the way it would in production:

- 40-250 ms response time per page (uniform random, seeded per path);
- HTTP 429 when one host is asked again within --min-gap seconds (a polite
  crawler at 2 s per host never triggers it; it counts as a politeness violation);
- HTTP 503 when more than --capacity requests are in flight across all hosts;
- unique 4-8 KB documentation-like HTML per path, which changes between
  "epochs" for --change-percent of pages (recrawl experiments).

GET http://control.bench/__stats returns counters; POST /__epoch/N sets the epoch.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import time
from collections import Counter

WORDS = ("async await request response handler middleware router schema query index cache "
         "connection pool timeout retry session token config deploy container volume network "
         "cluster replica migration transaction commit rollback cursor iterator generator closure "
         "decorator module package import export interface generic template compile runtime thread "
         "process signal socket stream buffer encode decode serialize parse validate render "
         "component state props hook effect reducer selector event listener callback promise").split()


def page(host: str, path: str, epoch: int, change_percent: int) -> bytes:
    key = f"{host}{path}"
    bucket = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100
    version = epoch if bucket < change_percent else 0
    rng = random.Random(f"{key}#{version}")
    title = " ".join(rng.choice(WORDS).capitalize() for _ in range(4))
    paragraphs = []
    for _ in range(rng.randint(6, 12)):
        sentence = lambda: " ".join(rng.choice(WORDS) for _ in range(rng.randint(8, 16))).capitalize() + "."
        paragraphs.append("<p>" + " ".join(sentence() for _ in range(rng.randint(3, 6))) + "</p>")
    code = "\n".join(f"def {rng.choice(WORDS)}_{i}({rng.choice(WORDS)}):\n    return {rng.choice(WORDS)}"
                     for i in range(rng.randint(2, 5)))
    body = (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{title} | {host} docs</title>"
            f"<meta name=\"description\" content=\"{title} reference\"></head><body><main><article>"
            f"<h1>{title}</h1>{''.join(paragraphs[:3])}<h2>Example</h2><pre><code class=\"language-python\">{code}"
            f"</code></pre>{''.join(paragraphs[3:])}<p>Revision {version}.</p></article></main></body></html>")
    return body.encode()


class App:
    def __init__(self, capacity: int, min_gap: float, change_percent: int):
        self.capacity, self.min_gap, self.change_percent = capacity, min_gap, change_percent
        self.in_flight = 0
        self.last: dict[str, float] = {}
        self.min_seen_gap: dict[str, float] = {}
        self.stats: Counter[str] = Counter()
        self.epoch = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode().split(":")[0].lower()
        path = scope["path"]

        async def reply(status: int, body: bytes, ctype: str = "text/html; charset=utf-8", extra=()):
            self.stats[f"status_{status}"] += 1
            self.stats["bytes_sent"] += len(body)
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", ctype.encode()), (b"content-length", str(len(body)).encode()), *extra]})
            await send({"type": "http.response.body", "body": body})

        if host == "control.bench":
            if path.startswith("/__epoch/"):
                self.epoch = int(path.rsplit("/", 1)[1])
            if path == "/__reset":
                self.stats.clear()
                self.min_seen_gap.clear()
            gaps = sorted(g for g in self.min_seen_gap.values() if g != float("inf"))
            return await reply(200, json.dumps({
                **self.stats, "epoch": self.epoch, "hosts_seen": len(self.min_seen_gap),
                "smallest_gap_seconds": round(gaps[0], 3) if gaps else None}).encode(), "application/json")

        now = time.monotonic()
        if path != "/robots.txt":
            previous = self.last.get(host)
            self.last[host] = now
            if previous is not None:
                gap = now - previous
                self.min_seen_gap[host] = min(self.min_seen_gap.get(host, gap), gap)
                if gap < self.min_gap:
                    self.stats["politeness_violations"] += 1
                    return await reply(429, b"slow down", extra=[(b"retry-after", b"5")])
            else:
                self.min_seen_gap.setdefault(host, float("inf"))
        if self.in_flight >= self.capacity:
            return await reply(503, b"busy", extra=[(b"retry-after", b"2")])
        self.in_flight += 1
        try:
            await asyncio.sleep(random.Random(f"{host}{path}").uniform(0.04, 0.25))
            if path == "/robots.txt":
                return await reply(200, b"User-agent: *\nAllow: /\n", "text/plain")
            if path.endswith(".xml"):
                return await reply(404, b"not found")
            return await reply(200, page(host, path, self.epoch, self.change_percent))
        finally:
            self.in_flight -= 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--capacity", type=int, default=24)
    parser.add_argument("--min-gap", type=float, default=1.0)
    parser.add_argument("--change-percent", type=int, default=16)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(App(args.capacity, args.min_gap, args.change_percent), host="127.0.0.1", port=args.port,
                log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
