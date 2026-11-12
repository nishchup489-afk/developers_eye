"""Search trade-offs 4-5 over real HTTP: concurrency and the timeout budget.

From the repository root:

  python backend/scripts/tradeoffs/http_bench.py concurrency --users 1 10 25 50 100 --seconds 20
  python backend/scripts/tradeoffs/http_bench.py timeout --deadlines 1000 2000 5000 --users 25 --seconds 30

Starts its own uvicorn (one worker, like deploy/docker-compose.yml) on the
benchmark database with the production API pool (DB_POOL_SIZE=8,
DB_MAX_OVERFLOW=2) and the default in-process cap SEARCH_MAX_CONCURRENT=16.
The per-client rate limit is raised out of the way because every simulated
user comes from 127.0.0.1; everything else is the live request path.

Users are a closed loop: each user sends a request, waits for the answer, and
sends the next one at once (no think time). Requests/sec is completed
responses of any status divided by the measured window.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PORT = 8765


def query_mix() -> list[dict[str, str]]:
    """Real queries from the evaluation sets plus short common terms (the DF-heavy case)."""
    queries, _ = common.load_checklist_queries()
    human = json.loads((common.REPO_ROOT / "backend/src/backend/search/evaluation/human_judging_queries.json")
                       .read_text(encoding="utf-8"))["queries"]
    mix = [{"q": q["query"], "mode": q["mode"]} for q in queries + human]
    for word in ["python", "docker", "react", "api", "error", "install", "config", "function",
                 "database", "test", "async", "server", "http", "json", "linux", "build"]:
        mix.append({"q": word, "mode": "all"})
    return mix


def start_server(url: str, extra_env: dict[str, str]) -> subprocess.Popen:
    env = {**os.environ, "DATABASE_URL": url, "DB_POOL_SIZE": "8", "DB_MAX_OVERFLOW": "2",
           "SEARCH_RATE_LIMIT_PER_MINUTE": "100000000", "SEARCH_RATE_LIMIT_BURST": "100000000",
           "AI_OVERVIEW": "false", "API_DOCS_ENABLED": "false", **extra_env}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--workers", "1", "--log-level", "warning", "--no-access-log"],
        cwd=common.REPO_ROOT / "backend", env=env)
    import httpx
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2).status_code == 200:
                return proc
        except Exception:
            pass
        if proc.poll() is not None:
            raise RuntimeError("uvicorn exited during startup")
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("uvicorn did not become healthy")


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


async def load(users: int, seconds: float, mix, seed: int = 7) -> dict:
    import httpx
    rng = random.Random(seed)
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    stop_at = time.perf_counter() + seconds
    limits = httpx.Limits(max_connections=users + 5, max_keepalive_connections=users + 5)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORT}", limits=limits, timeout=30) as client:
        async def user(index: int) -> None:
            local = random.Random(rng.random() + index)
            while time.perf_counter() < stop_at:
                item = local.choice(mix)
                started = time.perf_counter()
                try:
                    response = await client.get("/search", params={"q": item["q"], "mode": item["mode"], "limit": 20})
                    statuses[str(response.status_code)] += 1
                except httpx.HTTPError as exc:
                    statuses[type(exc).__name__] += 1
                latencies.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        await asyncio.gather(*(user(i) for i in range(users)))
        window = time.perf_counter() - started
    total = sum(statuses.values())
    ok = statuses.get("200", 0)
    ok_latency = latencies  # all responses, including fast 503 rejections
    return {
        "users": users, "window_seconds": round(window, 2), "requests": total,
        "requests_per_second": round(total / window, 2),
        "successful_per_second": round(ok / window, 2),
        "error_rate": round((total - ok) / total, 4) if total else None,
        "status_counts": dict(statuses), "latency_all_responses": common.summarize(ok_latency),
    }


def server_cpu(pid: int) -> float:
    """CPU of the server and its children: on Windows a venv's python.exe is a
    launcher that runs the real interpreter as a child process."""
    import psutil
    root = psutil.Process(pid)
    total = 0.0
    for proc in [root] + root.children(recursive=True):
        try:
            times = proc.cpu_times()
            total += times.user + times.system
        except psutil.Error:
            pass
    return total


async def bench_concurrency(args, url):
    mix = query_mix()
    proc = start_server(url, {})
    try:
        await load(4, 10, mix)  # warm the DF cache and PostgreSQL buffers once
        results = []
        for users in args.users:
            before = server_cpu(proc.pid)
            with common.ResourceSampler(extra_pids=[proc.pid]) as sampler:
                row = await load(users, args.seconds, mix)
            row["api_process_cpu_cores"] = round((server_cpu(proc.pid) - before) / row["window_seconds"], 3)
            row["resources"] = sampler.report()
            results.append(row)
            print(users, row["requests_per_second"], row["latency_all_responses"].get("p95_ms"), row["status_counts"], flush=True)
    finally:
        stop_server(proc)
    common.write_report("04-search-concurrency", {
        "server": "uvicorn 1 worker, DB_POOL_SIZE=8, DB_MAX_OVERFLOW=2, SEARCH_MAX_CONCURRENT=16, deadline 3000/4000 ms",
        "query_mix_size": len(mix), "levels": results}, args.output)


async def bench_timeout(args, url):
    mix = query_mix()
    results = []
    for deadline in args.deadlines:
        proc = start_server(url, {"SEARCH_QUERY_DEADLINE_MS": str(deadline),
                                  "SEARCH_TOTAL_DEADLINE_MS": str(deadline + 1000)})
        try:
            before = server_cpu(proc.pid)
            with common.ResourceSampler(extra_pids=[proc.pid]) as sampler:
                row = await load(args.users[0], args.seconds, mix)
            row["api_process_cpu_cores"] = round((server_cpu(proc.pid) - before) / row["window_seconds"], 3)
        finally:
            stop_server(proc)
        codes = row["status_counts"]
        row["statement_deadline_ms"] = deadline
        row["total_deadline_ms"] = deadline + 1000
        row["timeout_rate"] = round(codes.get("504", 0) / row["requests"], 4)
        row["completed_queries"] = codes.get("200", 0)
        row["resources"] = sampler.report()
        results.append(row)
        print(deadline, row["timeout_rate"], row["completed_queries"], flush=True)
    common.write_report("05-timeout-budget", {
        "server": "uvicorn 1 worker started fresh per budget (cold DF cache), DB_POOL_SIZE=8",
        "users": args.users[0], "query_mix_size": len(mix), "budgets": results}, args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["concurrency", "timeout"])
    parser.add_argument("--database-url")
    parser.add_argument("--users", type=int, nargs="+", default=None)
    parser.add_argument("--deadlines", type=int, nargs="+", default=[1000, 2000, 5000])
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.users = args.users or ([1, 10, 25, 50, 100] if args.what == "concurrency" else [25])
    url = common.configure(args.database_url)
    common.run({"concurrency": bench_concurrency, "timeout": bench_timeout}[args.what](args, url))


if __name__ == "__main__":
    main()
