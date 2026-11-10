"""Edge credentials gate every protected route before visitor identity is trusted."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.api.edge_trust import EdgeTrustMiddleware
from backend.api.request_limits import RateLimiter, client_key
from backend.core.config import Settings

SECRET = "test-edge-credential-" + "a" * 40


def edge_client(secret=SECRET):
    app = FastAPI()
    limiter = RateLimiter(1, 1)

    @app.get("/health")
    @app.get("/health/db")
    @app.get("/search")
    @app.get("/admin/report")
    def identity(request: Request):
        return {"identity": client_key(request), "limited": bool(limiter.acquire(client_key(request)))}

    app.add_middleware(EdgeTrustMiddleware, secret=secret)
    return TestClient(app)


@pytest.mark.parametrize("path", ["/search", "/health/db", "/admin/report", "/openapi.json", "/docs"])
@pytest.mark.parametrize("headers", [{}, {"X-Edge-Secret": "wrong", "X-Eye-Client-IP": "198.51.100.1"}])
def test_edge_rejects_direct_calls(path, headers):
    response = edge_client().get(path, headers=headers)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_authenticated_visitors_get_separate_rate_limit_buckets():
    client = edge_client()
    def visit(ip):
        return client.get("/search", headers={"X-Edge-Secret": SECRET, "X-Eye-Client-IP": ip,
                                               "X-Forwarded-For": "203.0.113.99"}).json()
    assert visit("198.51.100.1") == {"identity": "198.51.100.1", "limited": False}
    assert visit("198.51.100.1")["limited"]
    assert visit("2001:db8::1") == {"identity": "2001:db8::1", "limited": False}


@pytest.mark.parametrize("ip", ["not-an-ip", "198.51.100.1, 198.51.100.2", "fe80::1%eth0", "x" * 46])
def test_authenticated_invalid_identity_is_rejected(ip):
    assert edge_client().get("/search", headers={"X-Edge-Secret": SECRET, "X-Eye-Client-IP": ip}).status_code == 400


def test_duplicate_credentials_or_identity_are_rejected():
    client = edge_client()
    assert client.get("/search", headers=[("X-Edge-Secret", SECRET), ("X-Edge-Secret", SECRET)]).status_code == 403
    assert client.get("/search", headers=[("X-Edge-Secret", SECRET), ("X-Eye-Client-IP", "198.51.100.1"),
                                          ("X-Eye-Client-IP", "198.51.100.2")]).status_code == 400


def test_health_and_local_development_never_import_spoofed_identity():
    assert edge_client().get("/health", headers={"X-Eye-Client-IP": "198.51.100.1"}).json()["identity"] == "testclient"
    assert edge_client(None).get("/search", headers={"X-Eye-Client-IP": "198.51.100.1"}).json()["identity"] == "testclient"


@pytest.mark.parametrize("secret", [None, "", "short", "a" * 31, "a" * 32 + "\n"])
def test_production_requires_a_valid_edge_secret(secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+asyncpg:///test", app_env="production", edge_shared_secret=secret)
