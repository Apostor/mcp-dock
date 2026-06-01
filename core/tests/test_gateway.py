import textwrap
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_KEY_A = "mcp-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
VALID_KEY_B = "mcp-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

MINIMAL_YAML = textwrap.dedent(f"""\
    clients:
      claude: {VALID_KEY_A}
""")

POLICY_YAML = textwrap.dedent(f"""\
    clients:
      claude: {VALID_KEY_A}
    servers:
      google-drive:
        blocklist:
          - delete_file
""")

ALLOWLIST_YAML = textwrap.dedent(f"""\
    clients:
      claude: {VALID_KEY_A}
    servers:
      google-drive:
        allowlist:
          - list_files
          - search
""")


@pytest.fixture
def config_file(tmp_path):
    """Returns a factory that writes YAML to a temp file and returns the path."""
    def _write(content: str) -> str:
        p = tmp_path / "gateway.yaml"
        p.write_text(content)
        return str(p)
    return _write


# ---------------------------------------------------------------------------
# Cycle 1 — GatewayConfig: basic load
# ---------------------------------------------------------------------------

def test_gateway_config_loads_from_yaml(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(MINIMAL_YAML))
    assert "claude" in cfg.clients


# ---------------------------------------------------------------------------
# Cycle 2 — GatewayConfig: API key validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_key", [
    "no-prefix",
    "mcp-short",        # only 5 chars after prefix
    "sk-something",
    "mcp-has spaces here",
    "",
])
def test_invalid_api_key_raises_at_load(config_file, bad_key):
    from core.gateway import GatewayConfig
    import pydantic
    yaml_text = f"clients:\n  claude: '{bad_key}'\n"
    with pytest.raises((pydantic.ValidationError, ValueError)):
        GatewayConfig.load(config_file(yaml_text))


# ---------------------------------------------------------------------------
# Cycle 3 — resolve_client and is_tool_allowed
# ---------------------------------------------------------------------------

def test_resolve_client_returns_name_for_valid_key(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(MINIMAL_YAML))
    assert cfg.resolve_client(VALID_KEY_A) == "claude"


def test_resolve_client_returns_none_for_unknown_key(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(MINIMAL_YAML))
    assert cfg.resolve_client(VALID_KEY_B) is None


def test_blocklisted_tool_is_not_allowed(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(POLICY_YAML))
    assert cfg.is_tool_allowed("google-drive", "delete_file") is False


def test_non_blocklisted_tool_is_allowed(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(POLICY_YAML))
    assert cfg.is_tool_allowed("google-drive", "list_files") is True


def test_allowlisted_tool_is_allowed(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(ALLOWLIST_YAML))
    assert cfg.is_tool_allowed("google-drive", "list_files") is True


def test_tool_not_in_allowlist_is_blocked(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(ALLOWLIST_YAML))
    assert cfg.is_tool_allowed("google-drive", "delete_file") is False


def test_no_policy_allows_all_tools(config_file):
    from core.gateway import GatewayConfig
    cfg = GatewayConfig.load(config_file(MINIMAL_YAML))
    assert cfg.is_tool_allowed("google-drive", "delete_file") is True


def test_allowlist_and_blocklist_raises(config_file):
    from core.gateway import GatewayConfig
    import pydantic
    yaml_text = textwrap.dedent(f"""\
        clients:
          claude: {VALID_KEY_A}
        servers:
          google-drive:
            allowlist: [list_files]
            blocklist: [delete_file]
    """)
    with pytest.raises(pydantic.ValidationError):
        GatewayConfig.load(config_file(yaml_text))


# ---------------------------------------------------------------------------
# Cycle 4 — AuthMiddleware
# ---------------------------------------------------------------------------

import httpx
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse




def _make_app(config_yaml: str, tmp_path) -> "ASGIApp":
    from core.gateway import GatewayConfig, AuthMiddleware
    p = tmp_path / "gw.yaml"
    p.write_text(config_yaml)
    cfg = GatewayConfig.load(str(p))

    async def _ok(request):
        client = request.scope.get("gateway_client", "MISSING")
        return PlainTextResponse(f"ok:{client}")

    app = Starlette(routes=[Route("/ping", _ok)])
    return AuthMiddleware(app, cfg)


