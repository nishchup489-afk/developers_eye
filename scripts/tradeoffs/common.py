"""Shared helpers for the core trade-off benchmarks (CORE_TRADEOFFS.md).

Every benchmark script in this folder:
- takes --database-url and sets DATABASE_URL *before* importing backend code,
  so it never touches a database it was not pointed at;
- samples CPU and memory of this Python process, every postgres process and the
  whole machine while it runs (ResourceSampler);
- writes one JSON report with the machine, PostgreSQL settings and git commit,
  so a number can always be traced back to how it was produced.

The how-to for reading and recomputing every number is guide/tradeoffs_calculation.md.
"""

from __future__ import annotations

import json
import math
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "backend" / "reports" / "tradeoffs"
BENCH_DATABASE_NAME = "developers_eye_bench"


def default_bench_url() -> str:
    """backend/.env DATABASE_URL with the database name swapped for the benchmark copy.

    Benchmarks run on a pg_dump/pg_restore copy (see the guide) so writes, index
    experiments and corpus sampling never change the real database.
    """
    url = os.environ.get("BENCH_DATABASE_URL")
    if url:
        return url
    base = os.environ.get("DATABASE_URL")
    env_file = REPO_ROOT / "backend" / ".env"
    if not base and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                base = line.split("=", 1)[1].strip()
    if not base:
        raise SystemExit("Set BENCH_DATABASE_URL or pass --database-url")
    return base.rsplit("/", 1)[0] + "/" + BENCH_DATABASE_NAME


def configure(database_url: str | None, *, pool_size: int | None = None,
              max_overflow: int | None = None) -> str:
    """Point backend settings at the benchmark database. Call before importing backend."""
    url = database_url or default_bench_url()
    if not url.rsplit("/", 1)[-1].startswith(BENCH_DATABASE_NAME) and not os.environ.get("BENCH_ALLOW_ANY_DB"):
        raise SystemExit(f"Refusing to benchmark {url.rsplit('/', 1)[-1]!r}: point at a "
                         f"{BENCH_DATABASE_NAME} copy, or set BENCH_ALLOW_ANY_DB=1 for read-only runs")
    os.environ["DATABASE_URL"] = url
    if pool_size is not None:
        os.environ["DB_POOL_SIZE"] = str(pool_size)
    if max_overflow is not None:
        os.environ["DB_MAX_OVERFLOW"] = str(max_overflow)
    return url


