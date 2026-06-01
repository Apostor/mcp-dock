from __future__ import annotations

import hmac
import re
import time
import uuid
from typing import Annotated, Any

import yaml
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from pydantic import AfterValidator, BaseModel, model_validator
from starlette.types import ASGIApp, Receive, Scope, Send

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_request
from fastmcp.tools.base import ToolResult

from core.logging import AuditLogger

_KEY_RE = re.compile(r"^mcp-[A-Za-z0-9_-]{16,}$")


def _validate_api_key(v: str) -> str:
    if not _KEY_RE.match(v):
        raise ValueError(
            "API keys must start with 'mcp-' followed by at least 16 alphanumeric/_/- chars"
        )
    return v


class ServerPolicy(BaseModel):
    allowlist: list[str] = []
    blocklist: list[str] = []

    @model_validator(mode="after")
    def _validate(self) -> "ServerPolicy":
        if self.allowlist and self.blocklist:
            raise ValueError("Specify allowlist OR blocklist per server, not both")
        return self


class GatewayConfig(BaseModel):
    clients: dict[str, Annotated[str, AfterValidator(_validate_api_key)]]
    servers: dict[str, ServerPolicy] = {}

    @classmethod
    def load(cls, path: str) -> "GatewayConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data or {})

    def resolve_client(self, api_key: str) -> str | None:
        for name, key in self.clients.items():
            if hmac.compare_digest(key, api_key):
                return name
        return None

    def is_tool_allowed(self, server: str, tool: str) -> bool:
        policy = self.servers.get(server)
        if policy is None:
            return True
        if policy.allowlist:
            return tool in policy.allowlist
        if policy.blocklist:
            return tool not in policy.blocklist
        return True


# ---------------------------------------------------------------------------
# HTTP-level auth middleware (pure ASGI)
# ---------------------------------------------------------------------------

async def _send_401(send: Send, message: str) -> None:
    body = message.encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


_AUTH_EXEMPT_RE = re.compile(r"^/[^/]+/(auth/start|auth/callback|health)$")


class AuthMiddleware:
    def __init__(self, app: ASGIApp, config: GatewayConfig) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # OAuth browser redirects and health checks bypass API key enforcement.
        # /auth/start and /auth/callback cannot carry headers (browser navigation);
        # they are protected by the OAuth state parameter instead.
        path: str = scope.get("path", "")
        if _AUTH_EXEMPT_RE.search(path):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()

        if not auth.startswith("Bearer "):
            await _send_401(send, "Missing or invalid Authorization header")
            return

        client = self.config.resolve_client(auth[len("Bearer "):])
        if client is None:
            await _send_401(send, "Unknown API key")
            return

        scope["gateway_client"] = client
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# MCP-level gateway middleware (FastMCP Middleware subclass)
# ---------------------------------------------------------------------------

class GatewayMiddleware(Middleware):
    def __init__(
        self,
        server_name: str,
        config: GatewayConfig,
        logger: AuditLogger,
    ) -> None:
        self.server_name = server_name
        self.config = config
        self.logger = logger

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: Any,
    ) -> ToolResult:
        tool_name = context.message.name
        args_keys = list((context.message.arguments or {}).keys())
        start = time.perf_counter()

        try:
            req = get_http_request()
            instance = req.query_params.get("instance", "default")
            client = req.scope.get("gateway_client", "unknown")
        except RuntimeError:
            instance = "default"
            client = "unknown"

        request_id = str(uuid.uuid4())

        if not self.config.is_tool_allowed(self.server_name, tool_name):
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.logger.log(
                request_id=request_id,
                client=client,
                server=self.server_name,
                tool=tool_name,
                instance=instance,
                status="blocked",
                latency_ms=latency_ms,
                error_code=-32001,
                tool_args_redacted=args_keys,
            )
            raise McpError(
                ErrorData(
                    code=-32001,
                    message=f"Tool '{tool_name}' is blocked by gateway policy",
                )
            )

        try:
            result = await call_next(context)
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.logger.log(
                request_id=request_id,
                client=client,
                server=self.server_name,
                tool=tool_name,
                instance=instance,
                status="ok",
                latency_ms=latency_ms,
                error_code=None,
                tool_args_redacted=args_keys,
            )
            return result
        except Exception:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.logger.log(
                request_id=request_id,
                client=client,
                server=self.server_name,
                tool=tool_name,
                instance=instance,
                status="error",
                latency_ms=latency_ms,
                error_code=None,
                tool_args_redacted=args_keys,
            )
            raise
