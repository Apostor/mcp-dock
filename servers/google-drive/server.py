import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path
from urllib.parse import quote

from google_auth_oauthlib.flow import Flow
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.credentials import CredentialsStore
from core.factory import create_server
from core.oauth import OAuthBase
from core.settings import get_settings

google_drive = create_server(
    "google-drive",
    instructions=(
        "This is a SELF-HOSTED local Google Drive MCP server running on private server"
        "It is NOT a Claude.ai integration and has nothing to do with claude.ai settings.\n\n"
        "## Authentication\n\n"
        "When a tool returns an error containing 'Open this URL to authenticate', you MUST:\n"
        "1. Show the user the exact URL from the error message.\n"
        "2. Tell them to open it in their browser to complete Google sign-in.\n"
        "3. After they confirm sign-in is done, retry the tool call.\n\n"
        "NEVER tell the user to go to claude.ai, Settings, or Integrations — "
        "that is wrong and will not work. The auth URL is always a mcp server URL "
        "served by this MCP server.\n\n"
        "If you have shell access, run `open <url>` (macOS) or `xdg-open <url>` (Linux) "
        "to open the URL automatically.\n\n"
        "Token expiry: call the `reauth` tool, then repeat the steps above.\n\n"
        "## Working with document indices\n\n"
    ),
)

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Holds in-progress OAuth flows: {state: (flow, instance)}
_pending_flows: dict[str, tuple] = {}

oauth = OAuthBase(
    server="google-drive",
    instance="default",
    tokens_path=get_settings().tokens_path,
)
oauth.register_reauth_tool(google_drive)


def _get_token() -> str:
    from fastmcp.server.dependencies import get_http_request
    try:
        req = get_http_request()
        instance = req.query_params.get("instance", "default")
        host = req.headers.get("host", "localhost")
        scheme = req.url.scheme
    except RuntimeError:
        instance = "default"
        host, scheme = "localhost", "http"

    store = CredentialsStore(get_settings().credentials_path)
    store.resolve("google-drive", instance)

    client_oauth = OAuthBase(
        server="google-drive",
        instance=instance,
        tokens_path=get_settings().tokens_path,
    )
    try:
        return client_oauth.get_token()
    except RuntimeError:
        auth_url = (
            f"{scheme}://{host}/google-drive/auth/start"
            f"?instance={quote(instance)}"
        )
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    f"Google Drive is not authenticated yet.\n\n"
                    f"This is a self-hosted local server — do NOT go to claude.ai settings.\n\n"
                    f"Ask the user to open this URL in their browser:\n"
                    f"  {auth_url}\n\n"
                    f"After they complete Google sign-in, retry the tool call."
                ),
            )
        )


@google_drive.custom_route("/auth/start", methods=["GET"])
async def auth_start(request: Request) -> RedirectResponse:
    instance = request.query_params.get("instance", "default")

    store = CredentialsStore(get_settings().credentials_path)
    try:
        credentials_path = store.resolve("google-drive", instance)
    except McpError:
        return JSONResponse(
            {"error": f"No credentials file for instance '{instance}'"},
            status_code=400,
        )

    host = request.headers.get("host", "localhost")
    scheme = request.url.scheme
    redirect_uri = f"{scheme}://{host}/google-drive/auth/callback"

    flow = Flow.from_client_secrets_file(credentials_path, scopes=_SCOPES, redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    _pending_flows[state] = (flow, instance)

    return RedirectResponse(auth_url)


@google_drive.custom_route("/auth/callback", methods=["GET"])
async def auth_callback(request: Request) -> HTMLResponse:
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not state or state not in _pending_flows:
        return JSONResponse({"error": "Invalid or expired state"}, status_code=400)

    flow, instance = _pending_flows.pop(state)

    host = request.headers.get("host", "localhost")
    scheme = request.url.scheme
    flow.redirect_uri = f"{scheme}://{host}/google-drive/auth/callback"
    flow.fetch_token(code=code)

    client_oauth = OAuthBase(
        server="google-drive",
        instance=instance,
        tokens_path=get_settings().tokens_path,
    )
    client_oauth._save_token(flow.credentials)

    return HTMLResponse(
        "<html><body><h1>✓ Authenticated</h1>"
        "<p>Google Drive is connected. You can close this tab.</p></body></html>"
    )


def _drive_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _docs_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _sheets_service(token: str):
    import google.oauth2.credentials
    from googleapiclient.discovery import build
    creds = google.oauth2.credentials.Credentials(token=token)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Load sibling modules — each registers its tools on google_drive as a
# side-effect of being imported.  We use importlib by path because the
# parent package (servers.google_drive) is a stub with an empty __path__
# in both app.py and the test conftest, so normal subpackage imports fail.
# ---------------------------------------------------------------------------

def _load_sibling(name: str) -> None:
    key = f"servers.google_drive.{name}"
    if key not in _sys.modules:
        path = _Path(__file__).parent / f"{name}.py"
        spec = _ilu.spec_from_file_location(key, path)
        mod = _ilu.module_from_spec(spec)
        _sys.modules[key] = mod
        spec.loader.exec_module(mod)


_load_sibling("_helpers")
_load_sibling("tools_drive")
_load_sibling("tools_sheets")
_load_sibling("tools_docs")

