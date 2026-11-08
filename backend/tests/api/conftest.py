"""Every API test starts with unlimited, empty rate limiters.

The TestClient sends every request from one address, so a shared limiter would
make tests fail depending on how many ran before them. Tests that exercise rate
limiting install their own limiter.
"""

import pytest

import backend.api.search as search_api
from backend.api.request_limits import RateLimiter


@pytest.fixture(autouse=True)
def unlimited_rate(monkeypatch):
    monkeypatch.setattr(search_api, "search_rate_limiter", RateLimiter(0, 1))
    monkeypatch.setattr(search_api, "suggest_rate_limiter", RateLimiter(0, 1))
