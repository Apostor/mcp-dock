from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.settings import get_settings


def create_server(name: str, instructions: str | None = None) -> FastMCP:
    server = FastMCP(name, instructions=instructions)

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": name})

    settings = get_settings()
    if settings.gateway_enabled:
        from core.gateway import GatewayConfig, GatewayMiddleware
        from core.logging import AuditLogger
        try:
            config = GatewayConfig.load(settings.gateway_config_path)
        except FileNotFoundError:
            raise RuntimeError(
                f"Gateway enabled but config not found at '{settings.gateway_config_path}'. "
                "Create gateway.yaml from gateway.yaml.example or set GATEWAY_ENABLED=false."
            )
        server.add_middleware(GatewayMiddleware(name, config, AuditLogger()))

    return server