def run(coro):
    """asyncio.run with the selector loop the crawler uses on Windows."""
    import asyncio
    if sys.platform == "win32":
        import selectors
        return asyncio.run(coro, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    return asyncio.run(coro)


def percentile(values: Iterable[float], q: float) -> float | None:
    """Nearest-rank percentile: the smallest sample with at least q of samples at or below it."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(q * len(ordered)))
    return round(ordered[rank - 1], 3)


def summarize(samples_ms: list[float]) -> dict[str, Any]:
    if not samples_ms:
        return {"n": 0}
    return {
        "n": len(samples_ms),
        "mean_ms": round(statistics.fmean(samples_ms), 3),
        "p50_ms": percentile(samples_ms, 0.50),
        "p95_ms": percentile(samples_ms, 0.95),
        "p99_ms": percentile(samples_ms, 0.99),
        "max_ms": round(max(samples_ms), 3),
    }


def _postgres_processes():
    import psutil
    found = []
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name.startswith("postgres"):
            found.append(proc)
    return found


@dataclass
class ResourceSampler:
    """Background thread: CPU seconds and RSS of this process, postgres and the machine.

    CPU is reported two ways:
      *_cpu_seconds  total CPU time used during the window (sum over cores),
      *_cpu_cores    cpu_seconds / wall seconds, i.e. how many cores were busy on average.
    Postgres CPU covers every postgres process alive at the start or seen while
    sampling, including other databases' sessions, so run on a quiet machine or
    subtract the idle baseline that is recorded in the report.
    """

    interval: float = 0.5
    extra_pids: list[int] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _rows: list[dict[str, float]] = field(default_factory=list)

    def _cpu(self, procs) -> float:
        total = 0.0
        for proc in procs:
            try:
                times = proc.cpu_times()
                total += times.user + times.system
            except Exception:  # process ended or access denied
                pass
        return total

    def _rss(self, procs) -> float:
        total = 0
        for proc in procs:
            try:
                total += proc.memory_info().rss
            except Exception:
                pass
        return total / 2**20

    def __enter__(self) -> "ResourceSampler":
        import psutil
        self._psutil = psutil
        self._self = psutil.Process()
        self._extra = [psutil.Process(pid) for pid in self.extra_pids if psutil.pid_exists(pid)]
        self._pg = {p.pid: p for p in _postgres_processes()}
        # Per-process CPU at start and last seen: a backend that exits mid-run keeps
        # its last reading, and one that starts mid-run counts from zero.
        self._pg_first = {pid: self._cpu([proc]) for pid, proc in self._pg.items()}
        self._pg_last = dict(self._pg_first)
        self._self_start = self._cpu([self._self] + self._self.children(recursive=True) + self._extra)
        self._sys_start = psutil.cpu_times()
        self._wall_start = time.perf_counter()
        psutil.cpu_percent(None)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _loop(self) -> None:
        # Scanning the process table is the expensive part on Windows, so new
        # postgres backends and child processes are picked up every 3 seconds.
        psutil = self._psutil
        tick = 0
        started = time.thread_time()
        mine = [self._self] + self._self.children(recursive=True) + self._extra
        while not self._stop.wait(self.interval):
            if tick % 6 == 5:
                for proc in _postgres_processes():
                    self._pg.setdefault(proc.pid, proc)
                mine = [self._self] + self._self.children(recursive=True) + self._extra
            self._read_pg_cpu()
            tick += 1
            mem = psutil.virtual_memory()
            self._rows.append({
                "t": time.perf_counter() - self._wall_start,
                "system_cpu_percent": psutil.cpu_percent(None),
                "python_rss_mb": self._rss(mine),
                "postgres_rss_mb": self._rss(self._pg.values()) if tick % 4 == 1 else 0.0,
                "system_used_mb": (mem.total - mem.available) / 2**20,
            })
            # The sampler's own CPU is subtracted from python_cpu_seconds in __exit__.
            self._sampler_cpu = time.thread_time() - started

    def _read_pg_cpu(self) -> None:
        for pid, proc in list(self._pg.items()):
            try:
                times = proc.cpu_times()
                self._pg_last[pid] = times.user + times.system
            except Exception:
                pass

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.wall_seconds = time.perf_counter() - self._wall_start
        procs = [self._self] + self._self.children(recursive=True) + self._extra
        self.sampler_cpu_seconds = getattr(self, "_sampler_cpu", 0.0)
        self.python_cpu_seconds = max(0.0, self._cpu(procs) - self._self_start - self.sampler_cpu_seconds)
        self._read_pg_cpu()
        self.postgres_cpu_seconds = sum(last - self._pg_first.get(pid, 0.0) for pid, last in self._pg_last.items())
        end = self._psutil.cpu_times()
        busy = lambda t: t.user + t.system + getattr(t, "interrupt", 0.0) + getattr(t, "dpc", 0.0)
        self.system_cpu_seconds = busy(end) - busy(self._sys_start)

    def report(self) -> dict[str, Any]:
        wall = max(self.wall_seconds, 1e-9)
        rows = self._rows or [{}]
        peak = lambda key: round(max((r.get(key, 0.0) for r in rows), default=0.0), 1)
        return {
            "wall_seconds": round(self.wall_seconds, 3),
            "python_cpu_seconds": round(self.python_cpu_seconds, 3),
            "sampler_cpu_seconds_excluded": round(self.sampler_cpu_seconds, 3),
            "postgres_cpu_seconds": round(self.postgres_cpu_seconds, 3),
            "system_cpu_seconds": round(self.system_cpu_seconds, 3),
            "python_cpu_cores": round(self.python_cpu_seconds / wall, 3),
            "postgres_cpu_cores": round(self.postgres_cpu_seconds / wall, 3),
            "system_cpu_cores": round(self.system_cpu_seconds / wall, 3),
            "peak_python_rss_mb": peak("python_rss_mb"),
            "peak_postgres_rss_mb": peak("postgres_rss_mb"),
            "peak_system_used_mb": peak("system_used_mb"),
            "mean_system_cpu_percent": round(statistics.fmean(
                r.get("system_cpu_percent", 0.0) for r in rows), 1),
        }


def idle_baseline(seconds: float = 3.0) -> dict[str, Any]:
    """Machine CPU while this benchmark does nothing (other workloads, e.g. a live crawler)."""
    with ResourceSampler() as sampler:
        time.sleep(seconds)
    return sampler.report()


def machine() -> dict[str, Any]:
    import psutil
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": psutil.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "python": platform.python_version(),
    }


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return None


async def postgres_info(session) -> dict[str, Any]:
    from sqlalchemy import text
    rows = {}
    for name in ("server_version", "shared_buffers", "work_mem", "effective_cache_size",
                 "max_connections", "random_page_cost", "jit", "max_parallel_workers_per_gather"):
        rows[name] = await session.scalar(text(f"SHOW {name}"))
    rows["database"] = await session.scalar(text("SELECT current_database()"))
    rows["search_index_rows"] = await session.scalar(text("SELECT count(*) FROM search_index"))
    rows["database_size_mb"] = round(
        (await session.scalar(text("SELECT pg_database_size(current_database())"))) / 2**20, 1)
    return rows


def write_report(name: str, payload: dict[str, Any], output: Path | None = None) -> Path:
    path = output or (REPORT_DIR / f"{name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "benchmark": name,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "machine": machine(),
        **payload,
    }
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"saved {path}")
    return path


def load_checklist_queries() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The 25-query agent-reviewed set (EXP-0014) and its URL grades."""
    base = REPO_ROOT / "backend" / "evaluation" / "checklist-25"
    queries = json.loads((base / "queries.json").read_text(encoding="utf-8"))["queries"]
    qrels = json.loads((base / "qrels.json").read_text(encoding="utf-8"))["queries"]
    return queries, qrels


def graded_metrics(urls: list[str], grades: dict[str, int | None], k: int = 10) -> dict[str, Any]:
    """P@k, MRR@k, nDCG@k with unjudged URLs counted as grade 0, plus judged coverage.

    Same formulas as backend.search.evaluation.metrics (gain 2^g - 1, log2 discount,
    grade > 0 is relevant), but it never refuses to score: it reports how many of
    the top k had a grade so a reader can see how much was assumed.
    """
    known = {u: g for u, g in grades.items() if g is not None}
    positives = sorted((g for g in known.values() if g > 0), reverse=True)
    seen: set[str] = set()
    hits, first, dcg, judged = 0, None, 0.0, 0
    for rank, url in enumerate(urls[:k], start=1):
        if url in known:
            judged += 1
        grade = known.get(url, 0) if url not in seen else 0
        seen.add(url)
        if grade > 0:
            hits += 1
            first = first or rank
        dcg += (2**grade - 1) / math.log2(rank + 1)
    ideal = sum((2**g - 1) / math.log2(r + 1) for r, g in enumerate(positives[:k], start=1))
    return {
        "p_at_k": hits / k,
        "mrr_at_k": (1 / first) if first else 0.0,
        "ndcg_at_k": (dcg / ideal) if ideal else None,
        "judged_in_top_k": judged,
        "returned": min(len(urls), k),
    }


def mean_of(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.fmean(values), 4) if values else None
