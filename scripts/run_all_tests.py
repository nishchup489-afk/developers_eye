"""Run every test suite in Developer's Eye and print one diagnostics report.

Usage, from the repository root:

    python scripts/run_all_tests.py                  # Python suites + fast frontend checks
    python scripts/run_all_tests.py --with-build     # also `next build` and the tests that need it
    python scripts/run_all_tests.py --only backend indexer
    python scripts/run_all_tests.py --skip frontend
    python scripts/run_all_tests.py --list           # show the suites and exit
    python scripts/run_all_tests.py --save           # also write tests/reports/run-<time>.html/.txt/.json
    python scripts/run_all_tests.py --report out.html
    python scripts/run_all_tests.py -k fuzzy         # pass a -k filter to every pytest suite

Each suite still runs with its own native runner, from its own folder, exactly
as the per-package docs say (``cd backend && pytest``, ``npm run ...`` in
frontend/). This script only orchestrates them and reads their results:
pytest suites through a JUnit XML file, Node scripts through their exit code
and their ``PASS ...`` lines.

The report has: environment checks (Python and Node toolchains, git state,
the test database: reachable, Postgres version, pg_trgm, safe name), a
per-suite table (passed / failed / errors / skipped / duration), the reasons
tests were skipped, the slowest tests, and the full detail of every failure.

The script needs ``rich``. Both Poetry projects already install it, so if the
Python you start it with lacks it, the script re-runs itself with the
crawler's or backend's virtualenv.

Test database: put ``TEST_DATABASE_URL`` in the repo-root ``.env.local``
(copy ``.env.local.example``). The pytest suites load it themselves through
their ``tests/conftest.py``; this script reads the same file for its database
checks. Only test keys (``TEST_*``, ``*_TEST_*``) are read, and a value set in
the shell wins. ``--env-file`` points at another file, ``--no-env-file`` skips it.

Exit code: 0 when every suite that ran passed, 1 otherwise, 2 for bad usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------- #
# Bootstrapping: make sure `rich` is importable.
# --------------------------------------------------------------------------- #


def _venv_python(project_dir: Path) -> Path | None:
    for candidate in (
        project_dir / ".venv" / "Scripts" / "python.exe",
        project_dir / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return candidate
    return None


def _poetry_python(project_dir: Path) -> Path | None:
    poetry = shutil.which("poetry")
    if not poetry:
        return None
    try:
        out = subprocess.run(
            [poetry, "env", "info", "--executable"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    return path if path and path.is_file() else None


try:
    from rich import box
    from rich.console import Console, Group
    from rich.markup import escape
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover - depends on the caller's interpreter
    if os.environ.get("DE_TEST_RUNNER_REEXEC"):
        sys.exit("rich is not installed. Run: cd crawler && poetry install")
    for project in ("crawler", "backend"):
        python = _venv_python(ROOT / project) or _poetry_python(ROOT / project)
        if python and Path(python).resolve() != Path(sys.executable).resolve():
            env = dict(os.environ, DE_TEST_RUNNER_REEXEC="1")
            sys.exit(subprocess.call([str(python), __file__, *sys.argv[1:]], env=env))
    sys.exit(
        "rich is not installed for this Python and no project virtualenv was found.\n"
        "Run `cd crawler && poetry install`, then `poetry run python ../scripts/run_all_tests.py`."
    )


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

PASS, FAIL, ERROR, SKIPPED = "PASS", "FAIL", "ERROR", "SKIPPED"
STATUS_STYLE = {PASS: "bold green", FAIL: "bold red", ERROR: "bold magenta", SKIPPED: "yellow"}
CHECK_STYLE = {"ok": "green", "warn": "yellow", "fail": "red", "info": "cyan"}
CHECK_ICON = {"ok": "✔", "warn": "!", "fail": "✘", "info": "·"}


@dataclass
class Suite:
    name: str
    group: str  # python | frontend | build
    title: str
    cwd: str  # relative to ROOT
    kind: str  # pytest | node
    targets: list[str] = field(default_factory=list)  # pytest paths
    npm_script: str | None = None
    command: list[str] | None = None  # explicit node command (relative to cwd)
    needs_db: str = ""  # "", "some", "all"
    needs_build: bool = False


@dataclass
class TestCase:
    nodeid: str
    outcome: str  # passed | failed | error | skipped
    duration: float
    message: str = ""
    detail: str = ""


@dataclass
class SuiteResult:
    name: str
    title: str
    status: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    note: str = ""
    command: str = ""
    exit_code: int | None = None
    cases: list[TestCase] = field(default_factory=list)
    output_tail: str = ""


@dataclass
class Check:
    area: str
    name: str
    status: str  # ok | warn | fail | info
    detail: str


SUITES: list[Suite] = [
    Suite("backend", "python", "Backend (FastAPI, search)", "backend", "pytest", needs_db="some"),
    Suite("crawler", "python", "Crawler", "crawler", "pytest", targets=["tests/crawler"], needs_db="some"),
    Suite("indexer", "python", "Indexer", "crawler", "pytest", targets=["tests/indexer"], needs_db="some"),
    Suite("fe-lint", "frontend", "Frontend lint (eslint)", "frontend", "node", npm_script="lint"),
    Suite(
        "fe-types",
        "frontend",
        "Frontend typecheck (tsc)",
        "frontend",
        "node",
        command=["node", "node_modules/typescript/bin/tsc", "--noEmit", "-p", "."],
    ),
    Suite("fe-admin-unit", "frontend", "Frontend admin unit", "frontend", "node", npm_script="test:admin:unit"),
    Suite("fe-search-unit", "frontend", "Frontend search unit", "frontend", "node", npm_script="test:search:unit"),
    Suite("fe-build", "build", "Frontend production build", "frontend", "node", npm_script="build", needs_build=True),
    Suite(
        "fe-integration",
        "build",
        "Frontend integration",
        "frontend",
        "node",
        npm_script="test:integration",
        needs_build=True,
    ),
    Suite(
        "fe-admin", "build", "Frontend admin integration", "frontend", "node", npm_script="test:admin", needs_build=True
    ),
    Suite(
        "fe-admin-routes",
        "build",
        "Frontend admin routes",
        "frontend",
        "node",
        npm_script="test:admin:routes",
        needs_build=True,
    ),
    Suite(
        "fe-overview-routes",
        "build",
        "Frontend AI overview routes",
        "frontend",
        "node",
        npm_script="test:overview:routes",
        needs_build=True,
    ),
]
GROUP_ALIASES = {
    "python": {"backend", "crawler", "indexer"},
    "frontend": {s.name for s in SUITES if s.group in ("frontend", "build")},
    "build": {s.name for s in SUITES if s.group == "build"},
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def fmt_seconds(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, sec = divmod(int(round(seconds)), 60)
    return f"{minutes}m {sec:02d}s"


def tail(text: str, lines: int) -> str:
    parts = text.rstrip().splitlines()
    return "\n".join(parts[-lines:])


def run_quiet(cmd: list[str], cwd: Path | None = None, timeout: float = 30, env: dict | None = None) -> tuple[int, str]:
    try:
        out = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s"
    except OSError as exc:
        return 126, str(exc)
    return out.returncode, (out.stdout + out.stderr).strip()


def mask_url(url: str) -> str:
    return re.sub(r"(://[^:/@]+):[^@]*@", r"\1:***@", url)


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def build_env(extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    src_paths = [str(ROOT / "backend" / "src"), str(ROOT / "crawler" / "src")]
    if env.get("PYTHONPATH"):
        src_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(src_paths)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("FORCE_COLOR", "0")
    env["NO_COLOR"] = "1"
    return env


# --------------------------------------------------------------------------- #
# Interpreter discovery
# --------------------------------------------------------------------------- #


@dataclass
class PyInfo:
    path: str | None
    source: str
    version: str = ""
    pytest: str = ""
    asyncio_plugin: str = ""
    asyncpg: bool = False
    problem: str = ""


_PROBE = (
    "import sys, importlib.util as u, importlib.metadata as m\n"
    "def v(n):\n"
    "    try: return m.version(n)\n"
    "    except Exception: return ''\n"
    "print(sys.version.split()[0]); print(v('pytest')); print(v('pytest-asyncio'));"
    " print('1' if u.find_spec('asyncpg') else '0')\n"
)


def find_python(project: str, override: str | None) -> PyInfo:
    project_dir = ROOT / project
    if override:
        info = PyInfo(override, "--python")
    elif (venv := _venv_python(project_dir)) is not None:
        info = PyInfo(str(venv), f"{project}/.venv")
    elif (poetry := _poetry_python(project_dir)) is not None:
        info = PyInfo(str(poetry), "poetry env")
    else:
        info = PyInfo(sys.executable, "this Python")
    code, out = run_quiet([info.path, "-c", _PROBE], timeout=60)
    if code != 0:
        info.problem = f"cannot start: {tail(out, 2)}"
        return info
    lines = (out.splitlines() + ["", "", "", "0"])[:4]
    info.version, info.pytest, info.asyncio_plugin = lines[0], lines[1], lines[2]
    info.asyncpg = lines[3].strip() == "1"
    if not info.pytest:
        info.problem = "pytest is not installed (run `poetry install` in this folder)"
    return info


# --------------------------------------------------------------------------- #
# Environment checks
# --------------------------------------------------------------------------- #

_DB_PROBE = r"""
import asyncio, json, sys
import asyncpg

