import httpx
import pytest
from fastmcp import FastMCP


def test_create_server_returns_fastmcp_instance():
    from core.factory import create_server
    server = create_server("trello")
    assert isinstance(server, FastMCP)


@pytest.mark.anyio
async def test_health_endpoint_returns_200():
    from core.factory import create_server
    server = create_server("trello")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.http_app()), base_url="http://test"
    ) as client:
        response = await client.get("/trello/health")
    assert response.status_code == 200
