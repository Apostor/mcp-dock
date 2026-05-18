from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


def create_server(name: str) -> FastMCP:
    server = FastMCP(name)

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": name})

    return server