async def main(dsn):
    conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=8)
    try:
        version = await conn.fetchval("show server_version")
        database = await conn.fetchval("select current_database()")
        trgm = await conn.fetchval("select extversion from pg_extension where extname = 'pg_trgm'")
        tables = await conn.fetchval(
            "select count(*) from information_schema.tables where table_schema = 'public'"
        )
        alembic = None
        if await conn.fetchval("select to_regclass('public.alembic_version') is not null"):
            alembic = await conn.fetchval("select version_num from alembic_version limit 1")
        conns = await conn.fetchval("select count(*) from pg_stat_activity")
        max_conns = await conn.fetchval("show max_connections")
    finally:
        await conn.close()
    print(json.dumps(dict(version=version, database=database, trgm=trgm, tables=tables,
                          alembic=alembic, conns=conns, max_conns=max_conns)))

asyncio.run(main(sys.argv[1]))
"""


def db_checks(url: str | None, source: str, py: PyInfo | None) -> list[Check]:
    checks: list[Check] = []
    if not url:
        checks.append(
            Check(
                "database",
                "TEST_DATABASE_URL",
                "warn",
                "not set: PostgreSQL tests will skip or fail. Put it in .env.local (see .env.local.example).",
            )
        )
        return checks
    checks.append(Check("database", "TEST_DATABASE_URL", "ok", f"{mask_url(url)}  (from {source})"))

    parts = urlsplit(url)
    dbname = parts.path.lstrip("/")
    if "test" not in dbname.lower():
        checks.append(
            Check("database", "Safe database name", "fail", f"'{dbname}' has no 'test' in it; DB tests refuse to run")
        )
    else:
        checks.append(Check("database", "Safe database name", "ok", dbname))
    if not parts.scheme.startswith("postgresql"):
        checks.append(Check("database", "Driver", "fail", f"scheme '{parts.scheme}' is not postgresql"))
        return checks
    if "+asyncpg" not in parts.scheme:
        checks.append(Check("database", "Driver", "warn", "tests expect postgresql+asyncpg://"))

    host = parts.hostname or parse_qs(parts.query).get("host", ["localhost"])[0]
    port = parts.port or int(parse_qs(parts.query).get("port", ["5432"])[0])
    if host.startswith("/"):
        checks.append(Check("database", "Socket", "info", f"unix socket {host} port {port}"))
    else:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError as exc:
            checks.append(Check("database", "Port reachable", "fail", f"{host}:{port} — {exc}"))
            return checks
        checks.append(
            Check("database", "Port reachable", "ok", f"{host}:{port} in {fmt_seconds(time.perf_counter() - started)}")
        )

    if not py or not py.path or not py.asyncpg:
        checks.append(Check("database", "Server details", "info", "asyncpg not available; skipped login check"))
        return checks
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    code, out = run_quiet([py.path, "-c", _DB_PROBE, dsn], timeout=30)
    if code != 0:
        last = tail(out, 1).replace(dsn, mask_url(dsn))
        checks.append(Check("database", "Login", "fail", last or f"exit code {code}"))
        return checks
    try:
        info = json.loads(out.splitlines()[-1])
    except (ValueError, IndexError):
        checks.append(Check("database", "Login", "warn", f"unexpected probe output: {tail(out, 1)}"))
        return checks
    checks.append(Check("database", "PostgreSQL version", "ok", f"{info['version']} (database {info['database']})"))
    if info["trgm"]:
        checks.append(Check("database", "pg_trgm extension", "ok", f"installed, v{info['trgm']}"))
    else:
        checks.append(
            Check("database", "pg_trgm extension", "warn", "missing: run `create extension pg_trgm` in the test DB")
        )
    alembic = f", alembic head {info['alembic']}" if info["alembic"] else ""
    checks.append(Check("database", "Schema", "info", f"{info['tables']} public tables{alembic}"))
    usage = int(info["conns"]) / max(int(info["max_conns"]), 1)
    checks.append(
        Check(
            "database",
            "Connections",
            "warn" if usage > 0.8 else "ok",
            f"{info['conns']} of {info['max_conns']} in use",
        )
    )
    return checks


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def environment_checks(
    selected: list[Suite],
    pythons: dict[str, PyInfo],
    db_url: str | None,
    db_source: str,
) -> list[Check]:
    checks: list[Check] = []

    try:
        from importlib.metadata import version as _v

        rich_version = _v("rich")
    except Exception:  # pragma: no cover
        rich_version = "?"
    checks.append(
        Check(
            "system",
            "Platform",
            "info",
            f"{platform.system()} {platform.release()} · {platform.machine()} · runner Python "
            f"{platform.python_version()} · rich {rich_version}",
        )
    )
    usage = shutil.disk_usage(ROOT)
    free_gb = usage.free / 1024**3
    checks.append(
        Check("system", "Free disk", "warn" if free_gb < 2 else "ok", f"{free_gb:.1f} GB free on the repo drive")
    )

    code, branch = run_quiet(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT)
    if code == 0:
        _, commit = run_quiet(["git", "log", "-1", "--format=%h %s"], cwd=ROOT)
        _, status = run_quiet(["git", "status", "--porcelain"], cwd=ROOT)
        changed = len([line for line in status.splitlines() if line.strip()])
        checks.append(
            Check(
                "git",
                "Checkout",
                "info",
                f"{branch} @ {commit[:70]} · {changed} changed file(s)"
                if changed
                else f"{branch} @ {commit[:70]} · clean",
            )
        )
    else:
        checks.append(Check("git", "Checkout", "warn", "git not available"))

    for project, info in pythons.items():
        if info.problem:
            checks.append(Check("python", f"{project} Python", "fail", f"{info.path} ({info.source}): {info.problem}"))
            continue
        plugin = f", pytest-asyncio {info.asyncio_plugin}" if info.asyncio_plugin else ", pytest-asyncio missing"
        status = "ok" if info.asyncio_plugin else "warn"
        checks.append(
            Check(
                "python",
                f"{project} Python",
                status,
                f"{info.version} via {info.source} · pytest {info.pytest}{plugin}",
            )
        )

    if any(s.cwd == "frontend" for s in selected):
        code, node_v = run_quiet(["node", "--version"])
        if code == 0:
            major = int(re.sub(r"\D", "", node_v.split(".")[0]) or 0)
            checks.append(
                Check(
                    "node",
                    "Node.js",
                    "ok" if major >= 22 else "warn",
                    node_v + ("" if major >= 22 else " (tests use --experimental-strip-types; Node 22+ expected)"),
                )
            )
        else:
            checks.append(Check("node", "Node.js", "fail", "node is not on PATH"))
        npm = shutil.which("npm")
        if npm:
            _, npm_v = run_quiet([npm, "--version"])
            checks.append(Check("node", "npm", "ok", npm_v))
        else:
            checks.append(Check("node", "npm", "fail", "npm is not on PATH"))
        modules = ROOT / "frontend" / "node_modules"
        checks.append(
            Check(
                "node",
                "frontend/node_modules",
                "ok" if modules.is_dir() else "fail",
                "installed" if modules.is_dir() else "missing: run `npm install` in frontend/",
            )
        )
        if any(s.npm_script == "test:integration" for s in selected):
            busy = [p for p in (3181, 3182) if not port_free(p)]
            checks.append(
                Check(
                    "node",
                    "Ports 3181/3182",
                    "fail" if busy else "ok",
                    f"in use: {busy}" if busy else "free (needed by test:integration)",
                )
            )

    if any(s.needs_db for s in selected):
        db_py = pythons.get("crawler") or pythons.get("backend")
        checks.extend(db_checks(db_url, db_source, db_py))
    return checks


# --------------------------------------------------------------------------- #
# Running suites
# --------------------------------------------------------------------------- #


def stream_process(cmd: list[str], cwd: Path, env: dict, timeout: float, echo) -> tuple[int, str, bool]:
    """Run a command, collect its combined output, optionally echo each line."""
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines: list[str] = []

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line)
            if echo:
                echo(line.rstrip("\n"))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    thread.join(timeout=5)
    return proc.returncode, "".join(lines), timed_out


def parse_junit(path: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        nodeid = f"{classname.replace('.', '/')}::{name}" if classname else name
        duration = float(case.get("time", "0") or 0)
        outcome, message, detail = "passed", "", ""
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
                message = child.get("message", "") or ""
                detail = (child.text or "").strip()
                break
        cases.append(TestCase(nodeid, outcome, duration, message, detail))
    return cases


def run_pytest(suite: Suite, py: PyInfo, args: argparse.Namespace, env: dict, echo) -> SuiteResult:
    result = SuiteResult(suite.name, suite.title, ERROR)
    if py.problem or not py.path:
        result.note = py.problem or "no Python found"
        return result
    with tempfile.TemporaryDirectory(prefix="de-tests-") as tmp:
        xml = Path(tmp) / f"{suite.name}.xml"
        cmd = [
            py.path,
            "-m",
            "pytest",
            *suite.targets,
            "-q",
            "-rN",
            "--tb=short",
            "--color=no",
            f"--junitxml={xml}",
            "-o",
            "junit_family=xunit2",
            "-o",
            "junit_logging=no",
        ]
        if args.k:
            cmd += ["-k", args.k]
        if args.failfast_tests:
            cmd += ["-x"]
        cmd += args.pytest_args
        result.command = f"cd {suite.cwd} && " + " ".join(["python", *cmd[1:]]).replace(str(xml), "<report.xml>")
        started = time.perf_counter()
        code, output, timed_out = stream_process(cmd, ROOT / suite.cwd, env, args.timeout, echo)
        result.duration = time.perf_counter() - started
        result.exit_code = code
        result.output_tail = tail(output, 40)
        if xml.is_file():
            try:
                result.cases = parse_junit(xml)
            except ET.ParseError as exc:
                result.note = f"could not read JUnit XML: {exc}"
    for case in result.cases:
        if case.outcome == "passed":
            result.passed += 1
        elif case.outcome == "failed":
            result.failed += 1
        elif case.outcome == "error":
            result.errors += 1
        else:
            result.skipped += 1
    if timed_out:
        result.status, result.note = ERROR, f"timed out after {fmt_seconds(args.timeout)}"
    elif code == 5 and not result.cases:
        result.status, result.note = SKIPPED, "no tests collected"
    elif code in (0, 5) and not result.failed and not result.errors:
        result.status = PASS
    elif result.failed or result.errors:
        result.status = FAIL
    else:
        result.status = ERROR
        result.note = result.note or f"pytest exit code {code}"
    return result


def run_node(suite: Suite, args: argparse.Namespace, env: dict, echo) -> SuiteResult:
    result = SuiteResult(suite.name, suite.title, ERROR)
    frontend = ROOT / suite.cwd
    if not (frontend / "node_modules").is_dir():
        result.status, result.note = SKIPPED, "frontend/node_modules missing (npm install)"
        return result
    if suite.npm_script:
        npm = shutil.which("npm")
        if not npm:
            result.note = "npm not on PATH"
            return result
        cmd = [npm, "run", "--silent", suite.npm_script]
        result.command = f"cd {suite.cwd} && npm run {suite.npm_script}"
    else:
        node = shutil.which("node")
        if not node:
            result.note = "node not on PATH"
            return result
        assert suite.command
        if not (frontend / suite.command[1]).is_file():
            result.status, result.note = SKIPPED, f"{suite.command[1]} not installed"
            return result
        cmd = [node, *suite.command[1:]]
        result.command = f"cd {suite.cwd} && " + " ".join(suite.command)
    started = time.perf_counter()
    code, output, timed_out = stream_process(cmd, frontend, env, args.timeout, echo)
    result.duration = time.perf_counter() - started
    result.exit_code = code
    result.output_tail = tail(output, 40)

    pass_lines = [line.strip() for line in output.splitlines() if line.strip().startswith("PASS ")]
    result.passed = len(pass_lines)
    for line in pass_lines:
        result.cases.append(TestCase(f"{suite.name}::{line[5:][:120]}", "passed", 0.0))

    if timed_out:
        result.status, result.note = ERROR, f"timed out after {fmt_seconds(args.timeout)}"
        return result
    if code == 0:
        result.status = PASS
        if not result.passed:
            result.passed = 1  # lint / typecheck / build: one check that passed
        return result

    result.status = FAIL
    problems = [
        line.strip()
        for line in output.splitlines()
        if re.search(r"\berror\b|AssertionError|FAIL|✖|Error:", line) and line.strip()
    ]
    if suite.name == "fe-types":
        result.failed = len([p for p in problems if "error TS" in p]) or 1
    elif suite.name == "fe-lint":
        match = re.search(r"(\d+) problems? \((\d+) errors?", output)
        result.failed = int(match.group(2)) if match else 1
    else:
        result.failed = 1  # the .mjs scripts stop at the first failing assertion
    message = problems[0] if problems else f"exit code {code}"
    result.cases.append(
        TestCase(
            f"{suite.name}::{suite.npm_script or 'tsc'}", "failed", result.duration, message[:300], tail(output, 60)
        )
    )
    return result


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def render_header(console: Console, started: dt.datetime, selected: list[Suite]) -> None:
    title = Text("Developer's Eye · test diagnostics", style="bold white")
    sub = Text.assemble(
        ("started ", "dim"),
        (started.strftime("%Y-%m-%d %H:%M:%S"), "cyan"),
        ("   repo ", "dim"),
        (str(ROOT), "cyan"),
        ("   suites ", "dim"),
        (", ".join(s.name for s in selected), "cyan"),
    )
    console.print(Panel(Group(title, sub), box=box.HEAVY, border_style="blue"))


def render_checks(console: Console, checks: list[Check]) -> None:
    table = Table(title="Environment", title_justify="left", box=box.SIMPLE_HEAVY, expand=True)
    table.add_column("", width=1)
    table.add_column("Area", style="dim", no_wrap=True)
    table.add_column("Check", no_wrap=True)
    table.add_column("Detail", overflow="fold")
    for check in checks:
        style = CHECK_STYLE[check.status]
        table.add_row(
            Text(CHECK_ICON[check.status], style=style),
            check.area,
            Text(check.name, style=style),
            escape(check.detail),
        )
    console.print(table)


def render_summary(console: Console, results: list[SuiteResult], total_time: float) -> None:
    table = Table(title="Suites", title_justify="left", box=box.ROUNDED, expand=True, show_footer=True)
    totals = {k: sum(getattr(r, k) for r in results) for k in ("passed", "failed", "errors", "skipped")}
    table.add_column("Suite", footer="Total", no_wrap=True)
    table.add_column("Status", footer=f"{sum(r.status == PASS for r in results)}/{len(results)} pass", justify="center")
    table.add_column("Passed", justify="right", style="green", footer=str(totals["passed"]))
    table.add_column("Failed", justify="right", style="red", footer=str(totals["failed"]))
    table.add_column("Errors", justify="right", style="magenta", footer=str(totals["errors"]))
    table.add_column("Skipped", justify="right", style="yellow", footer=str(totals["skipped"]))
    table.add_column("Time", justify="right", footer=fmt_seconds(total_time))
    table.add_column("Note", overflow="fold", style="dim")
    for r in results:
        table.add_row(
            r.title,
            Text(r.status, style=STATUS_STYLE[r.status]),
            str(r.passed),
            str(r.failed) if r.failed else "·",
            str(r.errors) if r.errors else "·",
            str(r.skipped) if r.skipped else "·",
            fmt_seconds(r.duration) if r.duration else "–",
            escape(r.note),
        )
    console.print(table)


def render_skips(console: Console, results: list[SuiteResult]) -> None:
    reasons: dict[tuple[str, str], int] = {}
    for r in results:
        for case in r.cases:
            if case.outcome == "skipped":
                reason = re.sub(r"^Skipped:\s*", "", case.message or "(no reason given)")[:160]
                reasons[(r.name, reason)] = reasons.get((r.name, reason), 0) + 1
    if not reasons:
        return
    table = Table(title="Why tests were skipped", title_justify="left", box=box.SIMPLE, expand=True)
    table.add_column("Suite", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="yellow")
    table.add_column("Reason", overflow="fold")
    for (suite, reason), count in sorted(reasons.items(), key=lambda kv: -kv[1])[:15]:
        table.add_row(suite, str(count), escape(reason))
    console.print(table)


def render_slowest(console: Console, results: list[SuiteResult], limit: int) -> None:
    cases = [(r.name, c) for r in results for c in r.cases if c.duration > 0 and c.outcome != "skipped"]
    if not cases or limit <= 0:
        return
    cases.sort(key=lambda item: -item[1].duration)
    table = Table(title=f"Slowest {min(limit, len(cases))} tests", title_justify="left", box=box.SIMPLE, expand=True)
    table.add_column("Time", justify="right", style="bold")
    table.add_column("Suite", style="cyan", no_wrap=True)
    table.add_column("Test", overflow="fold")
    for suite, case in cases[:limit]:
        table.add_row(fmt_seconds(case.duration), suite, escape(case.nodeid))
    console.print(table)


HINTS: list[tuple[str, str]] = [
    (r"No module named '([\w.]+)'", "missing Python module '{0}' in this suite's env: run `poetry install` there"),
    (
        r'relation "(\w+)" does not exist',
        "test DB has no table '{0}': run `alembic upgrade head` against TEST_DATABASE_URL",
    ),
    (
        r"(?i)connection refused|could not connect|ConnectionRefusedError",
        "PostgreSQL is not reachable at TEST_DATABASE_URL",
    ),
    (r"Set TEST_DATABASE_URL", "TEST_DATABASE_URL is not set: these tests need a PostgreSQL test database"),
    (r"password authentication failed", "wrong user or password in TEST_DATABASE_URL"),
    (r'database "(\w+)" does not exist', "database '{0}' does not exist: create it first"),
    (r"(?i)address already in use|EADDRINUSE", "a port the test needs is taken: stop the other server"),
    (
        r"(?i)could not find a production build|Cannot find module '[^']*/server/app/|ENOENT.*\.next",
        "no production build for this test (or NEXT_BUILD_DIR points elsewhere): run with --with-build",
    ),
    (r"Cannot find module|ERR_MODULE_NOT_FOUND", "a Node module is missing: run `npm install` in frontend/"),
]


def failure_key(case: TestCase) -> str:
    """Group failures that share a root cause (same first E-line or message)."""
    for line in case.detail.splitlines():
        if line.startswith("E "):
            return re.sub(r"0x[0-9a-f]+", "0x…", line[1:].strip())[:200]
    return re.sub(r"0x[0-9a-f]+", "0x…", (case.message or "").splitlines()[0] if case.message else "")[:200]


def diagnose(results: list[SuiteResult]) -> list[str]:
    hints: dict[str, set[str]] = {}
    for r in results:
        texts = [c.message + "\n" + c.detail for c in r.cases if c.outcome in ("failed", "error")]
        if r.status == ERROR:
            texts.append(r.output_tail)
        for text in texts:
            for pattern, template in HINTS:
                match = re.search(pattern, text)
                if match:
                    hints.setdefault(template.format(*match.groups()), set()).add(r.name)
                    break  # first (most specific) pattern wins for this failure
    return [f"{hint}  [{', '.join(sorted(suites))}]" for hint, suites in hints.items()]


def render_failures(console: Console, results: list[SuiteResult], limit: int, trace_lines: int) -> None:
    failing = [(r, c) for r in results for c in r.cases if c.outcome in ("failed", "error")]
    broken = [r for r in results if r.status == ERROR and not any(c.outcome in ("failed", "error") for c in r.cases)]
    if not failing and not broken:
        return
    groups: dict[tuple[str, str], list[tuple[SuiteResult, TestCase]]] = {}
    for r, case in failing:
        groups.setdefault((r.name, failure_key(case)), []).append((r, case))
    console.print(Rule(f"[bold red]Failures ({len(failing)} in {len(groups)} distinct cause(s))", style="red"))
    for shown, members in enumerate(groups.values()):
        if shown >= limit:
            console.print(f"[dim]… {len(groups) - limit} more cause(s) not shown (raise --max-failures)[/]")
            break
        r, case = members[0]
        collection = case.message.startswith("collection failure")
        label = "COLLECTION ERROR" if collection else ("ERROR" if case.outcome == "error" else "FAIL")
        parts: list = [Text(case.message.splitlines()[0] if case.message else "(no message)", style="bold")]
        if case.detail:
            parts.append(Text(tail(case.detail, trace_lines), style="dim"))
        if len(members) > 1:
            others = [m[1].nodeid for m in members[1:]]
            listed = "\n".join(f"  • {n}" for n in others[:8])
            more = f"\n  … and {len(others) - 8} more" if len(others) > 8 else ""
            parts.append(Text(f"\nSame cause in {len(others)} more test(s):\n{listed}{more}", style="yellow"))
        console.print(
            Panel(
                Group(*parts),
                title=f"[{STATUS_STYLE[FAIL if label == 'FAIL' else ERROR]}]{label}[/] [{r.name}] {escape(case.nodeid)}",
                title_align="left",
                subtitle=escape(r.command) if r.command else None,
                subtitle_align="left",
                border_style="red" if label == "FAIL" else "magenta",
            )
        )
    for r in broken:
        console.print(
            Panel(
                Text(r.output_tail or r.note or "(no output)", style="dim"),
                title=f"[{STATUS_STYLE[ERROR]}]SUITE ERROR[/] {escape(r.title)}: {escape(r.note)}",
                title_align="left",
                subtitle=escape(r.command) if r.command else None,
                subtitle_align="left",
                border_style="magenta",
            )
        )


def render_verdict(console: Console, results: list[SuiteResult], checks: list[Check]) -> bool:
    bad = [r for r in results if r.status in (FAIL, ERROR)]
    failed_checks = [c for c in checks if c.status == "fail"]
    ran = [r for r in results if r.status != SKIPPED]
    total = sum(r.passed + r.failed + r.errors + r.skipped for r in results)
    if not bad:
        msg = Text.assemble(
            ("ALL GREEN  ", "bold green"),
            f"{len(ran)} suite(s) ran, {total} test(s) and check(s), none failed.",
        )
        if any(r.status == SKIPPED for r in results):
            msg.append(f"  {sum(r.status == SKIPPED for r in results)} suite(s) skipped.", style="yellow")
        console.print(Panel(msg, border_style="green", box=box.HEAVY))
        return True
    lines = [Text.assemble(("NOT GREEN  ", "bold red"), f"{len(bad)} of {len(ran)} suite(s) failed.")]
    for r in bad:
        collect = sum(c.message.startswith("collection failure") for c in r.cases)
        extra = f", {collect} file(s) failed to import" if collect else ""
        lines.append(
            Text(f"  • {r.title}: {r.failed} failed, {r.errors} errors{extra} {('· ' + r.note) if r.note else ''}")
        )
    if failed_checks:
        lines.append(Text("Environment problems that may explain it:", style="yellow"))
        for c in failed_checks:
            lines.append(Text(f"  • {c.name}: {c.detail}", style="yellow"))
    hints = diagnose(results)
    if hints:
        lines.append(Text("Likely causes found in the failures:", style="cyan"))
        for hint in hints:
            lines.append(Text(f"  • {hint}", style="cyan"))
    console.print(Panel(Group(*lines), border_style="red", box=box.HEAVY))
    return False


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def select_suites(args: argparse.Namespace) -> list[Suite]:
    names = {s.name for s in SUITES}

    def expand(items: list[str]) -> set[str]:
        out: set[str] = set()
        for item in items:
            for part in item.split(","):
                part = part.strip()
                if not part:
                    continue
                if part in GROUP_ALIASES:
                    out |= GROUP_ALIASES[part]
                elif part in names:
                    out.add(part)
                else:
                    raise SystemExit(f"unknown suite '{part}'. Use --list to see the names.")
        return out

    chosen = expand(args.only) if args.only else {s.name for s in SUITES if s.group != "build" or args.with_build}
    # `--only fe-admin-routes` without --with-build reuses whatever build already exists.
    if args.with_build and chosen & GROUP_ALIASES["build"]:
        chosen.add("fe-build")
    chosen -= expand(args.skip)
    return [s for s in SUITES if s.name in chosen]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run every Developer's Eye test suite and print a rich diagnostics report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Groups for --only/--skip: python, frontend, build. Suite names: " + ", ".join(s.name for s in SUITES),
    )
    parser.add_argument("--only", nargs="+", default=[], metavar="SUITE", help="run only these suites or groups")
    parser.add_argument("--skip", nargs="+", default=[], metavar="SUITE", help="leave out these suites or groups")
    parser.add_argument(
        "--with-build",
        action="store_true",
        help="also run `next build` and the frontend tests that need a production build",
    )
    parser.add_argument("--list", action="store_true", help="list the suites and exit")
    parser.add_argument("-k", metavar="EXPR", help="pytest -k expression for every pytest suite")
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[], help="extra pytest arguments (put last)")
    parser.add_argument("-x", "--failfast", action="store_true", help="stop after the first suite that fails")
    parser.add_argument(
        "--failfast-tests", action="store_true", help="pass -x to pytest (stop a suite at its first failure)"
    )
    parser.add_argument(
        "--python", metavar="PATH", help="Python to run the pytest suites with (default: each project's venv)"
    )
    parser.add_argument(
        "--env-file", default=".env.local", help="read test variables from this file (default: .env.local)"
    )
    parser.add_argument("--no-env-file", action="store_true", help="do not read any env file")
    parser.add_argument("--no-env-checks", action="store_true", help="skip the environment section")
    parser.add_argument("--timeout", type=float, default=1800, help="seconds before a suite is killed (default 1800)")
    parser.add_argument("--slowest", type=int, default=10, help="how many slow tests to list (default 10, 0 hides)")
    parser.add_argument("--max-failures", type=int, default=25, help="failures shown in full (default 25)")
    parser.add_argument("--trace-lines", type=int, default=30, help="traceback lines per failure (default 30)")
    parser.add_argument("-v", "--verbose", action="store_true", help="stream each suite's raw output while it runs")
    parser.add_argument("--save", action="store_true", help="write tests/reports/run-<time>.html, .txt and .json")
    parser.add_argument(
        "--report",
        metavar="FILE",
        action="append",
        default=[],
        help="write the report to FILE (.html, .svg, .txt or .json); repeatable",
    )
    return parser.parse_args(argv)


def save_reports(console: Console, paths: list[Path], payload: dict) -> list[Path]:
    written: list[Path] = []
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix == ".json":
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        elif suffix in (".html", ".htm"):
            console.save_html(str(path), clear=False)
        elif suffix == ".svg":
            console.save_svg(str(path), title="Developer's Eye test diagnostics", clear=False)
        else:
            console.save_text(str(path), clear=False, styles=False)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    # Redirected Windows output otherwise inherits cp1252 and crashes on Rich's
    # diagnostic symbols before any suite runs. Reports and subprocesses use UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args(argv)
    console = Console(record=True, highlight=False, soft_wrap=False)

    if args.list:
        table = Table(title="Suites", box=box.SIMPLE_HEAVY)
        for col in ("Name", "Group", "Runs", "Needs"):
            table.add_column(col)
        for s in SUITES:
            runs = (
                f"cd {s.cwd} && pytest {' '.join(s.targets)}".strip()
                if s.kind == "pytest"
                else f"cd {s.cwd} && " + (f"npm run {s.npm_script}" if s.npm_script else " ".join(s.command or []))
            )
            needs = ", ".join(
                filter(None, ["PostgreSQL (some tests)" if s.needs_db else "", "--with-build" if s.needs_build else ""])
            )
            table.add_row(s.name, s.group, runs, needs)
        console.print(table)
        return 0

    selected = select_suites(args)
    if not selected:
        console.print("[yellow]No suites selected.[/]")
        return 2

    started_at = dt.datetime.now()
    render_header(console, started_at, selected)

    # Test settings: shell first, then test keys from .env.local (same rules as tests/conftest.py).
    extra_env: dict[str, str] = {}
    db_source = "shell"
    if not args.no_env_file:
        env_path = (ROOT / args.env_file) if not Path(args.env_file).is_absolute() else Path(args.env_file)
        file_values = {
            k: v for k, v in read_env_file(env_path).items() if (k.startswith("TEST_") or "_TEST_" in k) and v
        }
        extra_env.update({k: v for k, v in file_values.items() if k not in os.environ})
        if "TEST_DATABASE_URL" in extra_env:
            db_source = str(env_path.relative_to(ROOT)) if env_path.is_relative_to(ROOT) else str(env_path)
    elif not os.environ.get("TEST_DATABASE_URL"):
        db_source = "nowhere"
    db_url = os.environ.get("TEST_DATABASE_URL") or extra_env.get("TEST_DATABASE_URL")
    if any(s.name == "fe-build" for s in selected):
        # A verification build must not replace a running `next dev` cache.
        extra_env["NEXT_BUILD_DIR"] = os.environ.get("NEXT_BUILD_DIR") or ".next-test-runner"
    env = build_env(extra_env)

    pythons: dict[str, PyInfo] = {}
    with console.status("Inspecting toolchains…", spinner="dots"):
        for project in sorted({s.cwd for s in selected if s.kind == "pytest"}):
            pythons[project] = find_python(project, args.python)
        checks = [] if args.no_env_checks else environment_checks(selected, pythons, db_url, db_source)
    if checks:
        render_checks(console, checks)

    results: list[SuiteResult] = []
    run_started = time.perf_counter()
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=24),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    stop_rest = False
    with progress:
        overall = progress.add_task("Running suites", total=len(selected))
        for suite in selected:
            if stop_rest:
                results.append(SuiteResult(suite.name, suite.title, SKIPPED, note="not run (--failfast)"))
                progress.advance(overall)
                continue
            build = next((r for r in results if r.name == "fe-build"), None)
            if suite.needs_build and suite.name != "fe-build" and build and build.status != PASS:
                results.append(SuiteResult(suite.name, suite.title, SKIPPED, note="production build failed"))
                progress.advance(overall)
                continue
            progress.update(overall, description=f"{suite.title}")
            echo = (
                (lambda line, s=suite.name: progress.console.print(f"[dim]{s} │[/] {escape(line)}"))
                if args.verbose
                else None
            )
            if suite.kind == "pytest":
                result = run_pytest(suite, pythons[suite.cwd], args, env, echo)
            else:
                result = run_node(suite, args, env, echo)
            results.append(result)
            progress.console.print(
                f"  [{STATUS_STYLE[result.status]}]{result.status:<7}[/] {suite.title:<32} "
                f"[green]{result.passed} passed[/]"
                + (f" [red]{result.failed} failed[/]" if result.failed else "")
                + (f" [magenta]{result.errors} errors[/]" if result.errors else "")
                + (f" [yellow]{result.skipped} skipped[/]" if result.skipped else "")
                + f" [dim]{fmt_seconds(result.duration)}[/]"
                + (f" [dim]· {escape(result.note)}[/]" if result.note else "")
            )
            progress.advance(overall)
            if args.failfast and result.status in (FAIL, ERROR):
                stop_rest = True
    total_time = time.perf_counter() - run_started

    console.print()
    render_summary(console, results, total_time)
    render_skips(console, results)
    render_slowest(console, results, args.slowest)
    render_failures(console, results, args.max_failures, args.trace_lines)
    ok = render_verdict(console, results, checks)

    report_paths = [Path(p) if Path(p).is_absolute() else Path.cwd() / p for p in args.report]
    if args.save:
        stamp = started_at.strftime("%Y%m%d-%H%M%S")
        base = ROOT / "tests" / "reports" / f"run-{stamp}"
        report_paths += [base.with_suffix(".html"), base.with_suffix(".txt"), base.with_suffix(".json")]
    if report_paths:
        payload = {
            "started_at": started_at.isoformat(timespec="seconds"),
            "duration_seconds": round(total_time, 2),
            "ok": ok,
            "hints": diagnose(results),
            "repo": str(ROOT),
            "checks": [asdict(c) for c in checks],
            "suites": [
                {k: v for k, v in asdict(r).items() if k != "cases"}
                | {
                    "failures": [asdict(c) for c in r.cases if c.outcome in ("failed", "error")],
                    "skips": [asdict(c) for c in r.cases if c.outcome == "skipped"],
                }
                for r in results
            ],
        }
        written = save_reports(console, report_paths, payload)
        for path in written:
            console.print(f"[dim]report saved:[/] {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
