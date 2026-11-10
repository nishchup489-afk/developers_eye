"""Load test settings (TEST_DATABASE_URL, ...) from the repo-root .env.local.

This runs before any test module is imported, so module-level skip checks
already see the values. Variables set in the shell still win.
"""

from backend.core.local_env import load_local_env

load_local_env(__file__)
