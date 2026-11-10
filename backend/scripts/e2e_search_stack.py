"""Fresh frontend-to-backend test: real Next.js, real FastAPI, a brand new PostgreSQL database.

Run from backend/, after `npm run build` in frontend/:

    poetry run python scripts/e2e_search_stack.py

TEST_DATABASE_URL (environment or backend/.env) only names the server and credentials:
the script creates its own database, migrates it to head, seeds it, and drops it again.
Slow queries are real ones: a held ACCESS EXCLUSIVE lock makes every search wait.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import asyncpg
import httpx
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from backend.core.local_env import load_local_env

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
DOCUMENTS = 25
API, LIMITED_API = "http://127.0.0.1:8131", "http://127.0.0.1:8132"
WEB, LIMITED_WEB = "http://127.0.0.1:3131", "http://127.0.0.1:3132"
Q = {"q": "python"}


def passed(label: str) -> None:
    print(f"PASS {label}", flush=True)


async def seed(url: str) -> None:
    db = await asyncpg.connect(url)
    try:
        source = await db.fetchval(
            "INSERT INTO source (slug, name, kind, base_url, allowed_hosts) "
            "VALUES ('e2e', 'E2E', 'website', 'https://e2e.example.test', ARRAY['e2e.example.test']) RETURNING id"
        )
        for number in range(DOCUMENTS):
            category = "github" if number % 5 == 0 else "docs"
            host = "github.com" if category == "github" else "e2e.example.test"
            code = "asyncio.create_task(fetch())" if number % 2 == 0 else ""
            document = await db.fetchval(
                "INSERT INTO document (source_id, canonical_url, document_type, title, body, content_hash) "
                "VALUES ($1, $2, 'documentation', $3, $4, $5) RETURNING id",
                source, f"https://{host}/{number}", f"Python guide {number}",
                f"python asyncio guide number {number}", f"hash-{number}",
            )
            await db.execute(
                "INSERT INTO search_index (document_id, search_vector, code_vector, indexed_hash, category) "
                "VALUES ($1, to_tsvector('english', $2), to_tsvector('simple', $3), $4, $5)",
                document, f"python asyncio guide number {number}", code, f"hash-{number}", category,
            )
        await db.executemany(
            "INSERT INTO search_terms (term, document_frequency) VALUES ($1, $2)",
            [("python", DOCUMENTS), ("asyncio", DOCUMENTS), ("guide", DOCUMENTS)],
        )
        await db.execute("ANALYZE")
    finally:
        await db.close()


async def wait_until_up(client: httpx.AsyncClient, url: str, servers: list[subprocess.Popen]) -> None:
    for _ in range(200):
        if any(server.poll() is not None for server in servers):
            raise RuntimeError("a server exited during startup")
        try:
            await client.get(url)
            return
        except httpx.TransportError:
            await asyncio.sleep(0.2)
    raise RuntimeError(f"{url} did not start")


async def waiting_searches(db: asyncpg.Connection) -> int:
    return await db.fetchval(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
    )


async def check_search(web: httpx.AsyncClient, api: httpx.AsyncClient) -> None:
    first = await web.get("/api/search", params=Q)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["mode"] == "live" and len(body["results"]) == 20, body
    second = (await web.get("/api/search", params={**Q, "page": 2})).json()
    assert len(second["results"]) == DOCUMENTS - 20
    assert not {r["url"] for r in body["results"]} & {r["url"] for r in second["results"]}
    passed("live search and pagination, no repeated results")

    github = (await web.get("/api/search", params={**Q, "source": "github"})).json()
    assert len(github["results"]) == 5 and {r["source"] for r in github["results"]} == {"github"}
    code = (await web.get("/api/search", params={"q": "asyncio.create_task", "mode": "code"})).json()
    assert code["results"], code
    passed("source filter and code mode reach PostgreSQL")

    suggestion = (await web.get("/api/search/suggest", params={"q": "pyhton"})).json()
    assert suggestion["suggestion"] == "python", suggestion
    passed("spelling suggestion through the proxy")

    assert (await web.get("/api/search", params={"q": "x" * 256})).status_code == 200
    assert (await api.get("/search", params={"q": "x" * 256})).status_code == 200
    assert (await web.get("/api/search", params={"q": "x" * 257})).status_code == 400
    assert (await api.get("/search", params={"q": "x" * 257})).status_code == 422
    spaced = "python" + " " * 400 + "asyncio"
    assert (await web.get("/api/search", params={"q": spaced})).status_code == 200
    assert (await api.get("/search", params={"q": spaced})).status_code == 200
    assert (await web.get("/api/search", params={"q": "😀" * 256})).status_code == 200
    passed("frontend and backend agree on query length")


async def check_rate_limit() -> None:
    async with httpx.AsyncClient(base_url=LIMITED_WEB, timeout=15) as web:
        first = {"X-Forwarded-For": "203.0.113.1"}
        for _ in range(2):
            assert (await web.get("/api/search", params=Q, headers=first)).status_code == 200
        limited = await web.get("/api/search", params=Q, headers=first)
        assert limited.status_code == 429, limited.text
        assert int(limited.headers["retry-after"]) >= 1
        assert limited.headers["cache-control"] == "no-store"
        other = await web.get("/api/search", params=Q, headers={"X-Forwarded-For": "203.0.113.2"})
        assert other.status_code == 200
    passed("429 with Retry-After through the proxy, one bucket per visitor")


async def check_under_lock(web: httpx.AsyncClient, db_url: str) -> None:
    lock = await asyncpg.connect(db_url)
    watch = await asyncpg.connect(db_url)
    transaction = lock.transaction()
    await transaction.start()
    try:
        await lock.execute("LOCK TABLE search_index, search_terms IN ACCESS EXCLUSIVE MODE")

        started = perf_counter()
        timed_out = await web.get("/api/search", params=Q)
        assert timed_out.status_code == 504, timed_out.text
        assert "statement timeout" not in timed_out.text
        assert 2.5 < perf_counter() - started < 5
        passed("real statement_timeout becomes 504 through the proxy")

        responses = await asyncio.gather(*(web.get("/api/search", params=Q) for _ in range(5)))
        statuses = sorted(r.status_code for r in responses)
        assert statuses == [503, 503, 503, 504, 504], statuses
        busy = next(r for r in responses if r.status_code == 503)
        assert busy.headers["retry-after"] == "1"
        passed("concurrency cap: 2 admitted, 3 rejected with 503 and Retry-After")

        for path in ["/api/search", "/api/search/suggest"] * 6:
            started = perf_counter()
            request = asyncio.create_task(web.get(path, params=Q))
            while await waiting_searches(watch) == 0:
                assert perf_counter() - started < 2, "the search never reached PostgreSQL"
                await asyncio.sleep(0.02)
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
            while await waiting_searches(watch) > 0:
                assert perf_counter() - started < 2.5, "the cancelled query kept running"
                await asyncio.sleep(0.02)
        passed("12 repeated browser disconnects stop search/suggestion PostgreSQL queries")
    finally:
        await transaction.rollback()
        await lock.close()
        await watch.close()

    assert (await web.get("/api/search", params=Q)).status_code == 200
    responses = await asyncio.gather(*(web.get("/api/search", params=Q) for _ in range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    passed("no slot leaked: search recovers once the lock is gone")


async def main() -> None:
    load_local_env(__file__)
    if not (FRONTEND / os.environ.get("NEXT_BUILD_DIR", ".next") / "BUILD_ID").exists():
        sys.exit("Run `npm run build` in frontend/ first")
    configured = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND / ".env").get("TEST_DATABASE_URL")
    if not configured or not configured.startswith("postgresql+asyncpg://"):
        sys.exit("Set TEST_DATABASE_URL to a postgresql+asyncpg:// URL")
    configured_url = make_url(configured)
    name = f"developers_eye_e2e_test_{uuid4().hex[:8]}"
    db_url = configured_url.set(drivername="postgresql", database=name).render_as_string(hide_password=False)
    python_url = configured_url.set(database=name).render_as_string(hide_password=False)

    admin = await asyncpg.connect(configured_url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False))
    await admin.execute(f'CREATE DATABASE "{name}"')
    servers: list[subprocess.Popen] = []
    logs = tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace")
    try:
        base = dict(os.environ, DATABASE_URL=python_url)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=base, check=True,
                       stdout=logs, stderr=logs)
        await seed(db_url)
        passed("fresh database migrated to head and seeded")

        def uvicorn(port: str, **limits: str) -> None:
            servers.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", port, "--log-level", "warning"],
                cwd=BACKEND, env={**base, **limits}, stdout=logs, stderr=logs,
            ))

        def next_start(port: str, api: str) -> None:
            servers.append(subprocess.Popen(
                [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", port],
                cwd=FRONTEND, env=dict(os.environ, BACKEND_URL=api, KNOWLEDGE_PANEL="off"), stdout=logs, stderr=logs,
            ))

        uvicorn("8131", SEARCH_RATE_LIMIT_PER_MINUTE="0", SEARCH_MAX_CONCURRENT="2")
        uvicorn("8132", SEARCH_RATE_LIMIT_PER_MINUTE="60", SEARCH_RATE_LIMIT_BURST="2")
        next_start("3131", API)
        next_start("3132", LIMITED_API)

        async with httpx.AsyncClient(timeout=15) as probe:
            for url in (f"{API}/health", f"{LIMITED_API}/health", f"{WEB}/api/search", f"{LIMITED_WEB}/api/search"):
                await wait_until_up(probe, url, servers)
        passed("Next.js and FastAPI started against the fresh database")

        async with httpx.AsyncClient(base_url=WEB, timeout=15) as web, httpx.AsyncClient(base_url=API, timeout=15) as api:
            await check_search(web, api)
            await check_rate_limit()
            await check_under_lock(web, db_url)
        print("ALL PASSED", flush=True)
    except BaseException:
        logs.seek(0)
        print(logs.read()[-4000:], file=sys.stderr)
        raise
    finally:
        for process in servers:
            process.kill()
            process.wait()
        logs.close()
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


if __name__ == "__main__":
    asyncio.run(main())
