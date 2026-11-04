"""Regenerate the test indexes under tests/.

Usage, from the repository root:

    python scripts/update_test_index.py                 # rewrite both indexes
    python scripts/update_test_index.py --check         # exit 1 if an index is stale
    python scripts/update_test_index.py --install-hook  # run this on every commit

Test files stay where their runners expect them (backend/tests, crawler/tests,
frontend/tests, tests/end-to-end). This script collects every one of them into:

    tests/test-index-of-whole-app.md                     one table per suite
    tests/all-test-cases-that-were-tested/index.md       every test case, by file

A file is picked up when its name starts with ``test_`` or when it sits anywhere
under a folder named ``test`` or ``tests``. Files git ignores (``__pycache__``,
``node_modules``, ``.venv``) never appear. New files are listed as soon as they
exist, before ``git add``.

Generated text lives between the two marker comments; anything written outside
them is kept.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

START = "<!-- test-index:start -->"
END = "<!-- test-index:end -->"

WHOLE_APP = "tests/test-index-of-whole-app.md"
CASES = "tests/all-test-cases-that-were-tested/index.md"
GENERATED = {WHOLE_APP, CASES}

# Where each suite lives, how to run it, and how it is labelled. First match wins.
SUITES = [
    ("tests/end-to-end/", "End-to-end (full app)", "Not written yet."),
    ("backend/tests/", "Backend (FastAPI, search)", "`cd backend && poetry run pytest`"),
    ("crawler/tests/indexer/", "Indexer", "`cd crawler && poetry run pytest tests/indexer`"),
    ("crawler/tests/", "Crawler", "`cd crawler && poetry run pytest tests/crawler`"),
    ("frontend/tests/", "Frontend (Next.js, admin)", "npm scripts in `frontend/package.json` (see below)"),
]

# Write-ups of what was tested and what happened, outside any tests/ folder.
REPORT_DIRS = ("0_tech_docs/journal/test-reports/",)

HOOK = """#!/bin/sh
# Installed by scripts/update_test_index.py --install-hook.
# Keeps tests/ indexes current so every new test file is listed.
for candidate in python python3 py; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "pre-commit: python not found, test index not refreshed" >&2
    exit 0
fi
"$PY" scripts/update_test_index.py --quiet || exit 1
git add tests/test-index-of-whole-app.md tests/all-test-cases-that-were-tested/index.md
"""


# ---------------------------------------------------------------- discovery

def repo_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8")
    return sorted({p for p in out.split("\0") if p and (root / p).is_file()})


def is_test_file(path: str) -> bool:
    p = PurePosixPath(path)
    if path in GENERATED or p.name == ".gitkeep" or p.suffix == ".pyc":
        return False
    if p.name.startswith("test_"):
        return True
    return any(part.lower() in {"test", "tests"} for part in p.parts[:-1])


def is_writeup(path: str) -> bool:
    p = PurePosixPath(path)
    return p.suffix == ".md" and (
        p.name.startswith("test_case") or path.startswith(REPORT_DIRS)
    )


def suite_of(path: str) -> tuple[str, str, str]:
    for prefix, label, run in SUITES:
        if path.startswith(prefix):
            return prefix, label, run
    return "", "Other", "See the file itself."


def role_of(path: str, root: Path | None = None) -> str:
    p = PurePosixPath(path)
    if root is not None and p.name.startswith("test_") and (root / path).stat().st_size == 0:
        return "empty placeholder"
    if p.suffix == ".md":
        return "write-up"
    if p.name == "conftest.py":
        return "fixtures"
    if "fixtures" in p.parts or "fixture" in p.name:
        return "fixture data"
    if p.suffix == ".py" and not p.name.startswith("test_"):
        return "helper"
    return "tests"


# ---------------------------------------------------------------- parsing

def first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return doc.strip().splitlines()[0].strip()


def python_cases(source: str) -> list[tuple[str, str]]:
    """Return (name, first docstring line) for every pytest-style test."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[tuple[str, str]] = []
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, funcs) and node.name.startswith("test"):
            found.append((node.name, first_line(ast.get_docstring(node))))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, funcs) and item.name.startswith("test"):
                    found.append((f"{node.name}.{item.name}", first_line(ast.get_docstring(item))))
    return found


def js_cases(source: str) -> list[tuple[str, str]]:
    """Named cases from test("..."), it("...") or describe("...") calls, if any."""
    names = re.findall(r"""\b(?:test|it)\(\s*(["'`])(.+?)\1""", source)
    return [(name, "") for _, name in names]


