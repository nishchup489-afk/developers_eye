"""Colorama status output for the Developer's Eye fetcher tests.

Install: poetry add --group dev pytest colorama
Run:     poetry run pytest tests/test_fetcher.py -q -s
"""

from __future__ import annotations

import pytest
from colorama import Fore, Style, just_fix_windows_console

just_fix_windows_console()


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != "call":
        return
    if report.passed and not hasattr(report, "wasxfail"):
        label, color = "PASS", Fore.GREEN
    elif hasattr(report, "wasxfail") and report.skipped:
        label, color = "XFAIL", Fore.YELLOW
    elif hasattr(report, "wasxfail") and report.passed:
        label, color = "XPASS", Fore.RED
    elif report.failed:
        label, color = "FAIL", Fore.RED
    else:
        label, color = "SKIP", Fore.YELLOW
    print(f"{color}[{label}]{Style.RESET_ALL} {report.nodeid}", flush=True)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    xfailed = len(terminalreporter.stats.get("xfailed", []))
    errors = len(terminalreporter.stats.get("error", []))
    color = Fore.RED if (failed or errors) else Fore.GREEN
    terminalreporter.write_line(
        f"{color}Fetcher test summary: {passed} passed, {failed} failed, "
        f"{errors} errors, {xfailed} expected failures{Style.RESET_ALL}"
    )
