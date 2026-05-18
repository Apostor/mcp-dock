import importlib

from starlette.applications import Starlette
from starlette.routing import Mount

from core.settings import get_settings

_SERVER_REGISTRY: dict[str, tuple[str, str]] = {
    "trello":       ("servers.trello.server",        "trello"),
    "google-drive": ("servers.google_drive.server",  "google_drive"),
    "github":       ("servers.github.server",        "github"),
    "gitlab":       ("servers.gitlab.server",        "gitlab"),
    "slack":        ("servers.slack.server",         "slack"),
    "notion":       ("servers.notion.server",        "notion"),
    "linear":       ("servers.linear.server",        "linear"),
    "jira":         ("servers.jira.server",          "jira"),
    "telegram":     ("servers.telegram.server",      "telegram"),
    "whatsapp":     ("servers.whatsapp.server",      "whatsapp"),
}


def create_app(enabled_servers: list[str] | None = None) -> Starlette:
    if enabled_servers is None:
        enabled_servers = get_settings().get_enabled_servers()

    routes = []
    for name in enabled_servers:
        if name not in _SERVER_REGISTRY:
            continue
        module_path, attr = _SERVER_REGISTRY[name]
        module = importlib.import_module(module_path)
        server = getattr(module, attr)
        routes.append(Mount(f"/{name}", app=server.http_app()))

    return Starlette(routes=routes)


app = create_app()
