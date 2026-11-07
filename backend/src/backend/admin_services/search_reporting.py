"""Search availability for the admin dashboard.

Traffic comes from search_minute, which every API process writes. Health checks
read the database directly. This report has to work during the outages it
describes, so a dead database still gets an answer: `build_offline_report` uses
the minutes the answering process holds in memory.

Availability excludes rejected input (HTTP 422): a bad query is not an outage.
Latency covers successful searches only. Failed ones show up in the failure
counts, and a fast rejection would otherwise make latency look better.
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text

from backend.admin_services.crawler_reporting import _percentage, _utc
from backend.api.search import MAX_CONCURRENT_SEARCHES, QUERY_DEADLINE_MS
from backend.models.search_minute import SearchMinute
from backend.search.service import corpus_snapshot_info
from backend.search.telemetry import LATENCY_BOUNDS_MS, OUTCOMES, telemetry

TIMELINE_BUCKETS = 60
RECENT = timedelta(minutes=15)
MIN_RECENT_REQUESTS = 5
AVAILABILITY_TARGET = 99.0
DOWN_BELOW = 50.0
SLOW_PING_MS = 1000
SNAPSHOT_STALE = timedelta(minutes=30)
# Autovacuum analyzes at 10% changed; twice that means it is not keeping up.
UNANALYZED_LIMIT = 0.2
SEARCH_TABLES = ("search_index", "document")
FAILURES = tuple(name for name in OUTCOMES if name not in ("successful", "invalid"))
ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


@lru_cache
def _expected_revision() -> str | None:
    """The newest migration shipped with this code, or None when none ship with it."""
    if not ALEMBIC_INI.exists():
        return None
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    return heads[0] if len(heads) == 1 else None


def _percentile(buckets: list[int], fraction: float) -> float | None:
    """Interpolate inside the bucket, so the result is an estimate from the histogram."""
    total = sum(buckets)
    if not total:
        return None
    rank, seen, lower = fraction * total, 0, 0
    for index, count in enumerate(buckets):
        if index == len(LATENCY_BOUNDS_MS):
            # The overflow bucket has no upper bound; report its floor.
            return float(lower)
        upper = LATENCY_BOUNDS_MS[index]
        if count and seen + count >= rank:
            return round(lower + (upper - lower) * (rank - seen) / count, 1)
        seen += count
        lower = upper
    return float(lower)


def _merge(rows) -> dict:
    merged = {name: 0 for name in OUTCOMES}
    buckets = [0] * (len(LATENCY_BOUNDS_MS) + 1)
    latency_sum = 0
    for row in rows:
        for name in OUTCOMES:
            merged[name] += row[name]
        latency_sum += row["latency_sum_ms"]
        for index, count in enumerate(row["latency_buckets"]):
            buckets[index] += count
    return dict(merged, latency_sum_ms=latency_sum, latency_buckets=buckets)


def _totals(merged: dict) -> dict:
    failed = sum(merged[name] for name in FAILURES)
    answered = merged["successful"] + failed
    buckets = merged["latency_buckets"]
    return dict(
        **{name: merged[name] for name in OUTCOMES}, requests=answered + merged["invalid"], answered=answered,
        failed=failed, availability_percent=_percentage(merged["successful"], answered),
        timeout_percent=_percentage(merged["timed_out"], answered),
        busy_percent=_percentage(merged["busy"], answered),
        mean_ms=round(merged["latency_sum_ms"] / merged["successful"], 1) if merged["successful"] else None,
        p50_ms=_percentile(buckets, 0.5), p95_ms=_percentile(buckets, 0.95), p99_ms=_percentile(buckets, 0.99))


def _traffic(rows, *, now: datetime, hours: int) -> dict:
    step = timedelta(hours=hours) / TIMELINE_BUCKETS
    start = now - timedelta(hours=hours)
    grouped: dict[int, list] = {}
    for row in rows:
        index = int((row["minute"] - start) / step)
        grouped.setdefault(min(max(index, 0), TIMELINE_BUCKETS - 1), []).append(row)
    timeline = []
    for index in range(TIMELINE_BUCKETS):
        slot = _totals(_merge(grouped.get(index, ())))
        timeline.append(dict(at=_utc(start + index * step), requests=slot["answered"], failed=slot["failed"],
                             timed_out=slot["timed_out"], busy=slot["busy"], p95_ms=slot["p95_ms"]))
    merged = _merge(rows)
    processes: dict[str, dict] = {}
    for row in rows:
        entry = processes.setdefault(row["process"], dict(process=row["process"], requests=0, last_seen_at=row["minute"]))
        entry["requests"] += row["successful"] + sum(row[name] for name in FAILURES)
        entry["last_seen_at"] = max(entry["last_seen_at"], row["minute"])
    latency = [dict(le_ms=bound, count=merged["latency_buckets"][index]) for index, bound in enumerate(LATENCY_BOUNDS_MS)]
    latency.append(dict(le_ms=None, count=merged["latency_buckets"][-1]))
    return dict(totals=_totals(merged), recent=_totals(_merge([r for r in rows if r["minute"] >= now - RECENT])),
                timeline=timeline, latency=latency,
                processes=[dict(p, last_seen_at=_utc(p["last_seen_at"])) for p in
                           sorted(processes.values(), key=lambda p: p["last_seen_at"], reverse=True)][:20])


def _snapshot(now: datetime) -> dict:
    info = corpus_snapshot_info()
    if info is None:
        return dict(loaded=False, documents=None, loaded_at=None, age_seconds=None)
    return dict(loaded=True, documents=info["documents"], loaded_at=_utc(info["loaded_at"]),
                age_seconds=int((now - info["loaded_at"]).total_seconds()))


def _limits() -> dict:
    return dict(deadline_ms=QUERY_DEADLINE_MS, max_concurrent_per_process=MAX_CONCURRENT_SEARCHES,
                availability_target_percent=AVAILABILITY_TARGET)


def _verdict(*, database: dict, schema: dict, snapshot: dict, planner: list, recent: dict, recording: bool):
    down, degraded = [], []
    if not database["reachable"]:
        down.append("The database did not answer. Every search that needs it is failing.")
    availability = recent["availability_percent"]
    if availability is not None and recent["answered"] >= MIN_RECENT_REQUESTS:
        if availability < DOWN_BELOW:
            down.append(f"Only {availability}% of searches succeeded in the last 15 minutes.")
        elif availability < AVAILABILITY_TARGET:
            degraded.append(f"{availability}% of searches succeeded in the last 15 minutes.")
    if schema["up_to_date"] is False:
        degraded.append(f"The database is on migration {schema['current'] or 'none'}, but this code expects "
                        f"{schema['expected']}. Run alembic upgrade head.")
    if database["reachable"] and not recording and schema["up_to_date"] is not False:
        degraded.append("The search_minute table is missing, so outcomes are not being recorded.")
    if not snapshot["loaded"]:
        degraded.append("This API process has no BM25 snapshot, so it cannot rank results.")
    elif snapshot["age_seconds"] > SNAPSHOT_STALE.total_seconds():
        degraded.append("This API process's BM25 snapshot has not refreshed for over 30 minutes.")
    if database["ping_ms"] is not None and database["ping_ms"] > SLOW_PING_MS:
        degraded.append(f"The database took {database['ping_ms']} ms to answer a trivial query.")
    for table in planner:
        if table["status"] != "ok":
            degraded.append(f"{table['table']} needs VACUUM ANALYZE: the planner may pick slow search plans.")
    return ("down" if down else "degraded" if degraded else "ok"), down + degraded


async def _planner_tables(session) -> list:
    rows = (await session.execute(text("""
        SELECT s.relname AS table_name, GREATEST(c.reltuples, 0)::bigint AS estimated_rows,
               s.n_mod_since_analyze AS modified_since_analyze,
               s.n_dead_tup AS dead_rows,
               GREATEST(s.last_autoanalyze, s.last_analyze) AS last_analyze_at,
               GREATEST(s.last_autovacuum, s.last_vacuum) AS last_vacuum_at
        FROM pg_stat_user_tables s JOIN pg_class c ON c.oid = s.relid
        WHERE s.schemaname = current_schema() AND s.relname = ANY(:tables)
        ORDER BY s.relname"""), {"tables": list(SEARCH_TABLES)})).mappings().all()
    tables = []
    for row in rows:
        behind = row["modified_since_analyze"] > max(1000, UNANALYZED_LIMIT * row["estimated_rows"])
        tables.append(dict(table=row["table_name"], estimated_rows=row["estimated_rows"],
                           modified_since_analyze=row["modified_since_analyze"], dead_rows=row["dead_rows"],
                           dead_percent=_percentage(row["dead_rows"], row["dead_rows"] + row["estimated_rows"]),
                           last_analyze_at=_utc(row["last_analyze_at"]), last_vacuum_at=_utc(row["last_vacuum_at"]),
                           status="stale" if behind else "ok"))
    return tables


async def build_search_report(session, *, hours: int = 24):
    now = datetime.now(timezone.utc)
    started = perf_counter()
    await session.execute(text("SELECT 1"))
    ping_ms = round((perf_counter() - started) * 1000, 1)
    connections = (await session.execute(text("""
        SELECT count(*) FILTER (WHERE datname = current_database()) AS used,
               current_setting('max_connections')::int AS max
        FROM pg_stat_activity"""))).mappings().one()
    database = dict(reachable=True, ping_ms=ping_ms, connections_used=connections["used"], connections_max=connections["max"])

    expected = _expected_revision()
    has_versions = await session.scalar(text("SELECT to_regclass('alembic_version') IS NOT NULL"))
    current = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1")) if has_versions else None
    schema = dict(current=current, expected=expected, up_to_date=None if expected is None else current == expected)

    recording = bool(await session.scalar(text("SELECT to_regclass('search_minute') IS NOT NULL")))
    rows = []
    if recording:
        table = SearchMinute.__table__
        rows = [dict(row) for row in (await session.execute(
            select(table).where(table.c.minute >= now - timedelta(hours=hours)).order_by(table.c.minute))).mappings().all()]
    traffic = _traffic(rows, now=now, hours=hours)
    snapshot = _snapshot(now)
    planner = await _planner_tables(session)
    status, reasons = _verdict(database=database, schema=schema, snapshot=snapshot, planner=planner,
                               recent=traffic["recent"], recording=recording)
    return dict(version=1, generated_at=_utc(now), window_hours=hours, status=status, reasons=reasons, recording=recording,
                partial=False, limits=_limits(), database=database, schema=schema, snapshot=snapshot, planner=planner, **traffic)


def build_offline_report(*, hours: int = 24):
    """The database is gone: report what this process alone still remembers."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    traffic = _traffic([r for r in telemetry.rows() if r["minute"] >= cutoff], now=now, hours=hours)
    database = dict(reachable=False, ping_ms=None, connections_used=None, connections_max=None)
    schema = dict(current=None, expected=_expected_revision(), up_to_date=None)
    snapshot = _snapshot(now)
    status, reasons = _verdict(database=database, schema=schema, snapshot=snapshot, planner=[],
                               recent=traffic["recent"], recording=False)
    return dict(version=1, generated_at=_utc(now), window_hours=hours, status=status, reasons=reasons, recording=False,
                partial=True, limits=_limits(), database=database, schema=schema, snapshot=snapshot, planner=[], **traffic)
