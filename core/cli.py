import typer
import uvicorn

app = typer.Typer()


@app.command()
def run(
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, "--reload/--no-reload", help="Enable auto-reload"),
):
    """Start the mcp-dock server."""
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=reload)


@app.command()
def new(name: str):
    """Scaffold a new MCP server under servers/<name>/."""
    from pathlib import Path

    module_name = name.replace("-", "_")
    base = Path("servers") / name
    tests_dir = base / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    (base / "__init__.py").write_text("")

    (base / "server.py").write_text(
        f'from core.factory import create_server\n'
        f'\n'
        f'{module_name} = create_server("{name}")\n'
        f'\n'
        f'\n'
        f'@{module_name}.tool()\n'
        f'async def placeholder() -> str:\n'
        f'    """Replace this with a real tool."""\n'
        f'    return "ok"\n'
    )

    (base / "pyproject.toml").write_text(
        f'[project]\n'
        f'name = "mcp-dock-{name}"\n'
        f'version = "0.1.0"\n'
        f'requires-python = ">=3.12"\n'
        f'dependencies = ["mcp-dock-core"]\n'
        f'\n'
        f'[tool.uv.sources]\n'
        f'mcp-dock-core = {{ workspace = true }}\n'
        f'\n'
        f'[build-system]\n'
        f'requires = ["hatchling"]\n'
        f'build-backend = "hatchling.build"\n'
        f'\n'
        f'[tool.hatch.build.targets.wheel]\n'
        f'packages = ["{module_name}"]\n'
    )

    (base / "README.md").write_text(
        f'# {name} MCP Server\n'
        f'\n'
        f'## Required Headers\n'
        f'\n'
        f'| Header | Description |\n'
        f'|--------|-------------|\n'
        f'| `x-{name}-token` | API token |\n'
        f'\n'
        f'## Tools\n'
        f'\n'
        f'| Tool | Description |\n'
        f'|------|-------------|\n'
        f'| `placeholder` | Replace with real tools |\n'
    )

    (tests_dir / "__init__.py").write_text("")

    (tests_dir / "test_server.py").write_text(
        f'import pytest\n'
        f'import httpx\n'
        f'\n'
        f'\n'
        f'@pytest.mark.anyio\n'
        f'async def test_health_returns_200():\n'
        f'    from servers.{module_name}.server import {module_name}\n'
        f'    async with httpx.AsyncClient(\n'
        f'        transport=httpx.ASGITransport(app={module_name}.http_app()), base_url="http://test"\n'
        f'    ) as client:\n'
        f'        response = await client.get("/health")\n'
        f'    assert response.status_code == 200\n'
    )

    typer.echo(f"Created servers/{name}/")


def main():
    app()