@pytest.mark.anyio
async def test_missing_auth_header_returns_401(tmp_path):
    app = _make_app(MINIMAL_YAML, tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ping")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_unknown_api_key_returns_401(tmp_path):
    app = _make_app(MINIMAL_YAML, tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ping", headers={"Authorization": f"Bearer {VALID_KEY_B}"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_valid_key_passes_through_and_sets_client(tmp_path):
    app = _make_app(MINIMAL_YAML, tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/ping", headers={"Authorization": f"Bearer {VALID_KEY_A}"})
    assert resp.status_code == 200
    assert resp.text == "ok:claude"


@pytest.mark.parametrize("path", [
    "/google-drive/auth/start",
    "/google-drive/auth/callback",
    "/google-drive/health",
])
@pytest.mark.anyio
async def test_auth_exempt_paths_bypass_api_key_check(tmp_path, path):
    """OAuth browser redirects and health checks must work without an API key."""
    from core.gateway import GatewayConfig, AuthMiddleware

    p = tmp_path / "gw.yaml"
    p.write_text(MINIMAL_YAML)
    cfg = GatewayConfig.load(str(p))

    async def _ok(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = AuthMiddleware(_ok, cfg)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(path)  # no Authorization header
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cycle 5 — GatewayMiddleware: governance + audit logging
# ---------------------------------------------------------------------------

def _make_server_with_gateway(policy_yaml: str, tmp_path):
    """Returns a FastMCP server with GatewayMiddleware attached and a test tool."""
    from core.gateway import GatewayConfig, GatewayMiddleware
    from core.logging import AuditLogger
    from fastmcp import FastMCP

    p = tmp_path / "gw.yaml"
    p.write_text(policy_yaml)
    cfg = GatewayConfig.load(str(p))

    server = FastMCP("test-server")

    @server.tool()
    async def delete_file(file_id: str) -> str:
        return f"deleted:{file_id}"

    @server.tool()
    async def list_files() -> list:
        return []

    logger = AuditLogger()
    server.add_middleware(GatewayMiddleware("google-drive", cfg, logger))
    return server, logger


@pytest.mark.anyio
async def test_blocklisted_tool_raises_tool_error(tmp_path):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError
    server, _ = _make_server_with_gateway(POLICY_YAML, tmp_path)
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("delete_file", {"file_id": "abc"})
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_allowed_tool_succeeds(tmp_path):
    from fastmcp import Client
    server, _ = _make_server_with_gateway(POLICY_YAML, tmp_path)
    async with Client(server) as client:
        result = await client.call_tool("list_files", {})
    assert result is not None


@pytest.mark.anyio
async def test_audit_log_emitted_on_block(tmp_path):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError
    from loguru import logger as loguru_logger
    records = []
    lid = loguru_logger.add(lambda msg: records.append(msg.record), level="INFO")
    try:
        server, _ = _make_server_with_gateway(POLICY_YAML, tmp_path)
        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool("delete_file", {"file_id": "abc"})
    finally:
        loguru_logger.remove(lid)

    audit_records = [r for r in records if r["extra"].get("audit")]
    assert len(audit_records) == 1
    extra = audit_records[0]["extra"]
    assert extra["status"] == "blocked"
    assert extra["tool"] == "delete_file"
    assert extra["error_code"] == -32001


@pytest.mark.anyio
async def test_audit_log_emitted_on_success(tmp_path):
    from fastmcp import Client
    from loguru import logger as loguru_logger
    records = []
    lid = loguru_logger.add(lambda msg: records.append(msg.record), level="INFO")
    try:
        server, _ = _make_server_with_gateway(POLICY_YAML, tmp_path)
        async with Client(server) as client:
            await client.call_tool("list_files", {})
    finally:
        loguru_logger.remove(lid)

    audit_records = [r for r in records if r["extra"].get("audit")]
    assert len(audit_records) == 1
    extra = audit_records[0]["extra"]
    assert extra["status"] == "ok"
    assert extra["tool"] == "list_files"
    assert extra["error_code"] is None


@pytest.mark.anyio
async def test_audit_log_contains_only_arg_names_not_values(tmp_path):
    from fastmcp import Client
    from loguru import logger as loguru_logger
    records = []
    lid = loguru_logger.add(lambda msg: records.append(msg.record), level="INFO")
    try:
        server, _ = _make_server_with_gateway(MINIMAL_YAML, tmp_path)
        async with Client(server) as client:
            await client.call_tool("delete_file", {"file_id": "abc"})
    finally:
        loguru_logger.remove(lid)

    audit_records = [r for r in records if r["extra"].get("audit")]
    assert len(audit_records) == 1
    extra = audit_records[0]["extra"]
    redacted = extra["tool_args_redacted"]
    assert "file_id" in redacted       # arg name is logged
    assert "abc" not in str(redacted)  # arg value is never logged


# ---------------------------------------------------------------------------
# Cycle 6 — create_server integration: gateway enabled/disabled
# ---------------------------------------------------------------------------

def test_missing_gateway_yaml_raises_at_create_server(monkeypatch, tmp_path):
    from core import factory
    monkeypatch.setenv("GATEWAY_ENABLED", "true")
    monkeypatch.setenv("GATEWAY_CONFIG_PATH", str(tmp_path / "nonexistent.yaml"))
    factory.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Gateway enabled"):
            factory.create_server("test")
    finally:
        factory.get_settings.cache_clear()


def test_gateway_disabled_create_server_succeeds_without_yaml(monkeypatch, tmp_path):
    from core import factory
    monkeypatch.setenv("GATEWAY_ENABLED", "false")
    monkeypatch.setenv("GATEWAY_CONFIG_PATH", str(tmp_path / "nonexistent.yaml"))
    factory.get_settings.cache_clear()
    try:
        server = factory.create_server("test")
        assert server is not None
    finally:
        factory.get_settings.cache_clear()