def slugify(text: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[`*_~]", lambda m: "_" if m.group(0) == "_" else "", text.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def sections(path: Path) -> list[tuple[str, str, str]]:
    """(heading text, GitHub anchor, body text) for each heading, with -1, -2 suffixes."""
    seen: dict[str, int] = defaultdict(int)
    result: list[tuple[str, str, list[str]]] = [("", "", [])]
    in_code = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not m:
            result[-1][2].append(line)
            continue
        base = slugify(m.group(1))
        anchor = base if seen[base] == 0 else f"{base}-{seen[base]}"
        seen[base] += 1
        result.append((m.group(1).strip("` ").strip(), anchor, []))
    return [(t, a, "\n".join(body)) for t, a, body in result]


# ---------------------------------------------------------------- rendering

def link(target: str, from_file: str, anchor: str = "", text: str | None = None) -> str:
    rel = Path(target).as_posix()
    depth = len(PurePosixPath(from_file).parts) - 1
    href = "../" * depth + rel + (f"#{anchor}" if anchor else "")
    return f"[{text or PurePosixPath(rel).name}]({href.replace(' ', '%20')})"


SKIP_SECTIONS = {"contents", "inventory", "not covered yet", "running tests"}


def documented_in(path: str, writeups: dict[str, list[tuple[str, str, str]]]) -> tuple[str, str] | None:
    """The write-up section that covers this file, if any.

    Best match first: a heading naming the file, then a section saying
    "Test file: <path>", then any section quoting the full path, then the name.
    Only write-ups in the same top-level folder (backend, crawler, frontend) count.
    """
    p = PurePosixPath(path)
    top = p.parts[0]
    candidates = [w for w in writeups if PurePosixPath(w).parts[0] == top]
    tiers: list[list[tuple[str, str]]] = [[], [], [], []]
    for doc in candidates:
        for title, anchor, body in writeups[doc]:
            if not anchor:
                continue
            if title in (p.name, p.stem) or title.startswith(p.name + " "):
                tiers[0].append((doc, anchor))
            if title.lower() in SKIP_SECTIONS:
                continue
            if re.search(r"test file:?\**\s*`?" + re.escape(path), body, re.I):
                tiers[1].append((doc, anchor))
            elif path in body:
                tiers[2].append((doc, anchor))
            elif re.search(r"(?<!\w)" + re.escape(p.name), body):
                tiers[3].append((doc, anchor))
    for tier in tiers:
        if tier:
            return tier[0]
    return None


def frontend_scripts(root: Path) -> list[tuple[str, str]]:
    pkg = root / "frontend/package.json"
    if not pkg.exists():
        return []
    scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    return [(k, v) for k, v in scripts.items() if k.startswith("test")]


def build(root: Path) -> tuple[str, str]:
    files = repo_files(root)
    tests = [f for f in files if is_test_file(f)]
    writeup_paths = sorted({f for f in files if is_writeup(f)})
    writeups = {w: sections(root / w) for w in writeup_paths}

    roles = {f: role_of(f, root) for f in tests}
    cases: dict[str, list[tuple[str, str]]] = {}
    for f in tests:
        if roles[f] != "tests":
            continue
        source = (root / f).read_text(encoding="utf-8", errors="replace")
        cases[f] = python_cases(source) if f.endswith(".py") else js_cases(source)

    by_suite: dict[str, list[str]] = defaultdict(list)
    for f in tests:
        by_suite[suite_of(f)[0]].append(f)
    for prefix, _, _ in SUITES:
        by_suite.setdefault(prefix, [])
    order = [p for p, _, _ in SUITES] + sorted(k for k in by_suite if k not in {p for p, _, _ in SUITES})

    # ---- whole-app index
    out: list[str] = []
    total_files = sum(1 for f in tests if roles[f] == "tests")
    total_cases = sum(len(c) for c in cases.values())
    out.append(f"**{total_files} test files, {total_cases} named test cases** "
               f"(Python `test_*` functions; script-style `.mjs` files count as one file each).\n")
    out.append("| Suite | Test files | Named cases | How to run |")
    out.append("|---|---:|---:|---|")
    for prefix in order:
        label, run = suite_of(prefix + "x")[1:] if prefix else ("Other", "See the file itself.")
        files_here = [f for f in by_suite[prefix] if roles[f] == "tests"]
        if not files_here and prefix != "tests/end-to-end/":
            continue
        n_cases = sum(len(cases.get(f, [])) for f in files_here)
        out.append(f"| [{label}](#{slugify(label)}) | {len(files_here)} | {n_cases} | {run} |")
    out.append("")

    for prefix in order:
        label = suite_of(prefix + "x")[1] if prefix else "Other"
        files_here = by_suite[prefix]
        if not files_here and prefix != "tests/end-to-end/":
            continue
        out.append(f"### {label}\n")
        if not files_here:
            out.append("Empty for now. Full-app tests go in `tests/end-to-end/`.\n")
            continue
        if prefix == "frontend/tests/":
            for name, cmd in frontend_scripts(root):
                out.append(f"- `npm run {name}` runs `{cmd}`")
            out.append("")
        out.append("| File | Kind | Cases | Write-up |")
        out.append("|---|---|---:|---|")
        for f in files_here:
            role = roles[f]
            n = (len(cases[f]) if cases[f] or f.endswith(".py") else "script") if f in cases else ""
            if role in ("write-up", "empty placeholder"):
                doc = ""
            else:
                hit = documented_in(f, writeups)
                doc = link(hit[0], WHOLE_APP, hit[1], PurePosixPath(hit[0]).name) if hit else ""
            short = f[len(prefix):] if prefix else f
            out.append(f"| {link(f, WHOLE_APP, text=short)} | {role} | {n} | {doc} |")
        out.append("")

    # ---- every test case
    cs: list[str] = []
    cs.append("## Write-ups of what was tested\n")
    cs.append("Hand-written notes: the cases each suite covers, how to run them, and results.\n")
    for w in writeup_paths:
        cs.append(f"- {link(w, CASES, text=w)}")
    cs.append("")
    undocumented = [f for f in cases if not documented_in(f, writeups)]
    for prefix in order:
        label = suite_of(prefix + "x")[1] if prefix else "Other"
        files_here = [f for f in by_suite[prefix] if f in cases]
        if not files_here:
            continue
        cs.append(f"## {label}\n")
        for f in files_here:
            hit = documented_in(f, writeups)
            note = f" · write-up: {link(hit[0], CASES, hit[1], PurePosixPath(hit[0]).name)}" if hit else ""
            cs.append(f"### {link(f, CASES, text=f)}\n")
            cs.append(f"{len(cases[f])} cases{note}\n" if cases[f] else
                      f"Script-style file, run as a whole{note}\n")
            for name, doc in cases[f]:
                cs.append(f"- `{name}`" + (f": {doc}" if doc else ""))
            if cases[f]:
                cs.append("")
    empty = [f for f in tests if roles[f] == "empty placeholder"]
    if empty:
        cs.append("## Empty placeholders (no tests yet)\n")
        for f in empty:
            cs.append(f"- {link(f, CASES, text=f)}")
        cs.append("")
    if undocumented:
        cs.append("## Not in any write-up yet\n")
        cs.append("These test files have no matching heading in a `test_case.md`.\n")
        for f in undocumented:
            cs.append(f"- {link(f, CASES, text=f)}")
        cs.append("")
    return "\n".join(out).rstrip() + "\n", "\n".join(cs).rstrip() + "\n"


# ---------------------------------------------------------------- writing

SKELETONS = {
    WHOLE_APP: "# Test index of the whole app\n\n"
               "Generated by `scripts/update_test_index.py`. Edit outside the markers only.\n\n",
    CASES: "# All test cases that were tested\n\n"
           "Generated by `scripts/update_test_index.py`. Edit outside the markers only.\n\n",
}


def splice(existing: str | None, path: str, body: str) -> str:
    if existing is None or START not in existing or END not in existing:
        head = existing.rstrip() + "\n\n" if existing else SKELETONS[path]
        return f"{head}{START}\n{body}{END}\n"
    before, rest = existing.split(START, 1)
    _, after = rest.split(END, 1)
    return f"{before}{START}\n{body}{END}{after}"


def install_hook(root: Path) -> Path:
    hooks = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=root,
                           check=True, capture_output=True, text=True).stdout.strip()
    target = (root / hooks / "pre-commit")
    if target.exists() and "update_test_index.py" not in target.read_text(errors="replace"):
        raise SystemExit(f"{target} already exists and is not ours; add this line to it:\n"
                         "  python scripts/update_test_index.py --quiet && git add tests/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(HOOK.encode("utf-8"))  # LF endings, so Git for Windows' sh can run it
    target.chmod(0o755)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if an index is stale")
    parser.add_argument("--install-hook", action="store_true", help="install the git pre-commit hook")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True,
                               capture_output=True, text=True).stdout.strip())
    if args.install_hook:
        print(f"installed {install_hook(root)}")

    whole, cases = build(root)
    stale = []
    for path, body in ((WHOLE_APP, whole), (CASES, cases)):
        file = root / path
        existing = file.read_text(encoding="utf-8") if file.exists() else None
        new = splice(existing, path, body)
        if new != existing:
            stale.append(path)
            if not args.check:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(new.encode("utf-8"))
    if args.check:
        for path in stale:
            print(f"stale: {path} (run python scripts/update_test_index.py)")
        return 1 if stale else 0
    if not args.quiet:
        print("updated: " + ", ".join(stale) if stale else "test indexes already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
