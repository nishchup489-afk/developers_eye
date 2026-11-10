"""Authenticate the server-only edge hop before accepting its visitor identity."""
import hmac
from ipaddress import ip_address

from starlette.responses import JSONResponse


class EdgeTrustMiddleware:
    def __init__(self, app, *, secret: str | None):
        self.app = app
        self.secret = secret.encode() if secret else None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.secret is None:
            return await self.app(scope, receive, send)
        headers = scope.get("headers", [])
        if scope["path"] == "/health" and scope["method"] in {"GET", "HEAD"}:
            # A public liveness check never imports a caller-provided identity.
            scope = {**scope, "headers": [(k, v) for k, v in headers if k.lower() not in
                     {b"x-eye-client-ip", b"x-edge-secret"}]}
            return await self.app(scope, receive, send)
        secrets = [v for k, v in headers if k.lower() == b"x-edge-secret"]
        if len(secrets) != 1 or not hmac.compare_digest(secrets[0], self.secret):
            return await JSONResponse({"detail": "Forbidden"}, status_code=403,
                                      headers={"Cache-Control": "no-store"})(scope, receive, send)
        identities = [v for k, v in headers if k.lower() == b"x-eye-client-ip"]
        if identities:
            try:
                if len(identities) != 1 or len(identities[0]) > 45:
                    raise ValueError("ambiguous identity")
                raw = identities[0].decode("ascii")
                if "%" in raw:
                    raise ValueError("scoped IP is not a visitor identity")
                identity = str(ip_address(raw))
            except (ValueError, UnicodeError):
                return await JSONResponse({"detail": "Invalid visitor identity"}, status_code=400,
                                          headers={"Cache-Control": "no-store"})(scope, receive, send)
            scope = {**scope, "client": (identity, 0)}
        return await self.app(scope, receive, send)
