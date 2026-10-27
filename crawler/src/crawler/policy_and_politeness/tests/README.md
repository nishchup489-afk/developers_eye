# Running the policy and politeness tests

What each test checks is in [test_case.md](test_case.md).

This folder mixes pytest suites and standalone Colorama scripts. Run each kind the right way.

## Pytest suites (offline)

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/policy_and_politeness/tests/test_robots_rules.py crawler/src/crawler/policy_and_politeness/tests/test_redirect_policy.py crawler/src/crawler/policy_and_politeness/tests/test_politeness_policy.py crawler/src/crawler/policy_and_politeness/tests/test_policy_coordinator.py -q
```

These mock DNS, robots, and the fetcher, so there is no network or database access.

## Standalone scripts

Each script has its own runner and prints PASS/FAIL lines with a summary.

Offline, no database:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.policy_and_politeness.tests.test_host_policy
.\crawler\.venv\Scripts\python.exe -m crawler.policy_and_politeness.tests.test_dns_policy
```

Do not run `test_dns_policy.py` through pytest. It has helper functions named `test_*` that take arguments, so pytest would collect them wrongly. The [crawler/tests README](../../../../tests/README.md) excludes it from the pytest run for the same reason.

Needs PostgreSQL:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.policy_and_politeness.tests.test_robots_policy
```

`test_robots_policy.py` uses the backend's `DATABASE_URL` to test the `robots_cache` table. It rolls back its transaction and uses fake hosts with a fake fetcher, but point it at a development or test database, never production.
