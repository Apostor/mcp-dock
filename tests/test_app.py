import sys
import types

import httpx
import pytest
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS
from starlette.applications import Starlette

from core.factory import create_server


@pytest.fixture
def inject_stub(monkeypatch):
    """Injects a stub FastMCP server into sys.modules for a given registry entry."""
    def _inject(name: str, module_path: str, attr: str) -> None:
        server = create_server(name)
        mod = types.ModuleType(module_path)
        setattr(mod, attr, server)
        monkeypatch.setitem(sys.modules, module_path, mod)
    return _inject


def test_create_app_returns_starlette_instance():
    from app import create_app
    assert isinstance(create_app([]), Starlette)


@pytest.mark.anyio
async def test_enabled_server_health_returns_200(inject_stub):
    inject_stub("trello", "servers.trello.server", "trello")
    from app import create_app
    root = create_app(["trello"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=root), base_url="http://test"
    ) as client:
        response = await client.get("/trello/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_two_enabled_servers_both_respond(inject_stub):
    inject_stub("trello", "servers.trello.server", "trello")
    inject_stub("github", "servers.github.server", "github")
    from app import create_app
    root = create_app(["trello", "github"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=root), base_url="http://test"
    ) as client:
        assert (await client.get("/trello/health")).status_code == 200
        assert (await client.get("/github/health")).status_code == 200


@pytest.mark.anyio
async def test_mcp_error_from_tool_returns_non_500(inject_stub, monkeypatch):
    server = create_server("trello")

    @server.tool()
    async def get_cards() -> list:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="No credentials configured"))

    mod = types.ModuleType("servers.trello.server")
    mod.trello = server
    monkeypatch.setitem(sys.modules, "servers.trello.server", mod)

    from app import create_app
    root = create_app(["trello"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=root), base_url="http://test"
    ) as client:
        response = await client.post(
            "/trello/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_cards", "arguments": {}},
            },
            headers={"content-type": "application/json", "accept": "application/json"},
        )
    assert response.status_code != 500


@pytest.mark.anyio
async def test_disabled_server_health_returns_404(inject_stub):
    inject_stub("trello", "servers.trello.server", "trello")
    from app import create_app
    root = create_app([])  # trello NOT enabled
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=root), base_url="http://test"
    ) as client:
        response = await client.get("/trello/health")
    assert response.status_code == 404
