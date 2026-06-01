import contextlib
import importlib
import importlib.util
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import ASGIApp

from core.settings import get_settings

_BASE_DIR = Path(__file__).parent

# (module_key_in_sys_modules, file_path_relative_to_project, attr)
_SERVER_REGISTRY: dict[str, tuple[str, str, str]] = {
    "trello":       ("servers.trello.server",       "servers/trello/server.py",       "trello"),
    "google-drive": ("servers.google_drive.server", "servers/google-drive/server.py", "google_drive"),
    "github":       ("servers.github.server",       "servers/github/server.py",       "github"),
    "gitlab":       ("servers.gitlab.server",       "servers/gitlab/server.py",       "gitlab"),
    "slack":        ("servers.slack.server",        "servers/slack/server.py",        "slack"),
    "notion":       ("servers.notion.server",       "servers/notion/server.py",       "notion"),
    "linear":       ("servers.linear.server",       "servers/linear/server.py",       "linear"),
    "jira":         ("servers.jira.server",         "servers/jira/server.py",         "jira"),
    "telegram":     ("servers.telegram.server",     "servers/telegram/server.py",     "telegram"),
    "whatsapp":     ("servers.whatsapp.server",     "servers/whatsapp/server.py",     "whatsapp"),
}


def _load_server(module_key: str, file_rel_path: str, attr: str):
    if module_key not in sys.modules:
        path = _BASE_DIR / file_rel_path
        if path.exists():
            # Register stub parent packages so dotted imports resolve correctly.
            parts = module_key.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[:i])
                if parent not in sys.modules:
                    stub = types.ModuleType(parent)
                    stub.__path__ = [str(path.parents[len(parts) - 1 - i])]
                    sys.modules[parent] = stub
            spec = importlib.util.spec_from_file_location(module_key, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_key] = module
            spec.loader.exec_module(module)
        else:
            importlib.import_module(module_key)
    return getattr(sys.modules[module_key], attr)


def create_app(enabled_servers: list[str] | None = None) -> ASGIApp:
    if enabled_servers is None:
        enabled_servers = get_settings().get_enabled_servers()

    http_apps = []
    routes = []
    for name in enabled_servers:
        if name not in _SERVER_REGISTRY:
            continue
        module_key, file_rel_path, attr = _SERVER_REGISTRY[name]
        server = _load_server(module_key, file_rel_path, attr)
        http_app = server.http_app()
        http_apps.append(http_app)
        routes.append(Mount(f"/{name}", app=http_app))

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            for ha in http_apps:
                await stack.enter_async_context(ha.router.lifespan_context(_app))
            yield

    starlette_app = Starlette(routes=routes, lifespan=lifespan)

    settings = get_settings()
    if settings.gateway_enabled:
        from core.gateway import GatewayConfig, AuthMiddleware
        try:
            config = GatewayConfig.load(settings.gateway_config_path)
            return AuthMiddleware(starlette_app, config)
        except FileNotFoundError:
            raise RuntimeError(
                f"Gateway enabled but config not found at '{settings.gateway_config_path}'. "
                "Create gateway.yaml from gateway.yaml.example or set GATEWAY_ENABLED=false."
            )

    return starlette_app


app = create_app()
