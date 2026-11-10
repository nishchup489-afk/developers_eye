"""Load test settings from the repository-root ``.env.local``.

Both pytest projects (``backend/`` and ``crawler/``) call :func:`load_local_env`
from their top-level ``tests/conftest.py``, so ``TEST_DATABASE_URL`` and the
other test switches no longer have to be exported in every new terminal.

Rules, kept deliberately narrow:

* Only test settings are read: keys that start with ``TEST_`` or contain
  ``_TEST_`` (for example ``OVERVIEW_TEST_USE_LOCAL_DB``). A production
  ``DATABASE_URL`` in the same file is ignored, so tests can never pick it up.
* A variable already set in the shell wins over the file.
* Only the ``.env.local`` at the repository root (the folder holding ``.git``)
  is used, never the per-package ones in ``backend/`` or ``crawler/``, so there
  is exactly one place to edit. Without a ``.git`` folder (a copied tree, a
  container) the nearest ``.env.local`` above the caller is used. A missing
  file is not an error.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE_NAME = ".env.local"


def is_test_key(key: str) -> bool:
    return key.startswith("TEST_") or "_TEST_" in key


def find_env_file(start: Path) -> Path | None:
    start = start.resolve()
    folders = [start if start.is_dir() else start.parent, *start.parents]
    for folder in folders:
        if (folder / ".git").exists():  # repository root: its file or nothing
            candidate = folder / ENV_FILE_NAME
            return candidate if candidate.is_file() else None
    for folder in folders:
        candidate = folder / ENV_FILE_NAME
        if candidate.is_file():
            return candidate
    return None


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_local_env(start: str | Path) -> dict[str, str]:
    """Set test variables from the nearest ``.env.local``; return what was set."""
    path = find_env_file(Path(start))
    if path is None:
        return {}
    loaded: dict[str, str] = {}
    for key, value in parse_env_file(path).items():
        if is_test_key(key) and value and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded
