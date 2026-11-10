import runpy
from pathlib import Path
import pytest

validate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "benchmarks" / "bench_safety.py"))["benchmark_database_url"]


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg:///benchmark_test?host=/var/run/postgresql",
    "postgresql+asyncpg://user:secret@localhost/crawler_test",
])
def test_socket_and_tcp_test_databases_are_accepted(url):
    assert validate(url) == url


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://test-host/production?application_name=test",
    "postgresql+asyncpg://user:test@localhost/production",
    "postgresql+asyncpg://localhost/production?host=/tmp/test",
    "sqlite:///crawler_test", "invalid", "",
])
def test_host_password_or_query_cannot_make_a_production_database_disposable(url):
    with pytest.raises(ValueError, match="BENCH_DATABASE_URL"):
        validate(url)
